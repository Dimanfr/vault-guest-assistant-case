"""Read the Markdown knowledge base: apartment files and the response rules."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["Section", "Apartment", "EscalationRule", "load_apartment", "load_rules"]


@dataclass
class Section:
    topic: str
    keywords: list[str]
    answers: dict[str, str]  # language code -> approved text


@dataclass
class Apartment:
    code: str
    name: str
    sections: list[Section] = field(default_factory=list)
    source: str = ""


@dataclass
class EscalationRule:
    category: str
    triggers: list[str]
    why: str


def _split_list(value: str) -> list[str]:
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def load_apartment(path: Path) -> Apartment:
    text = path.read_text(encoding="utf-8")
    title = re.search(r"^#\s+(\S+)\s+·\s+(.+)$", text, re.MULTILINE)
    if not title:
        raise ValueError(f"{path}: first heading must be '# <code> · <name>'")
    apartment = Apartment(code=title.group(1), name=title.group(2).strip(), source=text)

    current: Section | None = None
    for line in text.splitlines():
        heading = re.match(r"^##\s+(.+)$", line)
        if heading:
            current = Section(topic=heading.group(1).strip(), keywords=[], answers={})
            apartment.sections.append(current)
            continue
        if current is None:
            continue
        field_match = re.match(r"^(keywords|en|de):\s*(.+)$", line.strip())
        if not field_match:
            continue
        key, value = field_match.groups()
        if key == "keywords":
            current.keywords = _split_list(value)
        else:
            current.answers[key] = value.strip()

    for section in apartment.sections:
        if not section.keywords or not section.answers:
            raise ValueError(f"{path}: section '{section.topic}' needs keywords and an answer")
    return apartment


def load_rules(path: Path) -> tuple[list[EscalationRule], str]:
    """Return the escalation rules table and the full rules text."""
    text = path.read_text(encoding="utf-8")
    rules: list[EscalationRule] = []
    in_table = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_table = line.strip().lower() == "## escalate to a person"
            continue
        if not in_table or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 3 or cells[0].lower() == "category" or set(cells[0]) <= {"-"}:
            continue
        rules.append(EscalationRule(cells[0], _split_list(cells[1]), cells[2]))
    if not rules:
        raise ValueError(f"{path}: no rows under '## Escalate to a person'")
    return rules, text
