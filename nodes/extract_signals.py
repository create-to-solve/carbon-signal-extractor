import json
import os

import openai

from state import SignalState
from taxonomy import SIGNAL_TYPES

SYSTEM_PROMPT = (
    "You are a carbon markets analyst assistant. Your job is to read source "
    "material from official carbon market bodies and extract intelligence "
    "signals that matter to practitioners — project developers, carbon "
    "buyers, policymakers, and advisors."
)


def extract_signals(state: SignalState) -> dict:
    if state.get("fetch_error") or not state.get("raw_text"):
        return {"signals": []}

    type_list = "\n".join(f"  - {k}: {v}" for k, v in SIGNAL_TYPES.items())

    user_prompt = f"""Source: {state["source_name"]}

Raw page content:
---
{state["raw_text"]}
---

Extract a list of intelligence signals from the above source material.

For each signal, you must also classify it with a signal_type. Choose exactly
one type from this list:

{type_list}

Classification rules:
- Use india_regulatory when the signal is specific to India's carbon market,
  even if another type also fits.
- Classify by content, not format: a new PDF containing a rule change is
  rule_change, not publication.
- Use publication only when no more specific type applies.

Return a JSON array. Each object must have exactly four fields:
  headline, why_it_matters, who_is_affected, signal_type.
No other fields. No preamble. No markdown fences.

If no signals are present, return [].
"""

    try:
        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1000,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw_text = response.choices[0].message.content
        text = _strip_markdown_fences(raw_text)
        try:
            signals = json.loads(text)
        except json.JSONDecodeError as e:
            print(f"[extract_signals] JSON parse failed: {e}")
            print(f"[extract_signals] raw LLM response:\n---\n{raw_text}\n---")
            return {"signals": []}
        if not isinstance(signals, list):
            print(
                f"[extract_signals] LLM did not return a JSON array "
                f"(got {type(signals).__name__}):\n---\n{raw_text}\n---"
            )
            return {"signals": []}
        return {"signals": [_normalize_signal(s) for s in signals]}
    except Exception as e:
        print(f"[extract_signals] warning: {type(e).__name__}: {e}")
        return {"signals": []}


def _normalize_signal(s: dict) -> dict:
    """Drop unexpected fields, force signal_type into the canonical vocabulary."""
    signal_type = s.get("signal_type")
    if signal_type not in SIGNAL_TYPES:
        print(
            f"[extract_signals] warning: unknown signal_type "
            f"{signal_type!r}; replacing with 'publication'"
        )
        signal_type = "publication"
    return {
        "headline": s.get("headline", ""),
        "why_it_matters": s.get("why_it_matters", ""),
        "who_is_affected": s.get("who_is_affected", ""),
        "signal_type": signal_type,
    }


def _strip_markdown_fences(text: str) -> str:
    s = text.strip()
    if not s.startswith("```"):
        return s
    lines = s.splitlines()
    # drop opening fence (```json, ```JSON, ```)
    lines = lines[1:]
    # drop closing fence if present
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
