"""What leaves the server about a conversation (F10).

Before a conversation goes to an outside decisions service, the details that
identify people come out: emails, links, long numbers (phones, document and
card numbers) and the names of the customer and the agents. What is left is
enough to tell what the person wants and how they feel.
"""

from __future__ import annotations

import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
# Seven or more digits, with the separators people type: +598 99 123 456,
# 4.567.890-1, 1234 5678 9012 3456. Shorter numbers (prices, hours, dates)
# stay: they matter to the question and identify nobody.
_LONG_NUMBER = re.compile(r"\+?\d(?:[\s().-]*\d){6,}")


def anonymize(text: str, names: list[str] | tuple[str, ...] = ()) -> str:
    out = _EMAIL.sub("[correo]", text)
    out = _URL.sub("[enlace]", out)
    out = _LONG_NUMBER.sub("[número]", out)
    for name in names:
        for part in (name or "").split():
            part = part.strip(".,;:()[]")
            if len(part) >= 3 and not part.isdigit():
                out = re.sub(rf"(?<!\w){re.escape(part)}(?!\w)", "[nombre]", out, flags=re.IGNORECASE)
    return out


__all__ = ["anonymize"]
