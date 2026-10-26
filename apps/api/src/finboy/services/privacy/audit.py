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
        "review.completed",
        "review.undone",
        "obligation.corrected",
        "task.evidence_opened",
        "task.overview_understood",
        "task.overview_explanation_opened",
        "task.review_completed",
        "data.exported",
        "pilot.enrolled",
        "pilot.erased",
    }
)
METADATA = {
    "mode": {"gmail", "eml_upload", "demo_mailbox", "whatsapp_image", "whatsapp_voice"},
    "result": {"success", "failure"},
}


def audit(
    session: Session,
    event: str,
    subject_type: str,
    subject_id: UUID,
    *,
    user_id: UUID | None = None,
    **metadata: str,
) -> None:
    if event not in EVENTS or subject_type not in {
        "connection",
        "import",
        "user",
        "transaction",
        "commitment",
    }:
        raise ValueError("Unsupported audit event")
    clean = {
        key: value for key, value in metadata.items() if key in METADATA and value in METADATA[key]
    }
    session.add(
        AuditEvent(
            user_id=user_id or LOCAL_USER_ID,
            event_type=event,
            subject_type=subject_type,
            subject_id=subject_id,
            event_metadata=clean,
        )
    )
