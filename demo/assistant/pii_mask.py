"""Mask guest contact data in a message before people or models see it.

Two layers:
1. Known values from the booking (guest name, phone, e-mail) are replaced
   wherever they appear, including phone numbers written in another format.
2. Patterns catch contact data the booking does not know about: any e-mail
   address, phone-like numbers and long digit runs.

Dates and short references (e.g. a booking code) are left alone.

This is a pattern-based safeguard, not anonymisation. It misses misspelt or
shortened names, names of other people, addresses and free-form identifiers.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

__all__ = ["MaskResult", "mask"]

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# A phone-like run: starts with +, 00 or 0, then digits with common separators.
_PHONE = re.compile(r"(?<![\w+(])\(?(?:\+|0)[\d][\d\s()/.-]{6,}\d")
_LONG_NUMBER = re.compile(r"(?<!\w)\d{9,}(?!\w)")
_DATE = re.compile(r"\d{1,2}\.\d{1,2}\.(?:\d{2}|\d{4})|\d{4}-\d{2}-\d{2}")
_MIN_PHONE_DIGITS = 8
_TAIL = 7


@dataclass
class MaskResult:
    text: str
    counts: Counter = field(default_factory=Counter)

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def mask(text: str, known: dict | None = None) -> MaskResult:
    """Return the masked text and how many values of each kind were masked.

    ``known`` may contain ``guest_name``, ``phone`` and ``email`` from the
    booking. Replacements are ``[name]``, ``[phone]``, ``[email]`` and
    ``[number]``.
    """
    known = known or {}
    counts: Counter = Counter()

    value_text = text

    def sub(pattern, label: str, flags: int = 0) -> None:
        nonlocal value_text
        value_text, n = re.subn(pattern, label, value_text, flags=flags)
        counts[label.strip("[]")] += n

    # 1. E-mail addresses: the known one first, then any other.
    email = (known.get("email") or "").strip()
    if email:
        sub(re.escape(email), "[email]", re.IGNORECASE)
    sub(_EMAIL, "[email]")

    # 2. Phone numbers: anything phone-like, or matching the known number's tail.
    known_tail = _digits(known.get("phone") or "")[-_TAIL:]

    def phone_repl(match: re.Match) -> str:
        candidate = match.group(0)
        if _DATE.fullmatch(candidate.strip()):
            return candidate
        digits = _digits(candidate)
        is_known = len(known_tail) == _TAIL and digits.endswith(known_tail)
        if is_known or len(digits) >= _MIN_PHONE_DIGITS:
            counts["phone"] += 1
            return "[phone]"
        return candidate

    value_text = _PHONE.sub(phone_repl, value_text)

    # 3. Long digit runs (IDs, account numbers) that were not phone-like.
    def number_repl(match: re.Match) -> str:
        if known_tail and match.group(0).endswith(known_tail):
            counts["phone"] += 1
            return "[phone]"
        counts["number"] += 1
        return "[number]"

    value_text = _LONG_NUMBER.sub(number_repl, value_text)

    # 4. Names: the full name in any case, then each part of 3+ letters as a
    #    whole word with its original capitalisation.
    name = " ".join((known.get("guest_name") or "").split())
    if name:
        full = r"(?<!\w)" + r"\s+".join(map(re.escape, name.split())) + r"(?!\w)"
        sub(full, "[name]", re.IGNORECASE)
        for part in name.split():
            if len(part) >= 3:
                sub(r"(?<!\w)" + re.escape(part) + r"(?!\w)", "[name]")

    counts = Counter({k: v for k, v in counts.items() if v})
    return MaskResult(text=value_text, counts=counts)
