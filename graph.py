import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

import db
from nodes.check_change import check_change
from nodes.extract_signals import extract_signals
from nodes.fetch_source import fetch_source
from nodes.format_brief import format_brief
from nodes.no_change import no_change
from state import SignalState

CHECKPOINT_DB = "checkpoints/signals.db"

db.init_db()


def route_after_change_check(state: SignalState) -> str:
    if state.get("content_changed"):
        return "extract_signals"
    return "no_change"


def build_graph():
    builder = StateGraph(SignalState)

    builder.add_node("fetch_source", fetch_source)
    builder.add_node("check_change", check_change)
    builder.add_node("extract_signals", extract_signals)
    builder.add_node("format_brief", format_brief)
    builder.add_node("no_change", no_change)

    builder.add_edge(START, "fetch_source")
    builder.add_edge("fetch_source", "check_change")
    builder.add_conditional_edges(
        "check_change",
        route_after_change_check,
        {
            "extract_signals": "extract_signals",
            "no_change": "no_change",
        },
    )
    builder.add_edge("extract_signals", "format_brief")
    builder.add_edge("format_brief", END)
    builder.add_edge("no_change", END)

    conn = sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    return builder.compile(checkpointer=checkpointer)
