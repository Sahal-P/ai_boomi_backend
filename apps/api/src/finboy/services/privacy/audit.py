from uuid import UUID

from sqlalchemy.orm import Session

from finboy.core.config import LOCAL_USER_ID
from finboy.db.models.mail import AuditEvent

EVENTS = frozenset(
    {
        "gmail.connected",
        "gmail.sync_requested",
        "gmail.paused",
        "gmail.resumed",
        "gmail.revoked",
        "gmail.revoke_failed",
        "gmail.reconnect_required",
        "import.started",
        "import.completed",
        "import.failed",
        "data.deleted",
    }
)
METADATA = {"mode": {"gmail", "eml_upload", "demo_mailbox"}, "result": {"success", "failure"}}


def audit(
    session: Session, event: str, subject_type: str, subject_id: UUID, **metadata: str
) -> None:
    if event not in EVENTS or subject_type not in {"connection", "import", "user"}:
        raise ValueError("Unsupported audit event")
    clean = {
        key: value for key, value in metadata.items() if key in METADATA and value in METADATA[key]
    }
    session.add(
        AuditEvent(
            user_id=LOCAL_USER_ID,
            event_type=event,
            subject_type=subject_type,
            subject_id=subject_id,
            event_metadata=clean,
        )
    )
