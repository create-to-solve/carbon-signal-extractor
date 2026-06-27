import os
from collections import defaultdict

import openai
from langgraph.types import interrupt

import db
from state import SignalState
from taxonomy import TYPE_PRIORITY


def format_brief(state: SignalState) -> dict:
    signals = state.get("signals") or []
    source_name = state["source_name"]

    if not signals:
        return {"brief": f"No signals extracted from {source_name}."}

    decision = interrupt(
        {
            "source_name": source_name,
            "signals": signals,
            "prompt": "Type 'approve' to generate the brief, or 'skip' to abort.",
        }
    )
    decision = str(decision).strip().lower()
    if decision != "approve":
        return {
            "brief": (
                f"Brief generation skipped by reviewer for {source_name}. "
                f"{len(signals)} signal(s) were available."
            )
        }

    db.save_signals(
        source_name=source_name,
        run_id=state.get("run_id") or "unknown",
        signals=signals,
        content_hash=state.get("content_hash"),
        source_url=state.get("source_url"),
    )

    grouped_block = _format_grouped(signals)

    user_prompt = f"""Format these carbon market intelligence signals into a readable brief.

Source: {source_name}

Pre-grouped signals (already sorted by priority and grouped by type):
{grouped_block}

Format requirements:
- First line: `Carbon Market Signal Brief — {source_name}`
- One blank line
- For each type group, output a header line `[type_name]` followed by bullets.
  Each bullet shows: headline, why it matters, who is affected.
- Preserve the group ordering and bullet ordering exactly as provided above.
- One blank line between groups.
- Closing line: `{len(signals)} signal(s) detected.`

Return ONLY the brief text, no preamble.
"""

    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1200,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return {"brief": response.choices[0].message.content.strip()}


def _format_grouped(signals: list) -> str:
    by_type: dict[str, list[dict]] = defaultdict(list)
    for s in signals:
        by_type[s["signal_type"]].append(s)

    blocks = []
    seen = set()
    for t in TYPE_PRIORITY:
        if t in by_type:
            seen.add(t)
            blocks.append(_render_block(t, by_type[t]))
    # Any unexpected types (shouldn't happen post-normalization) come last.
    for t, items in by_type.items():
        if t not in seen:
            blocks.append(_render_block(t, items))
    return "\n\n".join(blocks)


def _render_block(signal_type: str, items: list) -> str:
    lines = [f"[{signal_type}]"]
    for s in items:
        lines.append(
            f"• {s['headline']}\n"
            f"  Why it matters: {s['why_it_matters']}\n"
            f"  Who is affected: {s['who_is_affected']}"
        )
    return "\n".join(lines)
