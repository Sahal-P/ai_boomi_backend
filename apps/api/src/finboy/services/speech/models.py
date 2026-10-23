from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel


class Transcript(BaseModel):
    transcript: str
    detected_language: Literal["en", "hi", "ml", "unknown"]


@dataclass(frozen=True)
class SynthesizedAudio:
    data: bytes = field(repr=False)
    media_type: Literal["audio/mpeg"] = "audio/mpeg"
