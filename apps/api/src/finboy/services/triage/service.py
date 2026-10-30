"""d1-ultra decides what a diary message, question or photo is, so FinBoy can answer before the
slower model call when it is sure (docs/triage-round/contract.md).

Today's model call always starts at the same moment, so no reply waits longer than before, and a
sure decision still answers when the model fails. Nothing is stored; logs carry fixed fields only.
"""

import logging
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from time import perf_counter

from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.core.languages import Language
from finboy.services.ingestion.types import Category
from finboy.services.triage import provider
from finboy.services.triage.provider import Choice, Noul

logger = logging.getLogger(__name__)

# How sure d1-ultra must be before FinBoy acts on it; set by the offline gate (`pnpm eval:triage`,
# results in the round contract).
SURE = 0.85  # the probability of a chosen option
CLEAR_NO = 0.1  # a yes/no probability this close to 0 or 1
IMAGE_SURE = 0.95  # a photo that is neither a payment nor a bill
# Each message or question takes two workers: today's model call and the d1-ultra sort.
_POOL = ThreadPoolExecutor(max_workers=32, thread_name_prefix="triage")

# What each category covers, in the order the statement prompt lists them.
CATEGORY_HINTS: dict[Category, str] = {
    "groceries": "ration, kirana, milk, vegetables, supermarket",
    "food_dining": "tea, snacks, eating out, Swiggy, Zomato",
    "transport": "bus, auto, taxi, Uber, Ola, metro, petrol, fuel",
    "shopping": "clothes, electronics, Amazon, Flipkart",
    "utilities": "electricity, water, gas cylinder, internet",
    "phone_recharge": "",
    "subscriptions": "Netflix, OTT, apps",
    "rent": "",
    "health": "medicine, doctor, hospital",
    "education": "school, college, books, tuition",
    "travel": "train, flight, hotel",
    "investments": "SIP, mutual fund, FD, RD, gold, money put into savings",
    "loan_emi": "loan, EMI, SHG or instalment repayment",
    "fees": "bank charges",
    "family_events": "wedding, festival, gifts, ceremonies",
    "remittance": "money sent to or received from family",
    "farming": (
        "seeds, fertiliser, pesticide, diesel for pump or tractor, tractor hire, farm labour"
    ),
    "livestock": "fodder, animal medicine, animals",
    "salary": "their salary",
    "wages": "pay for their own work, mazdoori",
    "farm_sales": "selling crops, milk, vegetables",
    "govt_benefit": "PM-KISAN, pension, MGNREGA, ration or gas subsidy",
    "other_income": "",
    "transfer": "to their own account",
    "other": "",
}
CATEGORIES: dict[str, Category] = {name: name for name in CATEGORY_HINTS}
_KINDS_OF_MONEY = {
    **{
        name: name.replace("_", " ") + (f": {hint}" if hint else "")
        for name, hint in CATEGORY_HINTS.items()
    },
    "other": "anything else",
    "none": "no kind of spending or income is named",
}
# As in categories.SYNONYMS, food in general is eating, not groceries.
FOOD = "Food or meals in general (food, khana, खाना, ഭക്ഷണം) is food dining."

MESSAGE: dict[str, provider.Question] = {
    "kind": Choice(
        instructions=(
            "A household sent this message to FinBoy, their money diary, in English, Hindi, "
            "Hinglish, Malayalam or Manglish. What is the message?"
        ),
        criteria={
            "spent": (
                "Records money they paid, gave or spent, something they bought, or a bill or fee "
                "they paid (दिए, खर्च किए, भरे, चुकाए, diye, കൊടുത്തു, ചെലവായി, അടച്ചു, koduthu). "
                "An item with just an amount, like 'chai 20' or 'auto 50', is money spent"
            ),
            "received": (
                "Records money that came to them, such as salary, wages or a sale (आए, मिले, "
                "mile, aaye, കിട്ടി, വന്നു, kitti)"
            ),
            "due": (
                "A payment they still have to make later, such as an instalment, loan, bill, fee "
                "or rent (किस्त, बकाया, देना है, भरना है, EMI, അടയ്ക്കണം, കൊടുക്കണം)"
            ),
            "budget": "Sets a monthly spending limit, such as 'food budget 5000'",
            "goal": "Sets how much they want to save each month",
            "today": (
                "Asks for today's money summary in general, not about one category, shop or person"
            ),
            "week": "Asks for this week's money summary or account (hisaab) in general",
            "month": "Asks for this month's money summary, budgets or savings goal in general",
            "question": "Any other question about their money",
            "other": "A greeting, thanks, or anything that is not about their money",
        },
    ),
    "several": Noul(
        instructions=(
            "Does the message list more than one payment, each with its own amount, like "
            "'chai 20, auto 50'?"
        )
    ),
    "payee": Noul(
        instructions=(
            "Does the message name who was paid or who paid them: a person, a named shop or "
            "company, or a person by their work, like 'milkman', 'Ramesh', 'Swiggy', 'दूधवाले' "
            "or 'പാൽക്കാരന്'? Things bought (tea, petrol, vegetables), kinds of spending or "
            "income (kirana, rent, bill, salary) and ways to pay (cash, UPI, GPay, PhonePe) are "
            "not names."
        )
    ),
    "category": Choice(
        instructions="Which kind of spending or income is the money in this message for? " + FOOD,
        criteria=_KINDS_OF_MONEY,
    ),
    "mode": Choice(
        instructions="How was the money paid?",
        criteria={
            "cash": "In cash: नकद, कैश, cash, കാശ്, പണമായി",
            "upi": "By UPI or a payment app: UPI, PhonePe, GPay, Paytm, फोनपे, गूगल पे, पेटीएम",
            "unknown": "The message does not say",
        },
    ),
}
QUESTION: dict[str, provider.Question] = {
    "intent": Choice(
        instructions=(
            "A household asked FinBoy, their money diary, this question in English, Hindi, "
            "Hinglish, Malayalam or Manglish. What does it ask?"
        ),
        criteria={
            "spending": "How much they spent in a period, in total or on one kind of spending",
            "income": "How much income or salary they received in a period",
            "left_over": "How much money is left over, unallocated or remaining",
            "bills": "Which bills, dues or payments are coming up or still unpaid",
            "afford_monthly": "Whether a monthly amount, such as a SIP or EMI, fits their money",
            "shop_or_person": "What they paid one particular shop, app or person",
            "explain": (
                "What a money term means, such as SIP, EMI, UPI, diversification or index fund"
            ),
            "investment_pick": "Which fund, stock or share to buy, sell or choose",
            "purchase": "Buying something such as a phone, bike or car, or an opinion on buying it",
            "other": "Anything else",
        },
    ),
    "topic": Choice(
        instructions="Which money term does the question ask about?",
        criteria={
            "sip": "SIP, a systematic investment plan",
            "emi": "EMI, an equated monthly instalment",
            "upi": "UPI payments",
            "diversification": "Diversification",
            "index_fund": "Index funds",
            "none": "None of these",
        },
    ),
    "category": Choice(
        instructions=(
            "Which one kind of spending or income does the question name? A question about all "
            "spending or all income names none. " + FOOD
        ),
        criteria=_KINDS_OF_MONEY,
    ),
    "merchant": Noul(
        instructions=(
            "Does the question name one particular shop, app, company or person, like Swiggy, "
            "Amazon or Ramesh?"
        )
    ),
}
PICTURE: dict[str, provider.Question] = {
    "image": Choice(
        instructions=(
            "A household sent this picture to FinBoy, their money diary, on WhatsApp. "
            "What does it show?"
        ),
        criteria={
            "payment_screen": "A phone screen showing a UPI or bank payment, sent or received",
            "bill": "A shop bill, receipt or invoice for a purchase",
            "other": (
                "Anything else: a photo, selfie, greeting, forwarded picture, chat, or a document "
                "without a payment"
            ),
        },
    )
}


@dataclass(frozen=True)
class Sorted:
    """d1-ultra's answers to one request. Each read gives a value only when it is sure."""

    answers: Mapping[str, provider.Answer]

    def pick(self, name: str, sure: float | None = None) -> str | None:
        """The chosen option, when its probability reaches `sure` (SURE when not given)."""
        answer = self.answers.get(name)
        if not isinstance(answer, provider.ChoiceAnswer):
            return None
        level = SURE if sure is None else sure
        return answer.choice if answer.probabilities.get(answer.choice, 0.0) >= level else None

    def says(self, name: str) -> bool | None:
        """Yes or no, when d1-ultra is clear either way."""
        answer = self.answers.get(name)
        if not isinstance(answer, provider.NoulAnswer):
            return None
        if answer.noul >= 1 - CLEAR_NO:
            return True
        return False if answer.noul <= CLEAR_NO else None


def sort_message(text: str, language: Language, settings: Settings) -> Sorted | None:
    """A diary message: what it is, whether it lists several payments or names a payee, its
    category and how it was paid. None when off, not for this language, unavailable or late."""
    return _sort("message", text, MESSAGE, settings, language)


def sort_question(text: str, language: Language, settings: Settings) -> Sorted | None:
    """A question: what it asks, a money term, a category, and whether it names a payee."""
    return _sort("question", text, QUESTION, settings, language)


def sort_image(jpeg: bytes, settings: Settings) -> Sorted | None:
    """A photo: a payment screen, a bill, or anything else."""
    state = "A picture a household sent to FinBoy on WhatsApp."
    return _sort("image", state, PICTURE, settings, images=(jpeg,))


def _sort(
    stage: str,
    state: str,
    questions: dict[str, provider.Question],
    settings: Settings,
    language: Language | None = None,
    images: tuple[bytes, ...] = (),
) -> Sorted | None:
    if not settings.triage_enabled or (
        language is not None and language not in settings.triage_languages
    ):
        return None
    started = perf_counter()
    try:
        answers = provider.decide(state, questions, settings, images=images)
    except ProviderUnavailable:
        _log("triage.sorted", stage, "unavailable", started, settings.liquid_decision_model)
        return None
    _log("triage.sorted", stage, "sorted", started, settings.liquid_decision_model)
    return Sorted(answers)


def first[T, S, F](
    stage: str,
    settings: Settings,
    model: Callable[[], T],
    sort: Callable[[], S | None],
    fast: Callable[[S], F | None],
) -> T | F:
    """Today's model call and a d1-ultra sort start together; `fast` turns a sort into an answer,
    or None when it is not sure. A sure answer is used only while the model is still working, so
    no reply waits longer than today, and it stands in when the model fails."""
    started = perf_counter()
    if not settings.triage_enabled:
        try:
            result = model()
        except Exception:
            _log("triage.answered", stage, "failed", started)
            raise
        _log("triage.answered", stage, "model", started)
        return result
    model_call, sort_call = _POOL.submit(model), _POOL.submit(sort)
    for done in as_completed((model_call, sort_call)):
        if done is model_call and done.exception() is None:
            _log("triage.answered", stage, "model", started)
            return model_call.result()
        if done is sort_call and (answer := _sure(sort_call, fast)) is not None:
            # The model's result, when it comes, is dropped unread.
            _log("triage.answered", stage, "fast", started)
            return answer
    _log("triage.answered", stage, "failed", started)
    return model_call.result()  # neither answered: raise the model's own error


def _sure[S, F](sort_call: Future[S | None], fast: Callable[[S], F | None]) -> F | None:
    """A failed or unsure sort, or a broken `fast`, leaves the answer to the model."""
    try:
        sorted_ = sort_call.result()
        return None if sorted_ is None else fast(sorted_)
    except Exception:
        logger.warning("triage.fast_failed", extra={"outcome": "model"})
        return None


def _log(event: str, stage: str, outcome: str, started: float, model: str | None = None) -> None:
    extra: dict[str, object] = {
        "stage": stage,
        "outcome": outcome,
        "latency_ms": round((perf_counter() - started) * 1000),
    }
    if model is not None:
        extra |= {"provider": "liquid", "model": model}
    logger.info(event, extra=extra)
