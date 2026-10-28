"""WhatsApp side of signing in to the FinBoy website, and the sign-up waitlist.

docs/signup-round/contract.md. A login code sent from a person's own WhatsApp gets a card naming
the browser that asked; only a tap on that card confirms. Codes, numbers and message text are
never stored: login requests keep HMACs, the waitlist keeps an HMAC and a Fernet copy.
"""

import re
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from finboy.core.config import LOCAL_USER_ID
from finboy.db.models.accounts import LoginRequest, SignupWaitlist
from finboy.db.models.core import User
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppPrompt
from finboy.services.accounts import households, login
from finboy.services.mail.security import encrypt
from finboy.services.whatsapp import prompts
from finboy.services.whatsapp.pilot import Conversation

JOIN = re.compile(r"^\s*(?:join|जॉइन|जोड़ो|जोड़िए)\s*[.!]?\s*$", re.IGNORECASE)


def _pending(user: User | None) -> bool:
    """Joined by itself but has not agreed yet."""
    return user is not None and user.joined_via is not None and user.consented_at is None


def handle_code(conversation: Conversation, code: str) -> str | None:
    """A login code arrived: answer with a card naming the browser, or say why not."""
    session, settings, binding = conversation.session, conversation.settings, conversation.binding
    words = conversation.words
    request = login.for_code(session, settings, code)
    user = session.get(User, binding.user_id)
    if request is None or user is None or user.deleted_at is not None:
        session.rollback()
        return conversation.done(conversation.send(words.LOGIN_EXPIRED), "login_expired")
    if user.pilot and user.id != LOCAL_USER_ID:
        session.rollback()
        return conversation.done(conversation.send(words.WEB_NOT_PILOT), "web_not_available")
    device = request.device or "a browser"
    pending = _pending(user)
    if request.purpose == "link":
        if user.id == request.user_id:
            login.confirm(request, user_id=user.id, binding_id=binding.id)
            session.commit()
            return conversation.done(conversation.send(words.LINKED))
        if not pending:
            # Two households are never merged, so a number in use elsewhere stays there.
            login.decline(request)
            session.commit()
            return conversation.done(conversation.send(words.ALREADY_LINKED))
        purpose, text, yes = "link", words.link_card(device), words.LINK_YES
    elif pending and not households.signup_open(session, settings):
        login.decline(request)
        session.commit()
        return conversation.done(conversation.send(words.FULL), "signup_full")
    elif pending:
        purpose, text, yes = "web_login", words.signup_card(device), words.CREATE_YES
    else:
        purpose, text, yes = "web_login", words.sign_in_card(device), words.SIGN_IN_YES
    prompt = prompts.open_prompt(session, binding, purpose, login_request_id=request.id)
    session.commit()
    sent = conversation.send(
        text, [(prompts.button(prompt, "yes"), yes), (prompts.button(prompt, "no"), words.NO)]
    )
    return conversation.done(sent)


def _move_binding(session: Session, binding: WhatsAppBinding, user: User, target: User) -> None:
    """Linking: a number that never agreed elsewhere joins the signed-in household."""
    binding.user_id = target.id
    binding.consented_at = binding.consented_at or datetime.now(UTC)
    session.flush()
    households.discard_pending(session, user.id)


def tap(conversation: Conversation, prompt: WhatsAppPrompt, choice: str) -> str | None:
    """Yes or No on a sign-in or link card."""
    session, settings, binding = conversation.session, conversation.settings, conversation.binding
    words = conversation.words
    request = (
        session.get(LoginRequest, prompt.login_request_id, with_for_update=True)
        if prompt.login_request_id
        else None
    )
    prompts.answer(prompt)
    if request is None or login.state_of(request) != "pending":
        session.commit()
        return conversation.done(conversation.send(words.LOGIN_EXPIRED), "login_expired")
    user = session.get(User, binding.user_id, with_for_update=True)
    if user is None or user.deleted_at is not None:
        session.commit()
        return conversation.done(conversation.send(words.LOGIN_EXPIRED), "login_expired")
    pending = _pending(user)
    if choice != "yes":
        login.decline(request)
        session.commit()
        sent = conversation.send(words.LOGIN_DECLINED)
        if pending and prompt.purpose == "web_login":
            households.discard_pending(session, user.id)
            session.commit()
        return conversation.done(sent)
    if prompt.purpose == "link":
        target = session.get(User, request.user_id, with_for_update=True)
        if target is None or target.deleted_at is not None or not (pending or user.id == target.id):
            login.decline(request)
            session.commit()
            return conversation.done(conversation.send(words.ALREADY_LINKED))
        if user.id != target.id:
            _move_binding(session, binding, user, target)
        login.confirm(request, user_id=target.id, binding_id=binding.id)
        session.commit()
        return conversation.done(conversation.send(words.LINKED))
    if pending:
        if not households.agree(session, settings, user):
            login.decline(request)
            session.commit()
            return conversation.done(conversation.send(words.FULL), "signup_full")
        binding.consented_at = binding.consented_at or datetime.now(UTC)
    login.confirm(request, user_id=user.id, binding_id=binding.id)
    session.commit()
    return conversation.done(conversation.send(words.SIGNED_IN))


def join(conversation: Conversation) -> str | None:
    """JOIN while FinBoy is full: keep a place in line and nothing else."""
    session, settings, binding = conversation.session, conversation.settings, conversation.binding
    sealed = binding.encrypted_sender
    if sealed is None and settings.token_encryption_key is not None:
        sealed = encrypt(
            settings.token_encryption_key.get_secret_value(), conversation.question.sender
        )
    if sealed is None:
        session.rollback()
        return conversation.done(conversation.send(conversation.words.UNAVAILABLE))
    session.execute(
        insert(SignupWaitlist)
        .values(
            id=uuid4(),
            sender_hash=binding.sender_hash,
            encrypted_sender=sealed,
            language=conversation.language,
        )
        .on_conflict_do_nothing(index_elements=[SignupWaitlist.sender_hash])
    )
    session.commit()
    sent = conversation.send(conversation.words.JOINED)
    households.discard_pending(session, binding.user_id)
    session.commit()
    return conversation.done(sent)
