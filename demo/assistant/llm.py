"""Optional: let a Claude model write the draft instead of the offline matcher.

Requires ``pip install anthropic`` and credentials (e.g. ANTHROPIC_API_KEY).
The model can only make the result more careful, never less:
- the same deterministic checks as offline run first (instruction-override
  attempt, escalation triggers from rules.md, no approved answer); if they
  escalate, the model is not called and cannot change that;
- the model sees the masked message, never the guest's contact data;
- a draft is accepted only from a normally finished reply (stop_reason
  "end_turn") with valid JSON and no contact data in it;
- the model's reason is a code from a fixed list; free text from the
  model is never shown as a reason (it could carry personal data that
  no pattern recognises);
- API errors, refusals and any other outcome lead to escalation.
"""

from __future__ import annotations

import json

from .decide import Decision, decide
from .pii_mask import mask
from .vault import Apartment, EscalationRule

__all__ = ["DEFAULT_MODEL", "decide_with_model"]

DEFAULT_MODEL = "claude-opus-5-5"
REASON_CODES = ("no_approved_answer", "needs_person", "unclear_request", "policy")

_INSTRUCTIONS = """You prepare reply drafts for guests of a holiday-rental operator.
Use only the apartment file and the rules below. If the rules say to escalate,
or the apartment file has no approved answer, escalate.
Answer in the guest's language. Do not include contact data.
Return only JSON: {"decision": "draft" | "escalate", "reason": "<code>", "draft": "<text or empty>"}
where <code> is one of: no_approved_answer, needs_person, unclear_request, policy.

# Rules
{rules}

# Apartment file
{apartment}
"""


def _client():
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise SystemExit("LLM mode needs the SDK: pip install anthropic") from exc
    return anthropic.Anthropic()


def _reason_code(value) -> str:
    """Only known codes are shown to a person; anything else becomes 'other'."""
    return value if value in REASON_CODES else "other"


def decide_with_model(
    text: str,
    booking: dict,
    apartment: Apartment,
    rules: list[EscalationRule],
    rules_text: str,
    *,
    model: str = DEFAULT_MODEL,
    client=None,
) -> Decision:
    # 1. Deterministic checks first. An escalation here is final.
    baseline = decide(text, apartment, rules)
    if baseline.kind == "escalate":
        return baseline
    language = baseline.language

    # 2. Ask the model, with the guest's contact data masked.
    masked = mask(text, booking).text
    client = client or _client()
    try:
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=_INSTRUCTIONS.replace("{rules}", rules_text).replace("{apartment}", apartment.source),
            messages=[{"role": "user", "content": masked}],
        )
    except Exception as error:  # noqa: BLE001 - any API or network failure: a person takes over
        return Decision("escalate", language, [f"model call failed ({type(error).__name__})"])

    stop_reason = getattr(response, "stop_reason", None)
    if stop_reason == "refusal":
        return Decision("escalate", language, ["model declined"])
    if stop_reason != "end_turn":
        return Decision("escalate", language, [f"model reply incomplete (stop_reason={stop_reason})"])

    # 3. Parse strictly; anything unexpected escalates.
    raw = "".join(block.text for block in response.content if block.type == "text").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").removeprefix("json").strip()
    try:
        data = json.loads(raw)
        kind = data["decision"]
        reason = str(data.get("reason", ""))
        draft = str(data.get("draft", ""))
    except (ValueError, KeyError, TypeError, AttributeError):
        return Decision("escalate", language, ["model reply was not valid JSON"])

    if kind == "draft" and draft.strip():
        if mask(draft, booking).total:
            return Decision("escalate", language, ["draft contained contact data"])
        return Decision("draft", language, topics=baseline.topics + ["model"], draft=draft.strip())
    return Decision("escalate", language, [f"model: {_reason_code(reason)}"])
