"""Decide for one guest message: prepare a draft from the Vault, or escalate.

Order of checks (offline, deterministic):
1. instruction-override attempt  -> escalate, no draft
2. escalation trigger from rules.md -> escalate with category and trigger
3. approved apartment section matches -> draft in the guest's language
4. nothing matches -> escalate ("no approved answer")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .vault import Apartment, EscalationRule

__all__ = ["Decision", "decide", "detect_injection", "detect_language", "find_triggers"]

# Guard rails stay in code on purpose: the operator edits knowledge and
# escalation words in the Vault, not the safety checks.
_INJECTION = [
    r"ignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|rules|messages)",
    r"disregard (all |any )?(the )?(previous|prior|above|earlier)",
    r"\byou are now\b",
    r"\bsystem prompt\b",
    r"\bdeveloper mode\b",
    r"\bact as (the )?(owner|admin|host|system)\b",
    r"ignoriere (alle )?(vorherigen |bisherigen )?(anweisungen|regeln)",
    r"\bdu bist (jetzt|ab sofort)\b",
]
_GERMAN_WORDS = {
    "hallo", "und", "ist", "gibt", "es", "einen", "eine", "wir", "ich", "der",
    "die", "das", "bitte", "danke", "mit", "dem", "wann", "wo", "können", "kann",
    "wie", "unsere", "unser", "ihr", "sie", "nicht",
}
_GREETING = {"en": "Hello!", "de": "Hallo!"}
_CLOSING = {"en": "Best regards, your host team", "de": "Viele Grüße, Ihr Gastgeber-Team"}


@dataclass
class Decision:
    kind: str  # "draft" or "escalate"
    language: str
    reasons: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    draft: str = ""


def _contains(text: str, phrase: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text) is not None


def detect_injection(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in _INJECTION)


def detect_language(text: str) -> str:
    words = re.findall(r"[a-zäöüß]+", text.lower())
    german = sum(word in _GERMAN_WORDS for word in words)
    return "de" if german >= 2 or re.search(r"[äöüß]", text.lower()) else "en"


def find_triggers(text: str, rules: list[EscalationRule]) -> list[str]:
    lowered = text.lower()
    found = []
    for rule in rules:
        hits = [t for t in rule.triggers if _contains(lowered, t)]
        if hits:
            found.append(f'{rule.category} ("{hits[0]}")')
    return found


def decide(text: str, apartment: Apartment, rules: list[EscalationRule]) -> Decision:
    language = detect_language(text)

    if detect_injection(text):
        return Decision("escalate", language, ["possible prompt injection"])

    triggers = find_triggers(text, rules)
    if triggers:
        return Decision("escalate", language, triggers)

    lowered = text.lower()
    scored = []
    for index, section in enumerate(apartment.sections):
        score = sum(_contains(lowered, keyword) for keyword in section.keywords)
        if score:
            scored.append((-score, index, section))
    if not scored:
        return Decision("escalate", language, ["no approved answer in the apartment file"])

    chosen = [section for _, _, section in sorted(scored)[:2]]
    body = " ".join(s.answers.get(language) or s.answers["en"] for s in chosen)
    draft = f"{_GREETING[language]} {body} {_CLOSING[language]}"
    return Decision("draft", language, topics=[s.topic for s in chosen], draft=draft)
