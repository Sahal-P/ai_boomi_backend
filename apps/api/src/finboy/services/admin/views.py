"""Everything the admin panel can show (docs/admin-round/contract.md): who each household is,
fixed codes, dates and counts.

These models are the boundary. Since the names and search round (docs/names-search-round), an
admin sees a household's name, phone number and email. Since the conversation round
(docs/conversation-round/contract.md), `MessageRow` and `MessagePage` carry the kept messages of
households that agreed: what they and FinBoy said, transcripts, and whether a voice note or photo
can be opened. No other model has a field for an amount of a household's records, a payee,
category, label, message, chat, memory, hash or key. FinBoy's own payment records (₹299 sales)
are the only money shown.
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from finboy.services.billing.plans import Renewal, State

Kind = Literal["owner", "pilot", "self_serve", "pending", "former_pilot"]
Status = Literal["active", "suspended", "deleted"]
Action = Literal["sign_out", "suspend", "restore", "erase", "premium", "autopay_cancel", "pay_link"]


class HouseholdRow(BaseModel):
    id: UUID
    short_id: str
    name: str | None
    phone: str | None  # the WhatsApp number's digits, like "919876543210"
    kind: Kind
    status: Status
    whatsapp: bool
    google: bool
    joined_at: datetime
    agreed_at: datetime | None
    last_active_at: datetime | None
    plan: State
    language: str | None


class HouseholdPage(BaseModel):
    items: list[HouseholdRow]
    total: int
    offset: int
    next_offset: int | None


class PlanSummary(BaseModel):
    state: State
    trial_ends_at: datetime | None
    paid_through: datetime | None
    renewal: Renewal | None
    next_charge_on: date | None
    grace_until: datetime | None


class PaymentRow(BaseModel):
    id: UUID
    household_id: UUID
    short_id: str
    household_name: str | None
    created_at: datetime
    amount_minor: int
    status: str
    kind: str
    mode: str | None
    txnid: str
    payu_id: str | None
    error_code: str | None
    covers_to: datetime | None


class PaymentPage(BaseModel):
    items: list[PaymentRow]
    total: int
    offset: int
    next_offset: int | None


class Usage(BaseModel):
    ai: int
    voice: int
    ai_limit: int
    voice_limit: int


class ImportRow(BaseModel):
    mode: str
    status: str
    error_code: str | None
    started_at: datetime | None
    finished_at: datetime | None


class StatementRow(BaseModel):
    period_start: date
    period_end: date
    pages: int
    rows_total: int
    reconciled: bool
    removed: bool


class GmailState(BaseModel):
    status: str
    connected_at: datetime
    last_synced_at: datetime | None
    revoked: bool


class WhatsAppState(BaseModel):
    replies_on: bool  # False after the person sent STOP
    agreed_at: datetime | None
    reminders: bool
    checkins: bool
    language: str | None
    last_message_at: datetime | None


class MessageState(BaseModel):
    kept_from: datetime | None  # when FinBoy started keeping its messages (it agreed)
    declined_at: datetime | None  # it answered "No thanks"
    count: int


class HouseholdDetail(HouseholdRow):
    suspended_at: datetime | None
    deleted_at: datetime | None
    last_message_at: datetime | None
    last_record_at: datetime | None
    # The full email once the household signs in with Google again; until then the masked one.
    google_email: str | None
    # What the household typed for PayU receipts, when it differs from the above.
    payer_email: str | None
    payer_phone: str | None
    plan_detail: PlanSummary
    payments: list[PaymentRow]
    usage: Usage
    records: dict[str, int]
    dues: dict[str, int]
    budgets: int
    goal_set: bool
    imports: list[ImportRow]
    statements: list[StatementRow]
    gmail: GmailState | None
    whatsapp_state: WhatsAppState | None
    messages: MessageState
    actions: list[Action]


class MessageRow(BaseModel):
    """One kept message: the household's (`in`) or FinBoy's (`out`), on WhatsApp or the web."""

    id: UUID
    at: datetime
    channel: Literal["whatsapp", "web"]
    direction: Literal["in", "out"]
    kind: str  # text, voice, photo, document, tap, command, buttons, list, voice_reply, template
    text: str | None
    transcript: str | None
    language: str | None
    choices: list[str]  # titles FinBoy offered, or the choice a tap made
    media: Literal["audio", "image"] | None  # a voice note or photo that can be opened
    media_bytes: int | None
    status: str | None  # FinBoy's sends: sent, delivered, read, failed, unknown
    outcome: str | None  # the household's messages: a fixed code when FinBoy couldn't help


class MessagePage(BaseModel):
    kept_from: datetime | None
    declined_at: datetime | None
    items: list[MessageRow]  # newest first
    next_before: str | None  # "<time>|<id>" of the oldest one shown, to pass back as `before`


class SignupCounts(BaseModel):
    enabled: bool
    open: bool
    agreed: int
    pending: int
    limit: int
    waitlist: int
    waitlist_languages: dict[str, int]
    oldest_waiting_since: datetime | None
    stale_pending: int


class Overview(BaseModel):
    billing_enabled: bool
    households: dict[str, int]
    signups: SignupCounts
    active: dict[str, int]
    plans: dict[str, int]
    paid_this_month: int
    received_this_month_minor: int
    open_payments: int
    usage_today: dict[str, int]
    deliveries_week: dict[str, int]
    imports_week: dict[str, int]
    # Household reports still marked New (docs/feedback-round/contract.md).
    feedback_new: int = 0


class SystemStatus(BaseModel):
    environment: str
    release: str | None
    database: Literal["connected", "unavailable"]
    schema_status: Literal["current", "behind", "unavailable"]
    schema_head: str
    flags: dict[str, bool]
    limits: dict[str, int]
    providers: dict[str, str]
    payu_environment: str
    active_imports: int | None
    open_payments: int | None


class AdminRow(BaseModel):
    id: UUID
    email: str
    active: bool
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime
    you: bool


class SessionRow(BaseModel):
    id: UUID
    device: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    current: bool


class AuditRow(BaseModel):
    id: UUID
    created_at: datetime
    action: str
    admin_email: str | None
    household_id: UUID | None
    short_id: str | None
    household_name: str | None
    detail: dict[str, str | int]


class AuditPage(BaseModel):
    items: list[AuditRow]
    total: int
    offset: int
    next_offset: int | None


class AdminSession(BaseModel):
    email: str
    must_change_password: bool


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class PasswordInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    current: str = Field(min_length=1, max_length=256)
    new: str = Field(min_length=1, max_length=256)


class NewAdmin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)


class CreatedAdmin(BaseModel):
    email: str
    temporary_password: str  # shown once; the new admin must change it at first sign-in


class EraseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: str = Field(min_length=8, max_length=8)  # the household's short ID, typed back


class PremiumInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    days: int = Field(ge=1, le=366)


class PayLink(BaseModel):
    url: str  # anyone holding it can pay for this household for 7 days


class Done(BaseModel):
    done: Literal[True] = True


# Household feedback (docs/feedback-round/contract.md): the list carries no words; the detail
# does, and only its route returns it.
class FeedbackRow(BaseModel):
    id: UUID
    household_id: UUID
    short_id: str
    household_name: str | None
    kind: Literal["problem", "idea", "other"]
    status: Literal["new", "planned", "done"]
    has_screenshot: bool
    created_at: datetime


class FeedbackPage(BaseModel):
    items: list[FeedbackRow]
    total: int
    offset: int
    next_offset: int | None
    new: int


class FeedbackDetail(FeedbackRow):
    message: str
    page: str
    status_changed_at: datetime | None
