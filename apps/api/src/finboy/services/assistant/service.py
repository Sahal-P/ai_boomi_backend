"""Agent 3 owns implementation after bootstrap. No fabricated successful answers."""

from uuid import UUID

from sqlalchemy.orm import Session

from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.core.languages import DisplayStyle
from finboy.services.assistant.models import AssistantAnswer


def answer_question(
    session: Session, *, user_id: UUID, text: str, display_style: DisplayStyle, settings: Settings
) -> AssistantAnswer:
    raise ProviderUnavailable("assistant_unavailable")
