"""The WhatsApp money diary: consent, entries saved at once with undo, and voice in three languages.

Runs for pilot households (`users.pilot`, docs/pilot/contract.md) and for self-serve households
(docs/signup-round/contract.md), in the person's language (services/whatsapp/language.py). Money
a household sends is saved at once and can be undone, changed or re-categorised by button; FinBoy
asks first only when it is unsure (docs/money-manager-round/contract.md). Each inbound message gets
at most one text-or-buttons reply plus one spoken reply. Records go through the existing review
decisions and prompts keep only IDs and fingerprints; what a household says is kept only in the
message log of a household that agreed (docs/conversation-round/contract.md).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import ModuleType
from typing import get_args
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from finboy.core.clock import today_ist
from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.core.languages import Language
from finboy.db.models.core import User
from finboy.db.models.ledger import Commitment, EmailSource, SourceEvent, Transaction
from finboy.db.models.whatsapp import (
    WhatsAppBinding,
    WhatsAppDelivery,
    WhatsAppPrompt,
    WhatsAppReceipt,
)
from finboy.services.accounts import households
from finboy.services.advisor import memory as advisor_memory
from finboy.services.advisor import service as advisor
from finboy.services.assistant import service as assistant
from finboy.services.assistant.language import money
from finboy.services.assistant.models import AssistantAnswer
from finboy.services.conversations import store
from finboy.services.ingestion import dates
from finboy.services.ingestion.hindi_numbers import only_amount
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
    missing_amount,
    premium,
    prompts,
    reminders,
    replies,
    statement,
)
from finboy.services.whatsapp import coach as coaching
from finboy.services.whatsapp import memory as memory_commands
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
    "work",
    "friends",
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
    # A line added once to the next written reply, like "📝 Saved to memory".
    note: str | None = None
    # A card (buttons or a list) went out for this message: one interactive reply per message.
    carded: bool = False

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
        limit = 1024 if buttons or listing else 4096  # an interactive body holds 1,024
        if self.note and len(text) + len(self.note) + 2 <= limit:
            text, self.note = f"{text}\n\n{self.note}", None
        sent = self.reply(
            self.session,
            self.config,
            self.client,
            self.receipt,
            self.question,
            text=text,
            buttons=buttons,
            **({"listing": listing} if listing is not None else {}),
        )
        if sent and (buttons or listing):
            self.carded = True
            self._stamp(
                [key for key, _ in (listing.rows if listing is not None else buttons or [])]
            )
        return sent

    def _stamp(self, keys: list[str]) -> None:
        """Which WhatsApp message carried these cards, so a swipe-reply to it finds them."""
        ids = {parsed[0] for key in keys if (parsed := prompts.parse(key))}
        outbound = self.session.scalar(
            select(WhatsAppDelivery.outbound_message_id).where(
                WhatsAppDelivery.receipt_id == self.receipt.id,
                WhatsAppDelivery.kind == "interactive",
            )
        )
        if ids and outbound:
            prompts.stamp(self.session, self.binding, ids, outbound)
            self.session.commit()

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
                spoken=text,
            )
        except ProviderUnavailable, MetaUnavailable, InvalidAudio:
            logger.info("whatsapp.pilot_audio_unavailable", extra={"outcome": "text_only"})

    def done(self, sent: bool, error: str | None = None) -> str | None:
        return error or (None if sent else "provider_unavailable")


# A first "Hi FinBoy" (the website's prefilled send) is a greeting, not an expense.
_GREETINGS = frozenset(
    {
        "hi",
        "hi finboy",
        "hello",
        "hello finboy",
        "hey",
        "namaste",
        "नमस्ते",
        "नमस्ते finboy",
        "namaskaram",
        "നമസ്കാരം",
    }
)


def _greeting(question: InboundQuestion) -> bool:
    if question.kind != "text":
        return False
    return " ".join(question.text.split()).casefold() in _GREETINGS


def _note_kept(conversation: Conversation) -> None:
    """With the log on, keep messages from now. A household that declined stays declined."""
    if not conversation.config.messages:
        return
    conversation.session.execute(
        update(User)
        .where(
            User.id == conversation.binding.user_id,
            User.messages_kept_from.is_(None),
            User.messages_declined_at.is_(None),
        )
        .values(messages_kept_from=datetime.now(UTC))
    )


def begin(conversation: Conversation, *, welcome: bool) -> tuple[bool, str | None]:
    """The first message agrees and continues. A greeting gets the welcome and stops.

    Returns whether the caller should keep handling this message, and the receipt error when
    the reply is already done.
    """
    binding = conversation.binding
    if binding.consented_at is not None:
        _note_kept(conversation)
        return True, None
    words = conversation.words
    if conversation.self_serve and not households.signup_open(
        conversation.session, conversation.settings
    ):
        conversation.session.rollback()
        return False, conversation.done(conversation.send(words.FULL), "signup_full")
    if conversation.self_serve:
        user = conversation.session.get(User, binding.user_id, with_for_update=True)
        if user is None or not households.agree(conversation.session, conversation.settings, user):
            conversation.session.rollback()
            return False, conversation.done(conversation.send(words.FULL), "signup_full")
    binding.consented_at = datetime.now(UTC)
    _note_kept(conversation)
    conversation.session.commit()
    if not welcome:
        return True, None
    sent = conversation.send(words.WELCOME)
    if sent:
        conversation.speak(words.WELCOME_SPEECH)
    return False, conversation.done(sent)


def handle(conversation: Conversation) -> str | None:
    """Returns the receipt error code (None when the household got a correct reply)."""
    if conversation.binding.consented_at is not None:
        _note_kept(conversation)
    error = _handle(conversation)
    if conversation.binding.consented_at is not None:
        _offer_waiting_due(conversation)
        _remind(conversation)
        premium.nudge(conversation)
    return error


def _handle(conversation: Conversation) -> str | None:
    question, binding = conversation.question, conversation.binding
    # Only the very next message can answer "how many rupees?" or "which date?".
    waiting = missing_amount.take(binding.id)
    if question.kind == "button":
        return _tap(conversation)
    if binding.consented_at is None:
        keep, error = begin(conversation, welcome=_greeting(question))
        if not keep:
            return error
    if question.kind == "image":
        return _screenshot(conversation)
    try:
        text = _heard(conversation)
    except ProviderUnavailable, MetaUnavailable, InvalidAudio:
        if waiting is not None:
            missing_amount.hold(binding.id, waiting)  # saying it again still answers
        conversation.session.rollback()
        sent = conversation.send(conversation.words.VOICE_UNCLEAR)
        return conversation.done(sent, "invalid_audio")
    if waiting is not None:
        finished, error = _finish_waiting(conversation, waiting, text)
        if finished:
            return error
    summary = cfo.asked(text)
    if summary is not None:
        return summary(conversation)
    advising = conversation.settings.advisor_enabled
    command = memory_commands.command(text) if advising else None
    if command is None and conversation.config.messages:
        command = memory_commands.clearing(text)  # kept messages can always be cleared
    if command is None and conversation.settings.coach_active:
        command = coaching.command(text)  # "coach on" / "coach off" (advisor phase 3)
    if command is not None:
        return command(conversation)
    answered, error, fixing = _reply_to_card(conversation, text)
    if answered:
        return error
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
    if fixing is not None:
        settled, error = _settle_fix(conversation, fixing, reading, text)
        if settled:
            return error
    if reading.kind == "question" and reading.checkup is not None:
        return cfo.CHECKUPS[reading.checkup](conversation)
    if advising and reading.kind in {"question", "unclear"}:
        # The advisor answers questions and everyday chat for every household, and remembers
        # what matters ("I'm saving for a bike"); see docs/advisor-round/contract.md.
        return _advise(conversation, text)
    if reading.kind == "question":
        # AI answers are Premium; the check-ups above stay free (docs/subscription-round).
        if not premium.allowed(conversation):
            return premium.refuse(conversation, "PREMIUM_ASK")
        return _answer(conversation, text)
    if reading.kind == "unclear":
        return _say(conversation, conversation.words.UNCLEAR, conversation.words.UNCLEAR_SPEECH)
    if advising and reading.remember:
        _learn(conversation, reading)
    if reading.amount_minor is None:
        # The reply is usually just the amount; the entry waits for it (its fact is learned).
        missing_amount.hold(binding.id, replace(reading, remember=None))
        return _say(
            conversation,
            conversation.words.AMOUNT_MISSING,
            conversation.words.AMOUNT_MISSING_SPEECH,
            "amount_unclear",
        )
    return _save(conversation, readings)


def _finish_waiting(
    conversation: Conversation, waiting: statement.Statement, text: str
) -> tuple[bool, str | None]:
    """The message after "how many rupees?" or "which date?": only that answer completes the
    entry; anything else is read as usual and the entry is forgotten."""
    if waiting.kind == "due" and waiting.amount_minor is not None and waiting.due_date is None:
        today = today_ist()
        reply = replies.read_reply(text, today, "future")
        day = reply.day
        if reply.kind == "fix" and day is None and reply.amount_minor and not reply.month:
            number = reply.amount_minor // 100  # "5" answers "which day?"
            if reply.amount_minor % 100 == 0 and 1 <= number <= 31:
                day = (
                    dates.place(waiting.date_month, number, None, today, "future")
                    if waiting.date_problem == "month_only" and waiting.date_month
                    else dates.day_of_month(number, today, "future")
                )
        if reply.kind == "fix" and day is not None:
            return True, _save(conversation, [replace(waiting, due_date=day, date_problem=None)])
        if reply.kind == "fix" and reply.month is not None and reply.amount_minor is None:
            asked = replace(waiting, date_problem="month_only", date_month=reply.month)
            return True, _ask_date(conversation, asked)
        return False, None
    amount = only_amount(text)
    if amount is None:
        return False, None
    return True, _save(conversation, [replace(waiting, amount_minor=amount)])


def _save(conversation: Conversation, readings: list[statement.Statement]) -> str | None:
    """Money, a due, a budget or a goal whose amount is known. Payments and dues sent together
    save the payments and ask for the due on its own; several dues take the first, and say so."""
    reading = readings[0]
    if reading.kind == "budget":
        return cfo.set_budget(conversation, reading)
    if reading.kind == "goal":
        return cfo.set_goal(conversation, reading)
    dues = [item for item in readings if item.kind == "due"]
    payments = [item for item in readings if item.kind in {"spent", "received"}]
    if dues and payments:
        conversation.note = conversation.words.DUE_ON_ITS_OWN
        readings = payments
    elif dues:
        if len(dues) > 1:
            conversation.note = conversation.words.DUES_ONE_AT_A_TIME
        return _save_due(conversation, dues[0])
    if len(readings) > 1:
        return _record_many(conversation, readings)
    return _record_money(conversation, readings[0])


def _learn(conversation: Conversation, reading: statement.Statement) -> None:
    """A lasting fact the diary message states ("Ramesh is the milkman") joins the household's
    memory when memory is on. Only the fact is kept, never the message."""
    session, user_id = conversation.session, conversation.binding.user_id
    if not advisor_memory.enabled(session, user_id):
        return
    change = advisor_memory.learn(
        session,
        user_id,
        reading.remember_kind,
        reading.remember,
        "whatsapp",
        conversation.settings.advisor_memory_limit,
    )
    session.commit()
    if change is not None:
        conversation.note = conversation.words.MEMORY_UPDATED


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
        store.note_transcript(
            conversation.session.get_bind(),
            conversation.receipt.id,
            text,
            heard.detected_language,
        )
        if heard.detected_language in WORDS:
            conversation.heard = heard.detected_language
    if not 1 <= len(text.strip()) <= 2000:
        raise ProviderUnavailable("invalid_audio")
    return text


def _tap(conversation: Conversation) -> str | None:
    session, binding = conversation.session, conversation.binding
    parsed = prompts.parse(conversation.question.button_id or "")
    prompt = prompts.claim(session, binding, parsed[0]) if parsed else None
    handler = HANDLERS.get((prompt.purpose, parsed[1])) if prompt and parsed else None
    if prompt is None or parsed is None or handler is None:
        session.rollback()
        return _closed_tap(conversation, parsed[0] if parsed else None)
    return handler(conversation, prompt, parsed[1])


def _closed_tap(conversation: Conversation, prompt_id: UUID | None) -> str | None:
    """Say what became of a card whose buttons no longer act: saved, dropped, replaced by a
    newer card, or too old."""
    words = conversation.words
    old = prompts.find(conversation.session, conversation.binding, prompt_id) if prompt_id else None
    if old is not None and old.state == "superseded":
        return conversation.done(conversation.send(words.TAP_REPLACED), "prompt_replaced")
    if old is not None and old.state == "answered":
        status = _status_of(conversation, old)
        text = (
            words.TAP_SAVED
            if status in {"confirmed", "upcoming", "paid"}
            else words.TAP_DROPPED
            if status in {"rejected", "dismissed", "merged"}
            else words.TAP_ANSWERED
        )
        return conversation.done(conversation.send(text), "prompt_answered")
    text = words.TAP_OLD if old is not None else words.EXPIRED
    return conversation.done(conversation.send(text), "prompt_expired")


def _status_of(conversation: Conversation, prompt: WhatsAppPrompt) -> str | None:
    due = _due_row(conversation, prompt.commitment_id)
    if due is not None:
        return due.status
    row = _record(conversation, prompt.transaction_id)
    return row.status if row is not None else None


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
    prompts.close_changes(session, binding, transaction_id=transaction_id)
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
    """✏️ on a card. The card keeps working (✅ and ❌ still act) while FinBoy waits for the
    right amount, date or name; a saved entry's "Amount" asks for the amount."""
    if prompt.commitment_id is not None:
        due = _due_row(conversation, prompt.commitment_id)
        current = prompts.due_fingerprint(conversation.config, due) if due else None
    else:
        row = _record(conversation, prompt.transaction_id)
        current = prompts.record_fingerprint(conversation.config, row) if row else None
    if current is None or current != prompt.fingerprint:
        return _changed(conversation, prompt.id, "record")
    words = conversation.words
    if prompt.purpose == "saved":
        text, spoken = words.CHANGE_ASK, words.CHANGE_ASK_SPEECH
    elif prompt.commitment_id is not None:
        text, spoken = words.FIX_DUE_ASK, words.FIX_DUE_ASK_SPEECH
    else:
        text, spoken = words.FIX_RECORD_ASK, words.FIX_RECORD_ASK_SPEECH
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
    sent = conversation.send(text)
    if sent:
        conversation.speak(spoken)
    return conversation.done(sent)


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


def with_sources(response: str, answer: AssistantAnswer, words: ModuleType) -> str:
    """An advisor reply names the FinBoy guides (each with its official site) and the web pages
    it is based on."""
    lines = [response]
    for kind, line in (("guide", words.GUIDES), ("web", words.WEB)):
        named = "; ".join(
            f"{source.title} {source.url}" if source.url else source.title
            for source in answer.sources
            if source.kind == kind
        )
        if named:
            lines.append(line.format(guides=named))
    return "\n\n".join(lines)


def _advise(conversation: Conversation, text: str) -> str | None:
    """The advisor: the household's own figures, its memories and this chat, in its language."""
    from finboy.services.whatsapp.processor import phone_text

    session, binding = conversation.session, conversation.binding
    try:
        answer = advisor.advise(
            session,
            user_id=binding.user_id,
            text=text,
            display_style=binding.language or "auto",  # type: ignore[arg-type]
            channel="whatsapp",
            settings=conversation.settings,
        )
    except ProviderUnavailable, ValueError:
        session.rollback()
        return conversation.done(
            conversation.send(conversation.words.UNAVAILABLE), "assistant_unavailable"
        )
    conversation.heard = answer.speech_language
    response = with_sources(phone_text(answer.display_text), answer, conversation.words)
    if any(change.action != "forgotten" for change in answer.memory_changes):
        response += "\n\n" + conversation.words.MEMORY_UPDATED
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
    """A spoken due is kept as `pending` (never counted) until the household taps yes. Sent
    again with the same amount before then, it replaces that unconfirmed one."""
    if reading.amount_minor is None or reading.due_date is None:
        return _ask_date(conversation, reading)
    session, words = conversation.session, conversation.words
    earlier = _unconfirmed(conversation, reading.amount_minor)
    if earlier is not None:
        earlier.due_date = reading.due_date
        if reading.label:
            earlier.label = reading.label
        session.flush()
        return offer_due_card(conversation, earlier.id, prefix=words.DUE_REPLACED + "\n\n")
    twin = _already_saved(conversation, reading.amount_minor, reading.due_date)
    row = Commitment(
        id=uuid4(),
        user_id=conversation.binding.user_id,
        kind="loan",
        label=reading.label or words.DUE_LABEL,
        amount_minor=reading.amount_minor,
        due_date=reading.due_date,
        status="pending",
        confidence=Decimal("1.000"),
        user_resolved=False,
    )
    session.add(row)
    session.flush()
    prefix = words.due_already(twin.amount_minor, twin.due_date) + "\n\n" if twin else ""
    return offer_due_card(conversation, row.id, prefix=prefix)


def _ask_date(conversation: Conversation, reading: statement.Statement) -> str | None:
    """A due whose date can't be used waits (one message) for it, and FinBoy says what it needs:
    the day in the month named, a real date, a nearer date, or one of two dates."""
    words = conversation.words
    missing_amount.hold(conversation.binding.id, replace(reading, remember=None))
    if reading.date_problem == "month_only" and reading.date_month:
        text = words.DUE_DAY_ASK.format(month=words.MONTHS[reading.date_month - 1])
    else:
        text = {
            "invalid": words.DUE_DATE_INVALID,
            "out_of_range": words.DUE_DATE_FAR,
            "ambiguous": words.DUE_DATE_UNSURE,
        }.get(reading.date_problem or "", words.DUE_DATE_ASK)
    return _say(conversation, text, words.DUE_DATE_ASK_SPEECH, "date_unclear")


def _unconfirmed(conversation: Conversation, amount_minor: int) -> Commitment | None:
    """The household's due of this amount from the last day that still waits for its yes."""
    return conversation.session.scalar(
        select(Commitment)
        .where(
            Commitment.user_id == conversation.binding.user_id,
            Commitment.dataset == "household",
            Commitment.status == "pending",
            Commitment.amount_minor == amount_minor,
            Commitment.created_at >= datetime.now(UTC) - timedelta(days=1),
        )
        .order_by(Commitment.created_at.desc())
        .limit(1)
    )


def _already_saved(conversation: Conversation, amount_minor: int, due: date) -> Commitment | None:
    """A saved due of the same amount near the same date: the card warns before a second one."""
    return conversation.session.scalar(
        select(Commitment)
        .where(
            Commitment.user_id == conversation.binding.user_id,
            Commitment.dataset == "household",
            Commitment.status == "upcoming",
            Commitment.amount_minor == amount_minor,
            Commitment.due_date.between(due - timedelta(days=20), due + timedelta(days=20)),
        )
        .order_by(Commitment.due_date)
        .limit(1)
    )


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
    prompts.close_changes(session, binding, commitment_id=row.id)
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


# Replies typed to a card (docs/whatsapp.md, "Dates and card replies"): "yes", "galat", "5 jan".
CARD_WINDOW = timedelta(minutes=30)


def _reply_to_card(
    conversation: Conversation, text: str
) -> tuple[bool, str | None, WhatsAppPrompt | None]:
    """A typed answer to the card the household is looking at: the one it swiped to reply to,
    else the newest open card from the last half hour. Returns whether it was one, the receipt
    error, and an open correction that the message may still be answering."""
    session, binding = conversation.session, conversation.binding
    card = prompts.target(session, binding, conversation.question.context_id, CARD_WINDOW)
    if card is None:
        return False, None, None
    due = _due_row(conversation, card.commitment_id)
    row = _record(conversation, card.transaction_id)
    if due is None and row is None:
        return False, None, None
    fixing = card if card.purpose == "change_amount" else None
    reply = replies.read_reply(text, today_ist(), "future" if due is not None else "past")
    if reply.kind == "other":
        return False, None, fixing
    waiting = (due is not None and due.status == "pending") or (
        row is not None and row.status == "needs_review"
    )
    if waiting and card.purpose in {"confirm", "change_amount"}:
        return True, _answer_waiting(conversation, card, due, row, reply), None
    if fixing is not None and row is not None and row.status == "confirmed":
        return True, _answer_amount(conversation, fixing, row, reply), None
    dated = reply.kind == "fix" and reply.amount_minor is None
    if card.purpose == "saved" and row is not None and row.status == "confirmed":
        if reply.kind == "undo":
            return True, _remove(conversation, card, "undo"), None
        if dated:
            return True, _fix_saved(conversation, card, row, None, reply), None
    if card.purpose == "undo" and due is not None and due.status == "upcoming":
        if reply.kind == "undo":
            return True, _undo_due(conversation, card), None
        if dated:
            return True, _fix_upcoming(conversation, card, due, reply), None
    return False, None, fixing


def _answer_waiting(
    conversation: Conversation,
    card: WhatsAppPrompt,
    due: Commitment | None,
    row: Transaction | None,
    reply: replies.Reply,
) -> str | None:
    """Yes, no, cancel or a correction typed to a card that waits for a check."""
    session, binding, words = conversation.session, conversation.binding, conversation.words
    confirm = prompts.card_for(session, binding, card)
    correcting = card.purpose == "change_amount"
    if reply.kind in {"no", "cancel"} and correcting:
        prompts.answer(card)
        session.commit()
        return conversation.done(conversation.send(words.FIX_CANCELLED))
    if reply.kind in {"yes", "cancel", "undo"}:
        if confirm is None:  # its card is gone: show it again rather than guess
            prompts.close_changes(
                session,
                binding,
                transaction_id=card.transaction_id,
                commitment_id=card.commitment_id,
            )
            return _card_again(conversation, due, row)
        return _decide(conversation, confirm, "yes" if reply.kind == "yes" else "no")
    if reply.kind == "no":
        # "No" typed to the card itself: ask what is wrong rather than drop it.
        prompts.open_prompt(
            session,
            binding,
            "change_amount",
            transaction_id=card.transaction_id,
            commitment_id=card.commitment_id,
            fingerprint=card.fingerprint,
        )
        session.commit()
        return conversation.done(conversation.send(words.WHAT_WRONG))
    if due is not None:
        day = _day_for(reply, due.due_date, "future")
        if day is None and reply.amount_minor is None:
            return _unclear_fix(conversation)
        return _fix_due(conversation, due, amount=reply.amount_minor, day=day)
    assert row is not None
    day = _day_for(reply, _day(row), "past")
    if day is None and reply.amount_minor is None:
        return _unclear_fix(conversation)
    return _fix_record(conversation, card, row, reply.amount_minor, day)


def _answer_amount(
    conversation: Conversation, change: WhatsAppPrompt, row: Transaction, reply: replies.Reply
) -> str | None:
    """The saved entry's "Amount" question: an amount or date corrects it, undo takes it out,
    and anything else that only answers (yes, no, cancel) ends the question."""
    session, binding = conversation.session, conversation.binding
    if reply.kind == "fix":
        return _fix_saved(conversation, change, row, reply.amount_minor, reply)
    if reply.kind == "undo":
        saved = session.scalar(
            select(WhatsAppPrompt)
            .where(
                WhatsAppPrompt.binding_id == binding.id,
                WhatsAppPrompt.purpose == "saved",
                WhatsAppPrompt.state == "open",
                WhatsAppPrompt.transaction_id == row.id,
                WhatsAppPrompt.expires_at > datetime.now(UTC),
            )
            .order_by(WhatsAppPrompt.created_at.desc())
            .limit(1)
        )
        if saved is not None:
            prompts.answer(change)
            return _remove(conversation, saved, "undo")
    prompts.answer(change)
    session.commit()
    return conversation.done(conversation.send(conversation.words.FIX_CANCELLED))


def _settle_fix(
    conversation: Conversation, change: WhatsAppPrompt, reading: statement.Statement, text: str
) -> tuple[bool, str | None]:
    """A message during a correction that was not a plain amount, date or answer. A question or
    a new entry ends the correction (the card keeps working, and the reply says so); the same
    due sent again, or a new name for it, corrects it; anything unclear asks again."""
    session, words = conversation.session, conversation.words
    due = _due_row(conversation, change.commitment_id)
    row = _record(conversation, change.transaction_id)
    pending = due is not None and due.status == "pending"
    if reading.kind == "unclear":
        if pending and _looks_like_name(text):
            return True, _fix_due(conversation, due, label=" ".join(text.split()))
        session.rollback()
        if row is not None and row.status == "confirmed":
            return True, conversation.done(
                conversation.send(words.AMOUNT_UNCLEAR), "amount_unclear"
            )
        return True, _unclear_fix(conversation)
    if (
        reading.kind == "due"
        and pending
        and reading.amount_minor in {None, due.amount_minor}
        and (reading.due_date is not None or reading.label)
    ):
        return True, _fix_due(conversation, due, day=reading.due_date, label=reading.label)
    prompts.answer(change)
    session.commit()
    if pending or (row is not None and row.status == "needs_review"):
        conversation.note = words.CARD_WAITING
    return False, None


def _unclear_fix(conversation: Conversation) -> str | None:
    conversation.session.rollback()
    return conversation.done(conversation.send(conversation.words.FIX_UNCLEAR), "reply_unclear")


def _looks_like_name(text: str) -> bool:
    """A short reply without numbers or a question, like "SBI card" or "rent"."""
    clean = " ".join(text.split())
    return (
        0 < len(clean) <= 40
        and len(clean.split()) <= 5
        and not any(character.isdigit() or character in "?？" for character in clean)
    )


def _day_for(reply: replies.Reply, base: date, direction: dates.Direction) -> date | None:
    """A corrected date; a month alone keeps the card's day ("january" after 1 December)."""
    if reply.day is not None:
        return reply.day
    if reply.month is not None:
        return dates.place(reply.month, base.day, None, today_ist(), direction)
    return None


def _card_again(
    conversation: Conversation, due: Commitment | None, row: Transaction | None
) -> str | None:
    if due is not None:
        return offer_due_card(conversation, due.id)
    assert row is not None
    return offer_card(conversation, row.id)


def _fix_due(
    conversation: Conversation,
    due: Commitment,
    *,
    amount: int | None = None,
    day: date | None = None,
    label: str | None = None,
) -> str | None:
    """A pending due takes the corrected amount, date or name, then shows its card again;
    nothing counts until yes."""
    prompts.close_changes(conversation.session, conversation.binding, commitment_id=due.id)
    if amount is not None and 0 < amount <= budgets.MAX_MINOR:
        due.amount_minor = amount
    if day is not None:
        due.due_date = day
    if label:
        due.label = label[:160]
    conversation.session.flush()
    return offer_due_card(conversation, due.id)


def _correction(row: Transaction, amount: int | None, day: date | None) -> Correction | None:
    fields: dict[str, object] = {}
    if amount is not None and amount != row.amount_minor and 0 < amount <= budgets.MAX_MINOR:
        fields["amount_minor"] = amount
    if day is not None and day != _day(row):
        clock = (row.occurred_at or datetime.now(UTC)).astimezone(IST).timetz()
        fields["occurred_at"] = datetime.combine(day, clock)
    return Correction(**fields) if fields else None  # type: ignore[arg-type]


def _correct(conversation: Conversation, row: Transaction, correction: Correction) -> bool:
    session, user_id = conversation.session, conversation.binding.user_id
    try:
        decisions.decide(
            session,
            user_id=user_id,
            transaction_id=row.id,
            request=decisions.DecisionRequest(
                action="correct",
                correction=correction,
                expected_version=data_version(session, user_id),
            ),
        )
    except TaskError:
        return False
    return True


def _fix_record(
    conversation: Conversation,
    card: WhatsAppPrompt,
    row: Transaction,
    amount: int | None,
    day: date | None,
) -> str | None:
    """A record waiting for a check takes the corrected amount or date; its card comes back."""
    transaction_id, card_id = row.id, card.id
    prompts.close_changes(conversation.session, conversation.binding, transaction_id=row.id)
    correction = _correction(row, amount, day)
    if correction is None:
        conversation.session.commit()
    elif not _correct(conversation, row, correction):
        return _changed(conversation, card_id, "record")
    return offer_card(conversation, transaction_id)


def _fix_saved(
    conversation: Conversation,
    card: WhatsAppPrompt,
    row: Transaction,
    amount: int | None,
    reply: replies.Reply,
) -> str | None:
    """A saved entry takes the corrected amount or date at once, with its card and Undo."""
    words = conversation.words
    transaction_id, card_id, group_id = row.id, card.id, card.group_id
    prompts.close_changes(conversation.session, conversation.binding, transaction_id=row.id)
    correction = _correction(row, amount, _day_for(reply, _day(row), "past"))
    if correction is None:
        conversation.session.commit()
        return saved_card(conversation, transaction_id, group_id=group_id)
    if not _correct(conversation, row, correction):
        return _changed(conversation, card_id, "record")
    prefix = (words.AMOUNT_CHANGED if correction.amount_minor else words.DATE_CHANGED) + "\n\n"
    return saved_card(conversation, transaction_id, prefix=prefix, group_id=group_id)


def _fix_upcoming(
    conversation: Conversation, card: WhatsAppPrompt, due: Commitment, reply: replies.Reply
) -> str | None:
    """A saved due's date typed after its card, corrected like the website's edit, with Undo."""
    session, binding, words = conversation.session, conversation.binding, conversation.words
    day = _day_for(reply, due.due_date, "future")
    if day is None:
        return _unclear_fix(conversation)
    due_id, card_id = due.id, card.id
    try:
        correct_obligation(
            session,
            user_id=binding.user_id,
            obligation_id=due_id,
            request=ObligationCorrection(
                expected_version=data_version(session, binding.user_id), due_date=day
            ),
        )
    except TaskError:
        return _changed(conversation, card_id, "record")
    row = _due_row(conversation, due_id)
    if row is None:
        return _changed(conversation, card_id, "record")
    undo = prompts.open_prompt(
        session,
        binding,
        "undo",
        commitment_id=row.id,
        fingerprint=prompts.due_fingerprint(conversation.config, row),
    )
    text = words.DATE_CHANGED + "\n\n" + words.due_saved(row.amount_minor, row.label, row.due_date)
    session.commit()
    return conversation.done(conversation.send(text, [(prompts.button(undo, "undo"), words.UNDO)]))


def _offer_waiting_due(conversation: Conversation) -> None:
    """A due still waiting for its yes with no working card is shown again after this
    message's reply (its new card lasts a week), so nothing waits unseen."""
    if conversation.carded:
        return
    session, binding = conversation.session, conversation.binding
    session.rollback()
    now = datetime.now(UTC)
    live = select(WhatsAppPrompt.commitment_id).where(
        WhatsAppPrompt.binding_id == binding.id,
        WhatsAppPrompt.state == "open",
        WhatsAppPrompt.expires_at > now,
        WhatsAppPrompt.commitment_id.is_not(None),
    )
    row = session.scalar(
        select(Commitment)
        .where(
            Commitment.user_id == binding.user_id,
            Commitment.dataset == "household",
            Commitment.status == "pending",
            Commitment.created_at < now - timedelta(minutes=2),
            Commitment.id.not_in(live),
        )
        .order_by(Commitment.created_at.desc())
        .limit(1)
    )
    if row is None:
        session.rollback()
        return
    offer_due_card(conversation, row.id, prefix=conversation.words.DUE_PENDING + "\n\n")


HANDLERS: dict[tuple[str, str], Callable[[Conversation, WhatsAppPrompt, str], str | None]] = {
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
    ("coach_opt_in", "coach"): coaching.choice,
    ("coach_opt_in", "nocoach"): coaching.choice,
}
