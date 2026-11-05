"""Everything the admin panel can show (docs/admin-round/contract.md): fixed codes, dates, counts.

These models are the boundary. None has a field for an amount of a household's records, a payee,
category, label, name, message, phone number, contact detail, hash or key, so no route can return
one. FinBoy's own payment records (₹299 sales) are the only money shown.
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


class HouseholdDetail(HouseholdRow):
    suspended_at: datetime | None
    deleted_at: datetime | None
    last_message_at: datetime | None
    last_record_at: datetime | None
    # Stored already masked by the sign-up round ("s***@***.com"); nothing is decrypted.
    google_email: str | None
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
    actions: list[Action]


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
