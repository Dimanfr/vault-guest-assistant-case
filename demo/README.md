# Synthetic demo

A small, runnable model of the idea behind the pilot: the assistant answers only from an editable Markdown knowledge base and escalates everything else. Everything here is fictional: the operator, both apartments, the guests and their contact data. All phone numbers are invalid by design.

```bash
python3 run_demo.py                       # offline, deterministic, Python 3.9+, no dependencies
python3 -m unittest discover -s tests     # 37 tests
```

## What is where
| Path | What it is |
|---|---|
| `vault/rules.md` | Response rules of a fictional operator, including the escalation table the code reads at run time |
| `vault/apartments/A-101.md`, `A-102.md` | Two fictional apartments; each `##` section is one approved answer in English and German |
| `messages.json` | Six fictional guest messages, with fictional booking contact data |
| `assistant/decide.py` | Offline decision: instruction-override check → escalation triggers from `rules.md` → matching apartment section → draft, or escalate |
| `assistant/pii_mask.py` | Masks guest name, phone and e-mail (known booking values plus patterns) before a person or a model sees the message |
| `assistant/llm.py` | Optional: a Claude model writes the draft, only after the offline checks allow it |
| `run_demo.py` | Prints what the operator's team would see for each message |

## Change the Vault, change the behaviour
Add `parrot` to the `pets` row in `vault/rules.md` and run again: "Can we bring our parrot?" is now escalated as `pets ("parrot")` instead of "no approved answer". Edit an `en:` line in an apartment file, and the draft changes. No code is touched; `tests/test_decide.py` checks exactly this.

## Optional: drafts by a model
```bash
pip install anthropic
export ANTHROPIC_API_KEY=...        # your own key
python3 run_demo.py --llm           # default model: claude-opus-5-5; change with --model
```
- **The offline checks run first and are final.** Instruction-override attempts, escalation triggers from `rules.md` and questions without an approved answer are escalated before any model call. The model can make a result more careful, never less.
- The model receives the rules, the apartment file and the **masked** message only.
- A draft is accepted only from a normally finished reply (`stop_reason: end_turn`) with valid JSON and no contact data. Refusals, other stop reasons, API errors and anything unexpected lead to escalation.
- The model's escalation reason must be one of four codes (`no_approved_answer`, `needs_person`, `unclear_request`, `policy`). Free text from the model is never shown as a reason, because it could carry personal data that no pattern recognises.
- The request opts in to server-side model fallbacks.

The automated tests cover this mode with a fake client. A live run costs API usage on your own key.

## Limitations
- Matching is keyword-based. It does not understand paraphrases, and a message that mentions a trigger word in passing is escalated (on purpose: when in doubt, ask a person).
- Language detection knows English and German only.
- The mask is pattern-based. It is not anonymisation, and it misses misspelt names, other people's names and addresses.
- A model draft is checked for this booking's contact data and for contact-like patterns. Names or addresses the model might invent are not detected; a person reads every draft before it is used.
- Nothing is sent anywhere. In the real pilot, sending through the channel manager was not exercised either.

## Licence
MIT for everything in this `demo/` folder (see `LICENSE`). The case text and diagram in the repository root are not covered by it.
