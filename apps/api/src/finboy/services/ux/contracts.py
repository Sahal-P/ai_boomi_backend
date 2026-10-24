"""Concrete additive response schemas consumed by the Product owner."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from finboy.services.money.engine import CommitmentView, MoneySummary, TransactionView
from finboy.services.money.models import TransactionSource
from finboy.services.ux.imports import ImportView


class DemoView(BaseModel):
    dataset: Literal["demo"]
    read_only: Literal[True]
    as_of: str
    summary: MoneySummary
    transactions: list[TransactionView]
    commitments: list[CommitmentView]


class ObligationList(BaseModel):
    items: list[CommitmentView]
    data_version: str


class ObligationDetail(BaseModel):
    commitment: CommitmentView
    sources: list[TransactionSource]
    version: str


class ImportPage(BaseModel):
    items: list[ImportView]
    total: int
    next_offset: int | None


class ImportStarted(BaseModel):
    import_run_id: UUID


class ImportIssue(BaseModel):
    id: UUID
    source_id: UUID
    source_mode: Literal["gmail", "eml_upload", "demo_mailbox"]
    reason: Literal["extraction_failed", "no_supported_events", "message_unavailable"]
    retryable: bool
    retry_strategy: Literal["refetch_gmail", "select_original_files", "none"]
    attempts: int


class IssuePage(BaseModel):
    items: list[ImportIssue]
    total: int
    next_offset: int | None


class DeletionPreview(BaseModel):
    version: str
    connection_id: UUID | None
    source_count: int
    event_count: int
    removed_transaction_count: int
    retained_shared_transaction_count: int
    removed_obligation_count: int
    retained_shared_obligation_count: int
    first_received_at: datetime | None
    last_received_at: datetime | None
    backup_retention_days: Literal[7]


class IsolationInventory(BaseModel):
    data_version: str
    demo_only_transactions: int
    mixed_transactions: int
    demo_only_obligations: int
    quarantined_obligations: int


class TaskResult(BaseModel):
    status: Literal["ok"]


class DeleteResult(TaskResult):
    data_version: str
