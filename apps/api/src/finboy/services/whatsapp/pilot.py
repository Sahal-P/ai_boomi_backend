"""The WhatsApp money diary: consent, entries saved at once with undo, and voice in three languages.

Runs for pilot households (`users.pilot`, docs/pilot/contract.md) and for self-serve households
(docs/signup-round/contract.md), in the person's language (services/whatsapp/language.py). Money
a household sends is saved at once and can be undone, changed or re-categorised by button; FinBoy
asks first only when it is unsure (docs/money-manager-round/contract.md). Each inbound message gets
at most one text-or-buttons reply plus one spoken reply. Nothing a household says is stored:
records go through the existing review decisions, and prompts keep only IDs and fingerprints.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import ModuleType
from typing import get_args
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.core.clock import today_ist
from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.core.languages import Language
from finboy.db.models.core import User
from finboy.db.models.ledger import Commitment, EmailSource, SourceEvent, Transaction
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppPrompt, WhatsAppReceipt
from finboy.services.accounts import households
from finboy.services.assistant import service as assistant
from finboy.services.assistant.language import money
from finboy.services.ingestion.hindi_numbers import parse_amount
from finboy.services.ingestion.types import Category
from finboy.services.money import budgets, merchants
from finboy.services.money.models import Correction
from finboy.services.speech import service as speech
from finboy.services.speech.media import InvalidAudio
from finboy.services.ux import decisions
from finboy.services.ux.obligations import ObligationCorrection, correct_obligation
from finboy.services.ux.state import TaskError, data_version
from finboy.services.whatsapp import (
    capture,
    categories,
    cfo,
    english,
    hindi,
    malayalam,
    prompts,
    reminders,
    statement,
)
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.events import InboundQuestion
from finboy.services.whatsapp.meta import InvalidMedia, Listing, MetaClient, MetaUnavailable

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)
Reply = Callable[..., bool]
WORDS = {"en": english, "hi": hindi, "ml": malayalam}
# Entries are saved at once, except these, which wait for a tap (money-manager contract).
ASK_FROM_MINOR = 5_000_000  # ₹50,000
SAME_PAYMENT_DAYS = 2
# The categories offered first when changing one, before the household's own most used.
SPENDING_ORDER: tuple[Category, ...] = (
    "groceries",
    "food_dining",
    "transport",
    "shopping",
    "utilities",
    "phone_recharge",
    "health",
    "rent",
    "education",
    "family_events",
    "loan_emi",
    "travel",
    "subscriptions",
    "investments",
    "farming",
    "livestock",
    "remittance",
    "fees",
)
INCOME_ORDER: tuple[Category, ...] = (
    "salary",
    "wages",
    "other_income",
    "farm_sales",
    "govt_benefit",
    "remittance",
    "transfer",
)


@dataclass
class Conversation:
    session: Session
    settings: Settings
    config: ChannelConfig
    client: MetaClient
    receipt: WhatsAppReceipt
    question: InboundQuestion
    binding: WhatsAppBinding
    reply: Reply  # processor.send_reply: consent lock, allowlist, 24-hour window, idempotency
    self_serve: bool = False  # joined by itself (docs/signup-round/contract.md)
    # The language this message showed, if any: its text, or what speech-to-text heard.
    heard: Language | None = None

    @property
    def language(self) -> Language:
        """A chosen language, else this message's, else the one FinBoy last used, else English."""
        for candidate in (self.binding.language, self.heard, self.binding.last_language):
            if candidate in WORDS:
                return candidate  # type: ignore[return-value]
        return "en"

    @property
    def words(self) -> ModuleType:
        """The `english`, `hindi` or `malayalam` copy module; all define the same names."""
        return WORDS[self.language]

    @property
    def speaks(self) -> bool:
        """Pilot households hear every reply; others hear one when they sent a voice note."""
        return not self.self_serve or self.question.kind == "audio"

    def send(
        self,
        text: str,
        buttons: list[tuple[str, str]] | None = None,
        listing: Listing | None = None,
    ) -> bool:
        # Kept for the next message that shows no language; committed with the delivery.
        self.binding.last_language = self.language
        return self.reply(
            self.session,
            self.config,
            self.client,
            self.receipt,
            self.question,
            text=text,
            buttons=buttons,
            **({"listing": listing} if listing is not None else {}),
        )

    def speak(self, text: str, language: Language | None = None) -> None:
        """Best effort after the written reply; never fabricate or retry audio."""
        if not self.speaks:
            return
        try:
            audio = speech.synthesize_speech(
                text=text, language=language or self.language, settings=self.settings
            )
            if audio.media_type != "audio/mpeg":
                raise InvalidMedia
            media_id = self.client.upload_audio(audio.data)
            self.reply(
                self.session,
                self.config,
                self.client,
                self.receipt,
                self.question,
                media_id=media_id,
            )
        except ProviderUnavailable, MetaUnavailable, InvalidAudio:
            logger.info("whatsapp.pilot_audio_unavailable", extra={"outcome": "text_only"})

    def done(self, sent: bool, error: str | None = None) -> str | None:
        return error or (None if sent else "provider_unavailable")


def handle(conversation: Conversation) -> str | None:
    """Returns the receipt error code (None when the household got a correct reply)."""
    error = _handle(conversation)
    if conversation.binding.consented_at is not None:
        _remind(conversation)
    return error


def _handle(conversation: Conversation) -> str | None:
    question, binding = conversation.question, conversation.binding
    if question.kind == "button":
        return _tap(conversation)
    if binding.consented_at is None:
        return ask_consent(conversation)
    if question.kind == "image":
        return _screenshot(conversation)
    try:
        text = _heard(conversation)
    except ProviderUnavailable, MetaUnavailable, InvalidAudio:
        conversation.session.rollback()
        sent = conversation.send(conversation.words.VOICE_UNCLEAR)
        return conversation.done(sent, "invalid_audio")
    summary = cfo.asked(text)
    if summary is not None:
        return summary(conversation)
    change = prompts.pending_change(conversation.session, binding)
    if change is not None:
        return _changed_amount(conversation, change, text)
    picking = prompts.pending(conversation.session, binding, "pick_category")
    typed = categories.exact(text) if picking is not None else None
    if picking is not None and typed is not None:
        return _set_category(conversation, picking, typed)
    try:
        readings = statement.read_statements(text, conversation.settings, today_ist())
    except ProviderUnavailable:
        conversation.session.rollback()
        sent = conversation.send(conversation.words.UNAVAILABLE)
        return conversation.done(sent, "statement_unavailable")
    reading = readings[0]
    if reading.kind == "question" and reading.checkup is not None:
        return cfo.CHECKUPS[reading.checkup](conversation)
    if reading.kind == "question":
        return _answer(conversation, text)
    if reading.kind == "unclear":
        return _say(conversation, conversation.words.UNCLEAR, conversation.words.UNCLEAR_SPEECH)
    if reading.amount_minor is None:
        return _say(
            conversation,
            conversation.words.AMOUNT_MISSING,
            conversation.words.AMOUNT_MISSING_SPEECH,
            "amount_unclear",
        )
    if reading.kind == "budget":
        return cfo.set_budget(conversation, reading)
    if reading.kind == "goal":
        return cfo.set_goal(conversation, reading)
    if reading.kind == "due":
        return _save_due(conversation, reading)
    if len(readings) > 1:
        return _record_many(conversation, readings)
    return _record_money(conversation, reading)


def _say(conversation: Conversation, text: str, spoken: str, error: str | None = None):
    conversation.session.rollback()
    sent = conversation.send(text)
    if sent:
        conversation.speak(spoken)
    return conversation.done(sent, error)


def _heard(conversation: Conversation) -> str:
    question = conversation.question
    text = question.text
    if question.kind == "audio":
        audio = conversation.client.download_audio(
            question.media_id or "", question.mime_type or ""
        )
        heard = speech.transcribe_audio(
            audio=audio.data,
            content_type=audio.content_type,
            settings=conversation.settings,
            # Only a chosen language is a hint; otherwise speech-to-text detects it.
            language_hint=conversation.binding.language,
        )
        text = heard.transcript
        if heard.detected_language in WORDS:
            conversation.heard = heard.detected_language
    if not 1 <= len(text.strip()) <= 2000:
        raise ProviderUnavailable("invalid_audio")
    return text


def ask_consent(conversation: Conversation) -> str | None:
    words = conversation.words
    if conversation.self_serve and not households.signup_open(
        conversation.session, conversation.settings
    ):
        # FinBoy is full: no consent card, only the waitlist (JOIN is handled by the processor).
        conversation.session.rollback()
        return conversation.done(conversation.send(words.FULL), "signup_full")
    prompt = prompts.open_prompt(conversation.session, conversation.binding, "consent")
    conversation.session.commit()
    sent = conversation.send(
        words.SELF_CONSENT if conversation.self_serve else words.CONSENT,
        [
            (prompts.button(prompt, "agree"), conversation.words.AGREE),
            (prompts.button(prompt, "decline"), conversation.words.DECLINE),
        ],
    )
    if sent:
        conversation.speak(conversation.words.CONSENT_SPEECH)
    return conversation.done(sent)


def _tap(conversation: Conversation) -> str | None:
    session, binding = conversation.session, conversation.binding
    parsed = prompts.parse(conversation.question.button_id or "")
    prompt = prompts.claim(session, binding, parsed[0]) if parsed else None
    handler = HANDLERS.get((prompt.purpose, parsed[1])) if prompt and parsed else None
    if prompt is None or parsed is None or handler is None:
        session.rollback()
        return conversation.done(conversation.send(conversation.words.EXPIRED), "prompt_expired")
    if prompt.purpose != "consent" and binding.consented_at is None:
        session.rollback()
        return ask_consent(conversation)
    return handler(conversation, prompt, parsed[1])


def _consent(conversation: Conversation, prompt: WhatsAppPrompt, choice: str) -> str | None:
    session, binding, words = conversation.session, conversation.binding, conversation.words
    prompts.answer(prompt)
    if choice == "agree" and conversation.self_serve:
        user = session.get(User, binding.user_id, with_for_update=True)
        if user is None or not households.agree(session, conversation.settings, user):
            session.rollback()
            return conversation.done(conversation.send(words.FULL), "signup_full")
    if choice == "agree":
        binding.consented_at = datetime.now(UTC)
    session.commit()
    if choice != "agree":
        sent = conversation.send(words.DECLINED)
        if conversation.self_serve:
            # A household that never agreed keeps nothing (docs/signup-round/contract.md).
            households.discard_pending(session, binding.user_id)
            session.commit()
        return conversation.done(sent)
    sent = conversation.send(conversation.words.WELCOME)
    if sent:
        conversation.speak(conversation.words.WELCOME_SPEECH)
    return conversation.done(sent)


def _record(conversation: Conversation, transaction_id: UUID | None) -> Transaction | None:
    if transaction_id is None:
        return None
    return conversation.session.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == conversation.binding.user_id,
        )
    )


def _payee(merchant: str | None) -> str | None:
    if not merchant or "[address]" in merchant or merchant.lower().startswith("unknown"):
        return None
    return merchant


def _day(row: Transaction) -> date:
    return row.occurred_at.astimezone(IST).date() if row.occurred_at else today_ist()


def _changed(conversation: Conversation, prompt_id: UUID, error: str) -> str | None:
    """The record moved on since the card: stop that card and say so."""
    session = conversation.session
    session.rollback()
    stale = session.get(WhatsAppPrompt, prompt_id, with_for_update=True)
    if stale is not None and stale.state in {"open", "answered"}:
        stale.state = "expired"
    session.commit()
    message = conversation.words.UNDO_REFUSED if error == "undo" else conversation.words.CHANGED
    return conversation.done(conversation.send(message), "record_changed")


def offer_card(conversation: Conversation, transaction_id: UUID, prefix: str = "") -> str | None:
    """The confirm card for a record waiting for review, in text and voice."""
    session, binding = conversation.session, conversation.binding
    row = _record(conversation, transaction_id)
    if row is None or row.status != "needs_review":
        session.rollback()
        return conversation.done(
            conversation.send(prefix + conversation.words.CHANGED), "record_changed"
        )
    prompt = prompts.open_prompt(
        session,
        binding,
        "confirm",
        transaction_id=row.id,
        fingerprint=prompts.record_fingerprint(conversation.config, row),
    )
    text, spoken = conversation.words.record_card(
        amount_minor=row.amount_minor,
        out=row.direction == "out",
        counterparty=_payee(row.merchant),
        day=_day(row),
        category=row.category,
        today=today_ist(),
    )
    session.commit()
    sent = conversation.send(
        prefix + text,
        [
            (prompts.button(prompt, "yes"), conversation.words.YES),
            (prompts.button(prompt, "change"), conversation.words.CHANGE),
            (prompts.button(prompt, "no"), conversation.words.NO),
        ],
    )
    if sent:
        conversation.speak(spoken)
    return conversation.done(sent)


def _same_payment(session: Session, row: Transaction) -> bool:
    """Another record of this amount and direction from around then that came from a screenshot,
    bill, SMS or email: a typed or spoken entry may be the same payment told twice."""
    if row.occurred_at is None:
        return False
    window = timedelta(days=SAME_PAYMENT_DAYS)
    found = session.scalar(
        select(Transaction.id)
        .join(SourceEvent, SourceEvent.transaction_id == Transaction.id)
        .join(EmailSource, EmailSource.id == SourceEvent.email_source_id)
        .where(
            Transaction.user_id == row.user_id,
            Transaction.id != row.id,
            Transaction.dataset == "household",
            Transaction.direction == row.direction,
            Transaction.amount_minor == row.amount_minor,
            Transaction.status.in_(("confirmed", "needs_review")),
            Transaction.occurred_at.between(row.occurred_at - window, row.occurred_at + window),
            EmailSource.source.not_in(("whatsapp_voice", "manual_entry")),
        )
        .limit(1)
    )
    return found is not None


def _unsure(conversation: Conversation, row: Transaction) -> str | None:
    """Why FinBoy asks before saving (the card's first line), or None to save at once."""
    if row.review_reason == "possible_duplicate" or _same_payment(conversation.session, row):
        return conversation.words.ASK_SAME
    if row.amount_minor >= ASK_FROM_MINOR:
        return conversation.words.ASK_BIG
    return None


def _confirm(conversation: Conversation, row: Transaction) -> UUID | None:
    """Save a record under the payee's remembered category; None when it moved on meanwhile."""
    session, user_id = conversation.session, conversation.binding.user_id
    remembered = merchants.remembered(session, user_id, row.merchant)
    try:
        result = decisions.decide(
            session,
            user_id=user_id,
            transaction_id=row.id,
            request=decisions.DecisionRequest(
                action="confirm",
                correction=Correction(category=remembered)
                if remembered is not None and remembered != row.category
                else None,
                expected_version=data_version(session, user_id),
            ),
        )
    except TaskError:
        return None
    return result.decision_id


def _save_or_ask(conversation: Conversation, row: Transaction) -> str | None:
    reason = _unsure(conversation, row)
    if reason is not None:
        return offer_card(conversation, row.id, prefix=reason)
    transaction_id = row.id
    decision_id = _confirm(conversation, row)
    if decision_id is None:
        conversation.session.rollback()
        return conversation.done(conversation.send(conversation.words.CHANGED), "record_changed")
    return saved_card(conversation, transaction_id, decision_id=decision_id)


def saved_card(
    conversation: Conversation,
    transaction_id: UUID,
    *,
    decision_id: UUID | None = None,
    prefix: str = "",
    group_id: UUID | None = None,
) -> str | None:
    """What was saved, with Undo, Amount and Category, and the budget it counts against."""
    session, binding, words = conversation.session, conversation.binding, conversation.words
    row = _record(conversation, transaction_id)
    if row is None or row.status != "confirmed":
        session.rollback()
        return conversation.done(conversation.send(prefix + words.CHANGED), "record_changed")
    prompt = prompts.open_prompt(
        session,
        binding,
        "saved",
        transaction_id=row.id,
        decision_id=decision_id,
        fingerprint=prompts.record_fingerprint(conversation.config, row),
        group_id=group_id,
    )
    today = today_ist()
    budget = (
        budgets.month_plan(session, binding.user_id).budget_for(row.category)
        if row.direction == "out" and _day(row).replace(day=1) == today.replace(day=1)
        else None
    )
    text, spoken = words.saved(
        amount_minor=row.amount_minor,
        out=row.direction == "out",
        counterparty=_payee(row.merchant),
        day=_day(row),
        category=row.category,
        today=today,
        budget=budget,
    )
    session.commit()
    sent = conversation.send(
        prefix + text,
        [
            (prompts.button(prompt, "undo"), words.UNDO),
            (prompts.button(prompt, "amount"), words.AMOUNT),
            (prompts.button(prompt, "category"), words.CATEGORY_BUTTON),
        ],
    )
    if sent:
        conversation.speak(spoken)
    return conversation.done(sent)


def _remove(conversation: Conversation, prompt: WhatsAppPrompt, _choice: str) -> str | None:
    """Undo on a saved entry takes it out of the records (a reject); it can be put back."""
    session, binding, words = conversation.session, conversation.binding, conversation.words
    row = _record(conversation, prompt.transaction_id)
    if row is None or prompts.record_fingerprint(conversation.config, row) != prompt.fingerprint:
        return _changed(conversation, prompt.id, "record")
    transaction_id, prompt_id, group_id = row.id, prompt.id, prompt.group_id
    amount, out, payee = row.amount_minor, row.direction == "out", _payee(row.merchant)
    prompts.answer(prompt)
    try:
        decisions.decide(
            session,
            user_id=binding.user_id,
            transaction_id=transaction_id,
            request=decisions.DecisionRequest(
                action="reject", expected_version=data_version(session, binding.user_id)
            ),
        )
    except TaskError:
        return _changed(conversation, prompt_id, "record")
    removed = _record(conversation, transaction_id)
    if removed is None:
        return _changed(conversation, prompt_id, "record")
    back = prompts.open_prompt(
        session,
        binding,
        "saved",
        transaction_id=transaction_id,
        fingerprint=prompts.record_fingerprint(conversation.config, removed),
        group_id=group_id,
    )
    session.commit()
    sent = conversation.send(
        words.removed(amount, out, payee), [(prompts.button(back, "putback"), words.PUT_BACK)]
    )
    if sent:
        conversation.speak(words.REMOVED_SPEECH)
    return conversation.done(sent)


def _put_back(conversation: Conversation, prompt: WhatsAppPrompt, _choice: str) -> str | None:
    """A removed entry is reopened and saved again (a rejected record can't be confirmed)."""
    session, binding = conversation.session, conversation.binding
    row = _record(conversation, prompt.transaction_id)
    if (
        row is None
        or row.status != "rejected"
        or prompts.record_fingerprint(conversation.config, row) != prompt.fingerprint
    ):
        return _changed(conversation, prompt.id, "undo")
    transaction_id, prompt_id, group_id = row.id, prompt.id, prompt.group_id
    prompts.answer(prompt)
    try:
        for action in ("reopen", "confirm"):
            result = decisions.decide(
                session,
                user_id=binding.user_id,
                transaction_id=transaction_id,
                request=decisions.DecisionRequest(
                    action=action,  # type: ignore[arg-type]
                    expected_version=data_version(session, binding.user_id),
                ),
            )
    except TaskError:
        return _changed(conversation, prompt_id, "undo")
    return saved_card(
        conversation,
        transaction_id,
        decision_id=result.decision_id,
        prefix=conversation.words.PUT_BACK_DONE + "\n\n",
        group_id=group_id,
    )


def _likely(conversation: Conversation, row: Transaction) -> list[Category]:
    """Ten categories to choose from: the household's own most used first, "other" last."""
    order: tuple[Category, ...] = INCOME_ORDER
    if row.direction == "out":
        top = budgets.month_plan(conversation.session, conversation.binding.user_id).top
        order = (*(category for category, _ in top), *SPENDING_ORDER)  # type: ignore[assignment]
    choices = [c for c in dict.fromkeys(order) if c not in {row.category, "other"}][:9]
    return [*choices, "other"] if row.category != "other" else choices


def _pick_category(conversation: Conversation, prompt: WhatsAppPrompt, _choice: str):
    """Category on a saved entry: a WhatsApp list of likely categories; typing one also works."""
    session, binding, words = conversation.session, conversation.binding, conversation.words
    row = _record(conversation, prompt.transaction_id)
    if row is None or prompts.record_fingerprint(conversation.config, row) != prompt.fingerprint:
        return _changed(conversation, prompt.id, "record")
    pick = prompts.open_prompt(
        session,
        binding,
        "pick_category",
        transaction_id=row.id,
        fingerprint=prompt.fingerprint,
        group_id=prompt.group_id,
    )
    rows = [(prompts.button(pick, c), words.CATEGORY[c]) for c in _likely(conversation, row)]
    session.commit()
    sent = conversation.send(
        words.CATEGORY_ASK,
        listing=Listing(words.CATEGORY_OPEN, words.CATEGORY_SECTION, rows),
    )
    return conversation.done(sent)


def _set_category(conversation: Conversation, prompt: WhatsAppPrompt, choice: str):
    """A chosen category; decisions.decide also remembers it for the payee (merchant memory)."""
    session, binding = conversation.session, conversation.binding
    category = next((c for c in get_args(Category) if c == choice), None)
    row = _record(conversation, prompt.transaction_id)
    if (
        category is None
        or row is None
        or prompts.record_fingerprint(conversation.config, row) != prompt.fingerprint
    ):
        return _changed(conversation, prompt.id, "record")
    transaction_id, prompt_id, group_id = row.id, prompt.id, prompt.group_id
    payee = _payee(row.merchant)
    prompts.answer(prompt)
    if category == row.category:
        session.commit()
    else:
        try:
            decisions.decide(
                session,
                user_id=binding.user_id,
                transaction_id=transaction_id,
                request=decisions.DecisionRequest(
                    action="correct",
                    correction=Correction(category=category),
                    expected_version=data_version(session, binding.user_id),
                ),
            )
        except TaskError:
            return _changed(conversation, prompt_id, "record")
    return saved_card(
        conversation,
        transaction_id,
        prefix=conversation.words.category_changed(category, payee) + "\n\n",
        group_id=group_id,
    )


def _fix(conversation: Conversation, prompt: WhatsAppPrompt, _choice: str) -> str | None:
    """One item chosen from "Fix one": its own saved card, or its check card if unsure."""
    row = _record(conversation, prompt.transaction_id)
    if row is None or prompts.record_fingerprint(conversation.config, row) != prompt.fingerprint:
        return _changed(conversation, prompt.id, "record")
    if row.status == "needs_review":
        prompts.answer(prompt)
        return offer_card(conversation, row.id)
    return saved_card(
        conversation, row.id, decision_id=prompt.decision_id, group_id=prompt.group_id
    )


def _title(amount_minor: int, name: str) -> str:
    """A list row title: WhatsApp allows 24 characters."""
    title = f"{money(amount_minor)} · {name}"
    return title if len(title) <= 24 else title[:23] + "…"


def _fix_one(conversation: Conversation, prompt: WhatsAppPrompt, _choice: str) -> str | None:
    """ "Fix one" on a message of several items: a list of them to choose from."""
    session, binding, words = conversation.session, conversation.binding, conversation.words
    rows = []
    for item in prompts.group(session, binding, prompt.id):
        row = _record(conversation, item.transaction_id)
        if row is not None and row.status in {"confirmed", "needs_review"}:
            name = _payee(row.merchant) or words.CATEGORY.get(row.category, words.CATEGORY["other"])
            rows.append((prompts.button(item, "fix"), _title(row.amount_minor, name)))
    session.commit()
    if not rows:
        return conversation.done(conversation.send(words.NOTHING_TO_FIX), "record_changed")
    sent = conversation.send(
        words.FIX_ASK, listing=Listing(words.FIX_OPEN, words.FIX_SECTION, rows[:10])
    )
    return conversation.done(sent)


def _remove_all(conversation: Conversation, prompt: WhatsAppPrompt, _choice: str) -> str | None:
    """ "Undo all": every item of the message that is still saved as it was is taken out."""
    session, binding, words = conversation.session, conversation.binding, conversation.words
    group_id = prompt.id
    prompts.answer(prompt)
    session.commit()
    count = total = 0
    for item in prompts.group(session, binding, group_id):
        row = _record(conversation, item.transaction_id)
        if (
            row is None
            or row.status != "confirmed"
            or prompts.record_fingerprint(conversation.config, row) != item.fingerprint
        ):
            continue
        amount = row.amount_minor
        prompts.answer(item)
        try:
            decisions.decide(
                session,
                user_id=binding.user_id,
                transaction_id=row.id,
                request=decisions.DecisionRequest(
                    action="reject", expected_version=data_version(session, binding.user_id)
                ),
            )
        except TaskError:
            continue
        count, total = count + 1, total + amount
    session.commit()
    if not count:
        return conversation.done(conversation.send(words.NOTHING_TO_FIX), "record_changed")
    sent = conversation.send(words.removed_many(count, total))
    if sent:
        conversation.speak(words.REMOVED_SPEECH)
    return conversation.done(sent)


def _decide(conversation: Conversation, prompt: WhatsAppPrompt, choice: str) -> str | None:
    if prompt.commitment_id is not None:
        return _decide_due(conversation, prompt, choice)
    session, binding = conversation.session, conversation.binding
    row = _record(conversation, prompt.transaction_id)
    if row is None or prompts.record_fingerprint(conversation.config, row) != prompt.fingerprint:
        return _changed(conversation, prompt.id, "record")
    prompt_id, transaction_id = prompt.id, row.id
    prompts.answer(prompt)
    if choice == "yes":
        # Checked and saved: the same card as an entry saved at once, with Undo, Amount, Category.
        decision_id = _confirm(conversation, row)
        if decision_id is None:
            return _changed(conversation, prompt_id, "record")
        return saved_card(conversation, transaction_id, decision_id=decision_id)
    try:
        result = decisions.decide(
            session,
            user_id=binding.user_id,
            transaction_id=row.id,
            request=decisions.DecisionRequest(
                action="reject", expected_version=data_version(session, binding.user_id)
            ),
        )
    except TaskError:
        return _changed(conversation, prompt_id, "record")
    undo = prompts.open_prompt(
        session, binding, "undo", transaction_id=transaction_id, decision_id=result.decision_id
    )
    session.commit()
    sent = conversation.send(
        conversation.words.REJECTED, [(prompts.button(undo, "undo"), conversation.words.UNDO)]
    )
    if sent:
        conversation.speak(conversation.words.NOT_ADDED_SPEECH)
    return conversation.done(sent)


def _ask_amount(conversation: Conversation, prompt: WhatsAppPrompt, _choice: str) -> str | None:
    if prompt.commitment_id is not None:
        due = _due_row(conversation, prompt.commitment_id)
        current = prompts.due_fingerprint(conversation.config, due) if due else None
    else:
        row = _record(conversation, prompt.transaction_id)
        current = prompts.record_fingerprint(conversation.config, row) if row else None
    if current is None or current != prompt.fingerprint:
        return _changed(conversation, prompt.id, "record")
    if prompt.purpose != "saved":
        prompts.answer(prompt)  # a saved entry's Undo keeps working until the amount arrives
    prompts.open_prompt(
        conversation.session,
        conversation.binding,
        "change_amount",
        transaction_id=prompt.transaction_id,
        commitment_id=prompt.commitment_id,
        fingerprint=prompt.fingerprint,
        group_id=prompt.group_id,
    )
    conversation.session.commit()
    sent = conversation.send(conversation.words.CHANGE_ASK)
    if sent:
        conversation.speak(conversation.words.CHANGE_ASK_SPEECH)
    return conversation.done(sent)


def _changed_amount(conversation: Conversation, change: WhatsAppPrompt, text: str) -> str | None:
    """The reply after "रकम बदलें" is read only as an amount, then the card comes back: the saved
    entry's card if it was saved, else the card asking for a check."""
    session, binding = conversation.session, conversation.binding
    amount = parse_amount(text)
    if amount is None or amount > budgets.MAX_MINOR:
        session.rollback()
        return conversation.done(
            conversation.send(conversation.words.AMOUNT_UNCLEAR), "amount_unclear"
        )
    if change.commitment_id is not None:
        return _changed_due_amount(conversation, change, amount)
    row = _record(conversation, change.transaction_id)
    if row is None or prompts.record_fingerprint(conversation.config, row) != change.fingerprint:
        return _changed(conversation, change.id, "record")
    change_id, transaction_id, group_id = change.id, row.id, change.group_id
    saved = row.status == "confirmed"
    prompts.answer(change)
    if amount != row.amount_minor:
        try:
            decisions.decide(
                session,
                user_id=binding.user_id,
                transaction_id=transaction_id,
                request=decisions.DecisionRequest(
                    action="correct",
                    correction=Correction(amount_minor=amount),
                    expected_version=data_version(session, binding.user_id),
                ),
            )
        except TaskError:
            return _changed(conversation, change_id, "record")
    else:
        session.commit()
    if saved:
        prefix = conversation.words.AMOUNT_CHANGED + "\n\n"
        return saved_card(conversation, transaction_id, prefix=prefix, group_id=group_id)
    return offer_card(conversation, transaction_id)


def _undo(conversation: Conversation, prompt: WhatsAppPrompt, _choice: str) -> str | None:
    if prompt.commitment_id is not None:
        return _undo_due(conversation, prompt)
    session, binding = conversation.session, conversation.binding
    prompt_id, transaction_id, decision_id = prompt.id, prompt.transaction_id, prompt.decision_id
    if transaction_id is None or decision_id is None:
        return _changed(conversation, prompt_id, "undo")
    prompts.answer(prompt)
    try:
        decisions.undo_decision(
            session,
            user_id=binding.user_id,
            transaction_id=transaction_id,
            decision_id=decision_id,
            expected_version=data_version(session, binding.user_id),
        )
    except TaskError:
        return _changed(conversation, prompt_id, "undo")
    return offer_card(conversation, transaction_id, prefix=conversation.words.UNDONE + "\n\n")


def _screenshot(conversation: Conversation) -> str | None:
    session = conversation.session
    # End this read snapshot; the import pipeline commits through its own sessions.
    session.rollback()
    result = capture.capture_screenshot(
        session.get_bind(),
        conversation.settings,
        conversation.client,
        conversation.question,
        conversation.binding.user_id,
    )
    row = _record(conversation, result.transaction_id) if result.outcome == "saved" else None
    if row is not None and row.status == "needs_review":
        return _save_or_ask(conversation, row)
    if row is not None and row.status == "confirmed":
        return saved_card(conversation, row.id)
    sent = conversation.send(capture.capture_reply(result, conversation.language))
    return conversation.done(sent, capture.RECEIPT_ERRORS.get(result.outcome))


def _answer(conversation: Conversation, text: str) -> str | None:
    """Questions use the shared assistant: engine figures, wording in the person's language."""
    from finboy.services.whatsapp.processor import phone_text

    session, binding = conversation.session, conversation.binding
    try:
        answer = assistant.answer_question(
            session,
            user_id=binding.user_id,
            text=text,
            # A chosen language, else the question's own, like the web's "Match my question".
            display_style=binding.language or "auto",
            settings=conversation.settings,
        )
    except ProviderUnavailable:
        session.rollback()
        return conversation.done(
            conversation.send(conversation.words.UNAVAILABLE), "assistant_unavailable"
        )
    conversation.heard = answer.speech_language
    response = phone_text(answer.display_text)
    sent = conversation.send(response if len(response) <= 4096 else conversation.words.UNAVAILABLE)
    if sent and 1 <= len(answer.speech_text) <= 600:
        conversation.speak(answer.speech_text, answer.speech_language)
    return conversation.done(sent)


def _record_money(conversation: Conversation, reading: statement.Statement) -> str | None:
    """Money spent or received, typed or said: one line through the pipeline, then saved at
    once, or a card first when FinBoy is unsure."""
    session, question = conversation.session, conversation.question
    session.rollback()  # end this read snapshot; the import pipeline commits on its own
    result = capture.record_voice(
        session.get_bind(),
        conversation.settings,
        user_id=conversation.binding.user_id,
        message_id=question.message_id,
        line=statement.payment_line(reading, question.provider_at),
        received_at=question.provider_at,
        category=reading.category,
    )
    row = _record(conversation, result.transaction_id)
    if row is not None and row.status == "needs_review":
        return _save_or_ask(conversation, row)
    if row is not None and row.status == "confirmed":
        return conversation.done(conversation.send(conversation.words.ALREADY))
    if result.outcome == "busy":
        return conversation.done(conversation.send(conversation.words.BUSY), "capture_busy")
    return conversation.done(
        conversation.send(conversation.words.UNAVAILABLE), "capture_unavailable"
    )


def _record_many(conversation: Conversation, readings: list[statement.Statement]) -> str | None:
    """Several payments in one message, each its own record: saved at once, except unsure
    ones, which wait for a check through "Fix one". One reply with Undo all and Fix one."""
    session, binding, question = conversation.session, conversation.binding, conversation.question
    words = conversation.words
    kept: list[tuple[UUID, UUID | None]] = []  # (record, its confirm decision)
    busy = False
    for index, reading in enumerate(readings, start=1):
        session.rollback()  # the import pipeline commits through its own sessions
        result = capture.record_voice(
            session.get_bind(),
            conversation.settings,
            user_id=binding.user_id,
            message_id=f"{question.message_id}#{index}",
            line=statement.payment_line(reading, question.provider_at),
            received_at=question.provider_at,
            category=reading.category,
        )
        row = _record(conversation, result.transaction_id)
        if row is None:
            busy = busy or result.outcome == "busy"
            continue
        if row.status == "needs_review" and _unsure(conversation, row) is None:
            transaction_id = row.id
            kept.append((transaction_id, _confirm(conversation, row)))
        elif row.status in {"needs_review", "confirmed"}:
            kept.append((row.id, None))
    session.rollback()
    group = prompts.open_prompt(session, binding, "pick_item")
    saved, unsure = [], []
    for transaction_id, decision_id in kept:
        row = _record(conversation, transaction_id)
        if row is None or row.status not in {"confirmed", "needs_review"}:
            continue
        prompts.open_prompt(
            session,
            binding,
            "saved",
            transaction_id=row.id,
            decision_id=decision_id,
            fingerprint=prompts.record_fingerprint(conversation.config, row),
            group_id=group.id,
        )
        item = (row.amount_minor, row.direction == "out", _payee(row.merchant), row.category)
        (saved if row.status == "confirmed" else unsure).append(item)
    if not saved and not unsure:
        session.rollback()
        if busy:
            return conversation.done(conversation.send(words.BUSY), "capture_busy")
        return conversation.done(conversation.send(words.UNAVAILABLE), "capture_unavailable")
    plan = budgets.month_plan(session, binding.user_id) if saved else None
    warnings = {
        status.category: status
        for _, out, _, category in saved
        if out and plan and (status := plan.budget_for(category)) and status.level != "ok"
    }
    text, spoken = words.saved_many(saved=saved, unsure=unsure, budgets=list(warnings.values())[:2])
    session.commit()
    buttons = [(prompts.button(group, "fixone"), words.FIX_ONE)]
    if saved:
        buttons.insert(0, (prompts.button(group, "undoall"), words.UNDO_ALL))
    sent = conversation.send(text, buttons)
    if sent:
        conversation.speak(spoken)
    return conversation.done(sent)


def _due_row(conversation: Conversation, commitment_id: UUID | None) -> Commitment | None:
    if commitment_id is None:
        return None
    return conversation.session.scalar(
        select(Commitment).where(
            Commitment.id == commitment_id,
            Commitment.user_id == conversation.binding.user_id,
            Commitment.dataset == "household",
        )
    )


def _save_due(conversation: Conversation, reading: statement.Statement) -> str | None:
    """A spoken due is kept as `pending` (never counted) until the household taps हाँ."""
    if reading.due_date is None or reading.amount_minor is None:
        return _say(
            conversation,
            conversation.words.DUE_DAY_MISSING,
            conversation.words.DUE_DAY_MISSING_SPEECH,
        )
    row = Commitment(
        id=uuid4(),
        user_id=conversation.binding.user_id,
        kind="loan",
        label=reading.label or conversation.words.DUE_LABEL,
        amount_minor=reading.amount_minor,
        due_date=reading.due_date,
        status="pending",
        confidence=Decimal("1.000"),
        user_resolved=False,
    )
    conversation.session.add(row)
    conversation.session.flush()
    return offer_due_card(conversation, row.id)


def offer_due_card(conversation: Conversation, commitment_id: UUID, prefix: str = "") -> str | None:
    session, binding = conversation.session, conversation.binding
    row = _due_row(conversation, commitment_id)
    if row is None or row.status != "pending":
        session.rollback()
        return conversation.done(
            conversation.send(prefix + conversation.words.CHANGED), "record_changed"
        )
    prompt = prompts.open_prompt(
        session,
        binding,
        "confirm",
        commitment_id=row.id,
        fingerprint=prompts.due_fingerprint(conversation.config, row),
    )
    text, spoken = conversation.words.due_card(
        amount_minor=row.amount_minor, label=row.label, due=row.due_date
    )
    session.commit()
    sent = conversation.send(
        prefix + text,
        [
            (prompts.button(prompt, "yes"), conversation.words.YES),
            (prompts.button(prompt, "change"), conversation.words.CHANGE),
            (prompts.button(prompt, "no"), conversation.words.NO),
        ],
    )
    if sent:
        conversation.speak(spoken)
    return conversation.done(sent)


def _decide_due(conversation: Conversation, prompt: WhatsAppPrompt, choice: str) -> str | None:
    session, binding = conversation.session, conversation.binding
    row = _due_row(conversation, prompt.commitment_id)
    if (
        row is None
        or row.status != "pending"
        or prompts.due_fingerprint(conversation.config, row) != prompt.fingerprint
    ):
        return _changed(conversation, prompt.id, "record")
    prompts.answer(prompt)
    row.status = "upcoming" if choice == "yes" else "dismissed"
    row.user_resolved = choice != "yes"
    session.flush()
    undo = prompts.open_prompt(
        session,
        binding,
        "undo",
        commitment_id=row.id,
        fingerprint=prompts.due_fingerprint(conversation.config, row),
    )
    buttons = [(prompts.button(undo, "undo"), conversation.words.UNDO)]
    text = conversation.words.due_saved(row.amount_minor, row.label, row.due_date)
    if choice != "yes":
        text = conversation.words.REJECTED
    elif binding.reminders_opt_in_at is None and not conversation.self_serve:
        # Asked once, after the household's first due; reminders are strictly opt-in. They reach
        # pilot households only so far, so a self-serve household is never promised one.
        opt_in = prompts.open_prompt(session, binding, "reminder_opt_in")
        buttons.insert(0, (prompts.button(opt_in, "remind"), conversation.words.REMIND))
        text += "\n\n" + conversation.words.REMIND_ASK
    session.commit()
    sent = conversation.send(text, buttons)
    if sent:
        conversation.speak(
            conversation.words.REMEMBERED_SPEECH
            if choice == "yes"
            else conversation.words.NOT_ADDED_SPEECH
        )
    return conversation.done(sent)


def _changed_due_amount(conversation: Conversation, change: WhatsAppPrompt, amount: int):
    row = _due_row(conversation, change.commitment_id)
    if (
        row is None
        or row.status != "pending"
        or prompts.due_fingerprint(conversation.config, row) != change.fingerprint
    ):
        return _changed(conversation, change.id, "record")
    prompts.answer(change)
    row.amount_minor = amount  # still pending: nothing counts until हाँ
    conversation.session.flush()
    return offer_due_card(conversation, row.id)


def _undo_due(conversation: Conversation, prompt: WhatsAppPrompt) -> str | None:
    row = _due_row(conversation, prompt.commitment_id)
    if (
        row is None
        or row.status not in {"upcoming", "dismissed"}
        or prompts.due_fingerprint(conversation.config, row) != prompt.fingerprint
    ):
        return _changed(conversation, prompt.id, "undo")
    prompts.answer(prompt)
    row.status, row.user_resolved = "pending", False
    conversation.session.flush()
    return offer_due_card(conversation, row.id, prefix=conversation.words.UNDONE + "\n\n")


def _reminders(conversation: Conversation, prompt: WhatsAppPrompt, _choice: str) -> str | None:
    prompts.answer(prompt)
    conversation.binding.reminders_opt_in_at = datetime.now(UTC)
    conversation.session.commit()
    sent = conversation.send(conversation.words.REMINDERS_ON)
    if sent:
        conversation.speak(conversation.words.REMINDERS_ON)
    return conversation.done(sent)


def _remind(conversation: Conversation) -> None:
    """Without a reminder template, a due coming up follows the reply as its own card."""
    session, binding = conversation.session, conversation.binding
    session.rollback()
    today = today_ist()
    due = reminders.fallback_due(session, conversation.settings, binding, today)
    reminder = reminders.claim(session, due, "sending") if due else None
    if due is None or reminder is None:
        session.rollback()
        return
    row = due.commitment
    prompt = prompts.open_prompt(
        session,
        binding,
        "due_paid",
        commitment_id=row.id,
        fingerprint=prompts.due_fingerprint(conversation.config, row),
    )
    text = conversation.words.due_notice(row.amount_minor, row.label, row.due_date, today)
    buttons = [
        (prompts.button(prompt, "paid"), conversation.words.PAID),
        (prompts.button(prompt, "later"), conversation.words.LATER),
    ]
    session.commit()
    sent = conversation.reply(
        session,
        conversation.config,
        conversation.client,
        conversation.receipt,
        conversation.question,
        text=text,
        buttons=buttons,
        reminder=True,
    )
    reminder.state = "sent" if sent else "failed"
    reminder.updated_at = datetime.now(UTC)
    session.commit()


def _reopen(session: Session, prompt_id: UUID) -> None:
    """Nothing was recorded, so the same button may be tapped again."""
    session.rollback()
    prompt = session.get(WhatsAppPrompt, prompt_id, with_for_update=True)
    if prompt is not None and prompt.state == "answered":
        prompt.state, prompt.answered_at = "open", None
    session.commit()


def _paid(conversation: Conversation, prompt: WhatsAppPrompt, _choice: str) -> str | None:
    """Records the payment as a confirmed outflow and links it to the due.

    The due then stops being deducted, so money left falls only by the amount actually paid.
    `decide` may already link it (payee equals the due label); `correct_obligation` makes sure.
    """
    session, binding, question = conversation.session, conversation.binding, conversation.question
    row = _due_row(conversation, prompt.commitment_id)
    if row is not None and row.status == "paid":
        prompts.answer(prompt)
        session.commit()
        return conversation.done(conversation.send(conversation.words.ALREADY_PAID))
    if (
        row is None
        or row.status != "upcoming"
        or prompts.due_fingerprint(conversation.config, row) != prompt.fingerprint
    ):
        return _changed(conversation, prompt.id, "record")
    prompt_id, due_id, amount, label = prompt.id, row.id, row.amount_minor, row.label
    prompts.answer(prompt)  # committed first: a second tap cannot record a second payment
    session.commit()
    payment = statement.Statement("spent", amount, label, "unknown", today_ist(), "loan_emi")
    result = capture.record_voice(
        session.get_bind(),
        conversation.settings,
        user_id=binding.user_id,
        message_id=question.message_id,
        line=statement.payment_line(payment, question.provider_at),
        received_at=question.provider_at,
        category="loan_emi",
    )
    paid = _record(conversation, result.transaction_id)
    if paid is None or paid.amount_minor != amount or paid.direction != "out":
        _reopen(session, prompt_id)
        if result.outcome == "busy":
            return conversation.done(conversation.send(conversation.words.BUSY), "capture_busy")
        return conversation.done(
            conversation.send(conversation.words.UNAVAILABLE), "capture_unavailable"
        )
    paid_id = paid.id
    try:
        if paid.status == "needs_review":
            decisions.decide(
                session,
                user_id=binding.user_id,
                transaction_id=paid_id,
                request=decisions.DecisionRequest(
                    action="confirm", expected_version=data_version(session, binding.user_id)
                ),
            )
        correct_obligation(
            session,
            user_id=binding.user_id,
            obligation_id=due_id,
            request=ObligationCorrection(
                expected_version=data_version(session, binding.user_id),
                status="paid",
                paid_transaction_id=paid_id,
            ),
        )
    except TaskError:
        return _changed(conversation, prompt_id, "record")
    repeat = prompts.open_prompt(session, binding, "due_repeat", commitment_id=due_id)
    session.commit()
    sent = conversation.send(
        conversation.words.paid_done(amount, label) + "\n\n" + conversation.words.REPEAT_ASK,
        [
            (prompts.button(repeat, "again"), conversation.words.AGAIN),
            (prompts.button(repeat, "skip"), conversation.words.NO),
        ],
    )
    if sent:
        conversation.speak(conversation.words.PAID_REPEAT_SPEECH)
    return conversation.done(sent)


def _later(conversation: Conversation, _prompt: WhatsAppPrompt, _choice: str) -> str | None:
    """The reminder's "भर दिया" button stays usable until the household has paid."""
    conversation.session.commit()
    return conversation.done(conversation.send(conversation.words.LATER_OK))


def _next_month(day: date) -> date:
    first = (day.replace(day=1) + timedelta(days=32)).replace(day=1)
    following = (first + timedelta(days=32)).replace(day=1)
    return first.replace(day=min(day.day, (following - timedelta(days=1)).day))


def _repeat(conversation: Conversation, prompt: WhatsAppPrompt, choice: str) -> str | None:
    """Next month's due is saved directly: the household just said it repeats. Undoable."""
    session = conversation.session
    row = _due_row(conversation, prompt.commitment_id)
    prompts.answer(prompt)
    if choice != "again" or row is None:
        session.commit()
        return conversation.done(conversation.send(conversation.words.OK))
    following = Commitment(
        id=uuid4(),
        user_id=conversation.binding.user_id,
        kind=row.kind,
        label=row.label,
        amount_minor=row.amount_minor,
        due_date=_next_month(row.due_date),
        status="upcoming",
        confidence=Decimal("1.000"),
        user_resolved=False,
    )
    session.add(following)
    session.flush()
    undo = prompts.open_prompt(
        session,
        conversation.binding,
        "undo",
        commitment_id=following.id,
        fingerprint=prompts.due_fingerprint(conversation.config, following),
    )
    session.commit()
    sent = conversation.send(
        conversation.words.due_saved(following.amount_minor, following.label, following.due_date),
        [(prompts.button(undo, "undo"), conversation.words.UNDO)],
    )
    if sent:
        conversation.speak(conversation.words.REMEMBERED_SPEECH)
    return conversation.done(sent)


HANDLERS: dict[tuple[str, str], Callable[[Conversation, WhatsAppPrompt, str], str | None]] = {
    ("consent", "agree"): _consent,
    ("consent", "decline"): _consent,
    ("confirm", "yes"): _decide,
    ("confirm", "no"): _decide,
    ("confirm", "change"): _ask_amount,
    ("undo", "undo"): _undo,
    ("reminder_opt_in", "remind"): _reminders,
    ("due_paid", "paid"): _paid,
    ("due_paid", "later"): _later,
    ("due_repeat", "again"): _repeat,
    ("due_repeat", "skip"): _repeat,
    ("saved", "undo"): _remove,
    ("saved", "putback"): _put_back,
    ("saved", "amount"): _ask_amount,
    ("saved", "category"): _pick_category,
    ("saved", "fix"): _fix,
    ("pick_item", "undoall"): _remove_all,
    ("pick_item", "fixone"): _fix_one,
    **{("pick_category", category): _set_category for category in get_args(Category)},
    ("checkin_opt_in", "checkin"): cfo.checkin_choice,
    ("checkin_opt_in", "nocheckin"): cfo.checkin_choice,
}
