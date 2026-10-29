"""Email content passed to the Resend transport."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Message:
    subject: str
    text: str = field(repr=False)
    html: str = field(repr=False)
