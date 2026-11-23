"""Where a sign-up came from (docs/ad-journey-round/contract.md).

A page with FinBoy's WhatsApp button records a visit under a random ref it made itself, then the
tap, and the first message of the new household it led to claims the visit: the ref rides at the
end of the prefilled greeting, " (ref K7Q2MX)", and is removed before anything reads the message.
Nothing here identifies a person: the link's campaign tags, the page and its language, coarse
browser and phone classes, and times. The User-Agent is read once and never kept or logged.
"""

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import median
from uuid import UUID, uuid4

from sqlalchemy import Select, Subquery, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from finboy.db.models.core import User
from finboy.db.models.ledger import Transaction
from finboy.db.models.visits import LANDING_PATTERN, REF_PATTERN, TAG_PATTERN, SignupVisit
from finboy.db.models.whatsapp import WhatsAppBinding

REF = re.compile(REF_PATTERN)
TAG = re.compile(TAG_PATTERN)
LANDING = re.compile(LANDING_PATTERN)
# Only a trailing ref, as FinBoy's own links write it, is read; one inside a sentence stays text.
SUFFIX = re.compile(
    r"^(?P<text>.*?)\s*\(\s*ref\s+(?P<ref>[2-9A-HJ-NP-Z]{6})\s*\)\s*$", re.IGNORECASE | re.DOTALL
)
LANGUAGES = {"en", "hi", "ml"}
KEEP = timedelta(days=90)  # visits that led to no sign-up
TIDY_BATCH = 500
MAX_ROWS = 50_000  # a funnel reads at most this many visits


@dataclass(frozen=True)
class Tags:
    source: str | None = None
    medium: str | None = None
    campaign: str | None = None
    content: str | None = None


def clean_tag(value: str | None) -> str | None:
    """A utm_* value as FinBoy keeps it: lowercase letters, digits and . _ -, at most 64."""
    if value is None:
        return None
    tag = value.strip().lower()
    return tag if TAG.fullmatch(tag) else None


def clean_tags(
    source: str | None,
    medium: str | None,
    campaign: str | None,
    content: str | None,
    *,
    meta_click: bool = False,
) -> Tags:
    """Invalid values are dropped, never rejected. A Meta click without tags (the page saw an
    `fbclid`, which it never sends) counts as source "meta", medium "click"."""
    tags = Tags(clean_tag(source), clean_tag(medium), clean_tag(campaign), clean_tag(content))
    if tags.source is None and meta_click:
        return Tags("meta", tags.medium or "click", tags.campaign, tags.content)
    return tags


def classify(user_agent: str) -> tuple[str, str]:
    """(browser, platform) classes from a User-Agent, which is not kept."""
    agent = user_agent[:512]
    if "Instagram" in agent:
        browser = "instagram"
    elif any(token in agent for token in ("FBAN/", "FBAV/", "FB_IAB")):
        browser = "facebook"
    else:
        browser = "other"
    if "Android" in agent:
        platform = "android"
    elif any(token in agent for token in ("iPhone", "iPad", "iPod")):
        platform = "ios"
    elif any(token in agent for token in ("Windows", "Macintosh", "X11", "CrOS")):
        platform = "desktop"
    else:
        platform = "other"
    return browser, platform


def split_ref(text: str) -> tuple[str, str | None]:
    """A message without FinBoy's trailing "(ref XXXXXX)", and that ref. A message that is only
    the ref was a greeting with its words deleted, so it reads as "hi"."""
    match = SUFFIX.match(text)
    if match is None:
        return text, None
    return match["text"].strip() or "hi", match["ref"].upper()


def record(
    session: Session,
    *,
    ref: str,
    tags: Tags,
    landing: str,
    language: str | None,
    user_agent: str,
) -> bool:
    """A page opened. False for a ref already seen (a reload in the same tab) or bad input."""
    if not REF.fullmatch(ref) or not LANDING.fullmatch(landing):
        return False
    browser, platform = classify(user_agent)
    created = session.scalar(
        insert(SignupVisit)
        .values(
            id=uuid4(),
            ref=ref,
            source=tags.source,
            medium=tags.medium,
            campaign=tags.campaign,
            content=tags.content,
            landing=landing,
            language=language if language in LANGUAGES else None,
            browser=browser,
            platform=platform,
        )
        .on_conflict_do_nothing(index_elements=[SignupVisit.ref])
        .returning(SignupVisit.id)
    )
    return created is not None


def tap(session: Session, ref: str | None) -> bool:
    """The WhatsApp button was tapped, or sign-in started; only the first time counts."""
    if ref is None or not REF.fullmatch(ref):
        return False
    result = session.execute(
        update(SignupVisit)
        .where(SignupVisit.ref == ref, SignupVisit.tapped_at.is_(None))
        .values(tapped_at=datetime.now(UTC))
    )
    return bool(result.rowcount)


def claim(session: Session, ref: str | None, user_id: UUID) -> bool:
    """A new household's first message carried this ref. A visit is claimed once."""
    if ref is None or not REF.fullmatch(ref):
        return False
    result = session.execute(
        update(SignupVisit)
        .where(
            SignupVisit.ref == ref,
            SignupVisit.user_id.is_(None),
            SignupVisit.joined_at.is_(None),
        )
        .values(user_id=user_id, joined_at=datetime.now(UTC))
    )
    return bool(result.rowcount)


def unlink(session: Session, user_id: UUID) -> int:
    """Erasure: the household's visits stay only as anonymous counts."""
    result = session.execute(
        update(SignupVisit).where(SignupVisit.user_id == user_id).values(user_id=None)
    )
    return result.rowcount or 0


def tidy(session: Session) -> int:
    """Forget visits that led to no sign-up after 90 days; bounded per call."""
    stale = (
        select(SignupVisit.id)
        .where(
            SignupVisit.joined_at.is_(None),
            SignupVisit.created_at < datetime.now(UTC) - KEEP,
        )
        .limit(TIDY_BATCH)
    )
    result = session.execute(delete(SignupVisit).where(SignupVisit.id.in_(stale)))
    return result.rowcount or 0


@dataclass(frozen=True)
class Step:
    """One visit's journey, or one sign-up that came with no visit (opened is None)."""

    source: str | None
    medium: str | None
    campaign: str | None
    opened: datetime | None
    tapped: datetime | None
    joined: datetime | None
    agreed: datetime | None
    first_record: datetime | None


@dataclass(frozen=True)
class Funnel:
    source: str | None  # None with `direct`: sign-ups that came with no visit
    medium: str | None  # Instagram tags its own bio links ig/social; our ads say paid_social
    campaign: str | None
    direct: bool
    opened: int
    tapped: int
    signed_up: int
    agreed: int
    first_record: int
    minutes_to_tap: float | None
    minutes_to_sign_up: float | None
    minutes_to_record: float | None


def _minutes(pairs: list[tuple[datetime | None, datetime | None]]) -> float | None:
    gaps = [(end - start).total_seconds() / 60 for start, end in pairs if start and end]
    gaps = [gap for gap in gaps if gap >= 0]
    return round(median(gaps), 1) if gaps else None


def summarize(steps: list[Step]) -> list[Funnel]:
    """Counts and median minutes per (source, medium, campaign); direct sign-ups last."""
    groups: dict[tuple[bool, str | None, str | None, str | None], list[Step]] = defaultdict(list)
    for step in steps:
        groups[(step.opened is None, step.source, step.medium, step.campaign)].append(step)
    rows = []
    for (direct, source, medium, campaign), items in groups.items():
        rows.append(
            Funnel(
                source=source,
                medium=medium,
                campaign=campaign,
                direct=direct,
                opened=sum(1 for item in items if item.opened),
                # Sending the greeting means the button was tapped, even if its ping was lost.
                tapped=sum(1 for item in items if item.tapped or (item.opened and item.joined)),
                signed_up=sum(1 for item in items if item.joined),
                agreed=sum(1 for item in items if item.joined and item.agreed),
                first_record=sum(1 for item in items if item.joined and item.first_record),
                minutes_to_tap=_minutes([(item.opened, item.tapped) for item in items]),
                minutes_to_sign_up=_minutes([(item.tapped, item.joined) for item in items]),
                minutes_to_record=_minutes([(item.joined, item.first_record) for item in items]),
            )
        )
    return sorted(rows, key=lambda row: (row.direct, -row.opened, -row.signed_up))


def first_records(user_ids: Select) -> Subquery:
    """Each listed household's earliest still-confirmed record."""
    return (
        select(Transaction.user_id, func.min(Transaction.created_at).label("at"))
        .where(
            Transaction.status == "confirmed",
            Transaction.dataset == "household",
            Transaction.user_id.in_(user_ids),
        )
        .group_by(Transaction.user_id)
        .subquery()
    )


def funnel(session: Session, since: datetime) -> list[Funnel]:
    """Visits since `since`, and self-serve sign-ups since then that came with no visit."""
    claimed = select(SignupVisit.user_id).where(SignupVisit.user_id.is_not(None))
    visited = select(SignupVisit.user_id).where(
        SignupVisit.created_at >= since, SignupVisit.user_id.is_not(None)
    )
    firsts = first_records(visited)
    steps = [
        Step(*row)
        for row in session.execute(
            select(
                SignupVisit.source,
                SignupVisit.medium,
                SignupVisit.campaign,
                SignupVisit.created_at,
                SignupVisit.tapped_at,
                SignupVisit.joined_at,
                User.consented_at,
                firsts.c.at,
            )
            .outerjoin(User, User.id == SignupVisit.user_id)
            .outerjoin(firsts, firsts.c.user_id == SignupVisit.user_id)
            .where(SignupVisit.created_at >= since)
            .order_by(SignupVisit.created_at.desc())
            .limit(MAX_ROWS)
        ).all()
    ]
    direct_users = select(User.id).where(
        User.joined_via.is_not(None), User.created_at >= since, User.id.not_in(claimed)
    )
    direct_firsts = first_records(direct_users)
    steps += [
        Step(None, None, None, None, None, created, agreed, first)
        for created, agreed, first in session.execute(
            select(User.created_at, User.consented_at, direct_firsts.c.at)
            .outerjoin(direct_firsts, direct_firsts.c.user_id == User.id)
            .where(User.id.in_(direct_users))
            .limit(MAX_ROWS)
        ).all()
    ]
    return summarize(steps)


@dataclass(frozen=True)
class Journey:
    source: str | None
    medium: str | None
    campaign: str | None
    content: str | None
    landing: str | None
    browser: str | None
    platform: str | None
    opened: datetime | None
    tapped: datetime | None
    first_message: datetime | None
    agreed: datetime | None
    whatsapp_linked: datetime | None
    first_record: datetime | None


def journey(session: Session, user: User) -> Journey:
    """One household's way in: its visit (if one was claimed) and the times after it."""
    visit = session.scalar(
        select(SignupVisit)
        .where(SignupVisit.user_id == user.id)
        .order_by(SignupVisit.joined_at)
        .limit(1)
    )
    linked = session.scalar(
        select(func.min(WhatsAppBinding.created_at)).where(WhatsAppBinding.user_id == user.id)
    )
    first = session.scalar(
        select(func.min(Transaction.created_at)).where(
            Transaction.user_id == user.id,
            Transaction.status == "confirmed",
            Transaction.dataset == "household",
        )
    )
    return Journey(
        source=visit.source if visit else None,
        medium=visit.medium if visit else None,
        campaign=visit.campaign if visit else None,
        content=visit.content if visit else None,
        landing=visit.landing if visit else None,
        browser=visit.browser if visit else None,
        platform=visit.platform if visit else None,
        opened=visit.created_at if visit else None,
        tapped=visit.tapped_at if visit else None,
        first_message=visit.joined_at if visit else user.created_at,
        agreed=user.consented_at,
        whatsapp_linked=linked,
        first_record=first,
    )
