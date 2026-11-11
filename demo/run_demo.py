"""Run the synthetic demo over messages.json and print what the operator's team would see.

    python3 run_demo.py                 # offline, deterministic, no key needed
    python3 run_demo.py --llm           # drafts by a Claude model (pip install anthropic)
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from assistant.decide import decide  # noqa: E402
from assistant.pii_mask import mask  # noqa: E402
from assistant.vault import load_apartment, load_rules  # noqa: E402

WIDTH = 92


def show(label: str, text: str) -> None:
    lines = textwrap.wrap(text, WIDTH - 13) or [""]
    print(f"    {label:<8} {lines[0]}")
    for line in lines[1:]:
        print(f"    {'':<8} {line}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--messages", type=Path, default=HERE / "messages.json")
    parser.add_argument("--vault", type=Path, default=HERE / "vault")
    parser.add_argument("--llm", action="store_true", help="use a Claude model for drafts")
    parser.add_argument("--model", default=None, help="model id for --llm")
    args = parser.parse_args(argv)

    rules, rules_text = load_rules(args.vault / "rules.md")
    apartments = {}
    for path in sorted((args.vault / "apartments").glob("*.md")):
        apartment = load_apartment(path)
        apartments[apartment.code] = apartment

    messages = json.loads(args.messages.read_text(encoding="utf-8"))
    summary = {"draft": 0, "escalate": 0}
    for message in messages:
        apartment = apartments[message["apartment"]]
        booking = message.get("booking", {})
        if args.llm:
            from assistant.llm import DEFAULT_MODEL, decide_with_model

            decision = decide_with_model(
                message["text"], booking, apartment, rules, rules_text,
                model=args.model or DEFAULT_MODEL,
            )
        else:
            decision = decide(message["text"], apartment, rules)
        summary[decision.kind] += 1

        masked = mask(message["text"], booking)
        print(f"#{message['id']}  {apartment.code} {apartment.name}  "
              f"[{decision.language.upper()}]  -> {decision.kind.upper()}")
        show("guest", masked.text)
        if masked.total:
            detail = ", ".join(f"{k} {v}" for k, v in sorted(masked.counts.items()))
            show("masked", f"{masked.total} value(s): {detail}")
        if decision.kind == "draft":
            show("topics", ", ".join(decision.topics))
            show("draft", decision.draft)
        else:
            show("reason", "; ".join(decision.reasons))
        print()

    print(f"{len(messages)} messages: {summary['draft']} drafts, "
          f"{summary['escalate']} escalations. Nothing was sent to any guest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
