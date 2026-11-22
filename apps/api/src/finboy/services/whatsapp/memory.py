"""WhatsApp commands for the advisor's memory and chats (docs/advisor-round/contract.md).

"memory off", "memory on", "forget everything" and "clear chat history", in English, Hindi and
Malayalam, act without a model so they always work. Everyday requests ("forget the bike") go to
the advisor, which changes single memories itself.
"""

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from finboy.core.errors import AccessError
from finboy.services.advisor import history, memory
from finboy.services.conversations import store

if TYPE_CHECKING:
    from finboy.services.whatsapp.pilot import Conversation

END = r"\s*[.!।]*\s*"
OFF = re.compile(
    r"\s*(?:memory\s+off|turn\s+off\s+(?:your\s+)?memory|stop\s+remembering|मेमोरी\s+बंद(?:\s+करो)?"
    r"|याद\s+रखना\s+बंद(?:\s+करो)?|memory\s+band(?:\s+karo)?|മെമ്മറി\s+ഓഫ്(?:\s+ചെയ്യൂ)?)" + END,
    re.IGNORECASE,
)
ON = re.compile(
    r"\s*(?:memory\s+on|turn\s+on\s+(?:your\s+)?memory|मेमोरी\s+चालू(?:\s+करो)?"
    r"|याद\s+रखना\s+चालू(?:\s+करो)?|memory\s+chalu(?:\s+karo)?|മെമ്മറി\s+ഓൺ(?:\s+ചെയ്യൂ)?)" + END,
    re.IGNORECASE,
)
FORGET_ALL = re.compile(
    r"\s*(?:forget\s+everything(?:\s+about\s+me)?|delete\s+(?:all\s+)?(?:my\s+)?memor(?:y|ies)"
    r"|सब\s+(?:कुछ\s+)?भूल\s+जाओ|sab\s+(?:kuch\s+)?bhool\s+jao|എല്ലാം\s+മറക്കൂ|ellam\s+marakku)" + END,
    re.IGNORECASE,
)
CLEAR_CHATS = re.compile(
    r"\s*(?:clear\s+(?:my\s+)?(?:chat\s+)?history|delete\s+(?:my\s+)?chats?"
    r"|चैट\s+(?:हिस्ट्री\s+)?मिटाओ|chat\s+history\s+(?:delete|mitao)|ചാറ്റ്\s+മായ്ക്കൂ)" + END,
    re.IGNORECASE,
)


def _switch(value: bool) -> Callable[[Conversation], str | None]:
    def handle(conversation: Conversation) -> str | None:
        memory.set_enabled(conversation.session, conversation.binding.user_id, value)
        conversation.session.commit()
        words = conversation.words
        return conversation.done(conversation.send(words.MEMORY_ON if value else words.MEMORY_OFF))

    return handle


def _forget_all(conversation: Conversation) -> str | None:
    memory.forget_all(conversation.session, conversation.binding.user_id)
    conversation.session.commit()
    return conversation.done(conversation.send(conversation.words.MEMORY_FORGOTTEN))


def _clear_chats(conversation: Conversation) -> str | None:
    """The advisor's chats and, for a household that agreed, its kept messages and their files
    (docs/conversation-round/contract.md)."""
    session, user_id = conversation.session, conversation.binding.user_id
    try:
        store.remove(session, conversation.settings, user_id)
    except AccessError:
        session.rollback()  # R2 can't be reached: nothing is cleared, so asking again works
        sent = conversation.send(conversation.words.UNAVAILABLE)
        return conversation.done(sent, "provider_unavailable")
    history.delete_all(session, user_id)
    session.commit()
    return conversation.done(conversation.send(conversation.words.CHATS_CLEARED))


def clearing(text: str) -> Callable[[Conversation], str | None] | None:
    """Only "clear chat history", which works whenever messages are kept, advisor on or off."""
    return _clear_chats if CLEAR_CHATS.fullmatch(text) else None


def command(text: str) -> Callable[[Conversation], str | None] | None:
    """The memory or chat command a whole message gives, if it is one."""
    for pattern, handler in (
        (OFF, _switch(False)),
        (ON, _switch(True)),
        (FORGET_ALL, _forget_all),
        (CLEAR_CHATS, _clear_chats),
    ):
        if pattern.fullmatch(text):
            return handler
    return None
