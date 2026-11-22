"""Email content passed to the Resend transport."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Message:
    subject: str
    text: str = field(repr=False)
    html: str = field(repr=False)


FEEDBACK_KINDS = {"problem": "a problem", "idea": "an idea", "other": "feedback"}


def feedback_received(*, kind: str, link: str | None, screenshot: bool) -> Message:
    """The owner's note about a new report: its type and where to read it, never its words, so
    what a household wrote stays in FinBoy (docs/feedback-round/contract.md)."""
    what = FEEDBACK_KINDS.get(kind, "feedback")
    extra = " It has a screenshot." if screenshot else ""
    where = f"Read it in the admin panel: {link}" if link else "Read it in the admin panel."
    text = f"A household sent {what} from the FinBoy app.{extra}\n\n{where}\n"
    anchor = f'<a href="{link}">Open it in the admin panel</a>' if link else "the admin panel"
    html = f"<p>A household sent {what} from the FinBoy app.{extra}</p><p>Read it in {anchor}.</p>"
    return Message(subject=f"FinBoy feedback: {what}", text=text, html=html)
