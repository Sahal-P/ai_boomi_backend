from uuid import UUID

from sqlalchemy.orm import Session


def merge_transactions(session: Session, *, user_id: UUID, keep_id: UUID, merge_id: UUID) -> None:
    raise NotImplementedError


def keep_separate(session: Session, *, user_id: UUID, transaction_id: UUID) -> None:
    raise NotImplementedError
