"""
Verification harness for the taxonomy layer (spec step 3).
Seeds a dummy baseline hash for ICVCM so the next run is CHANGED, then
invokes the compiled graph against just that source and auto-approves
the human-in-the-loop interrupt so we can inspect the classified brief.
"""

import sqlite3
from datetime import datetime

from dotenv import load_dotenv
from langgraph.types import Command

import db
from graph import build_graph

load_dotenv()

SOURCE = {
    "source_name": "ICVCM",
    "source_url": "https://icvcm.org/assessment-status/",
}


def seed_dummy_baseline(source_name: str) -> None:
    db.init_db()
    db.save_run(
        source_name=source_name,
        run_id="seed_baseline",
        content_hash="0" * 64,  # deliberately wrong
        content_length=0,
        status="new",
    )
    print(f"Seeded baseline row for {source_name} with dummy hash 0000...0000")


def main():
    seed_dummy_baseline(SOURCE["source_name"])

    graph = build_graph()
    thread_id = f"{SOURCE['source_name']}_verify_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    config = {"configurable": {"thread_id": thread_id}}
    print(f"thread_id: {thread_id}\n")

    result = graph.invoke({**SOURCE, "run_id": thread_id}, config=config)

    while "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        print(">>> Auto-approving interrupt for verification <<<")
        print(f"Signals about to be saved: {len(payload['signals'])}")
        result = graph.invoke(Command(resume="approve"), config=config)

    print("\n--- content_changed:", result.get("content_changed"))
    print("--- previous_hash[:12]:", (result.get("previous_hash") or "")[:12])
    print("--- content_hash[:12]:", (result.get("content_hash") or "")[:12])
    print("\n--- Final brief ---\n")
    print(result.get("brief"))

    print("\n--- signals table contents ---")
    with sqlite3.connect("data/app.db") as conn:
        rows = list(
            conn.execute(
                """
                SELECT id, source_name, signal_type, headline
                FROM signals
                WHERE run_id = ?
                ORDER BY id
                """,
                (thread_id,),
            )
        )
    for r in rows:
        print(r)
    print(f"rows saved this run: {len(rows)}")


if __name__ == "__main__":
    main()
