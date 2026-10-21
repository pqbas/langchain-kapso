"""Split long replies into WhatsApp-sized messages."""

from __future__ import annotations

import re

WHATSAPP_TEXT_LIMIT = 4096
"""Maximum length of a WhatsApp text message body."""

# Places to cut, from the most natural to the least: paragraph, line, sentence, word
_BREAKS = (re.compile(r"\n\s*\n"), re.compile(r"\n"), re.compile(r"(?<=[.!?…])\s+"), re.compile(r"\s+"))


def _cut_point(text: str, limit: int) -> int:
    """Index where the first chunk of ``text`` should end, at most ``limit``."""
    window = text[: limit + 1]
    for pattern in _BREAKS:
        # Last break inside the window, as long as the chunk is not too short
        cuts = [m.start() for m in pattern.finditer(window) if m.start() <= limit]
        if cuts and cuts[-1] >= limit // 2:
            return cuts[-1]
    return limit


def split_message(text: str, limit: int = WHATSAPP_TEXT_LIMIT) -> list[str]:
    """Split ``text`` into chunks of at most ``limit`` characters.

    Cuts between paragraphs when possible, then between lines, sentences and
    words, and only cuts inside a word when there is no other option. Short
    texts come back unchanged as a single chunk; empty texts give no chunks.
    """
    if limit < 1:
        raise ValueError("limit must be positive")
    text = text.strip()
    chunks: list[str] = []
    while len(text) > limit:
        cut = _cut_point(text, limit)
        chunks.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    if text:
        chunks.append(text)
    return chunks
