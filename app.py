import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from langgraph.types import Command

from graph import build_graph
from main import SOURCES

load_dotenv()

st.set_page_config(page_title="Carbon Market Intelligence", layout="wide")


@st.cache_resource
def get_graph():
    return build_graph()


graph = get_graph()


defaults = {
    "phase": "idle",
    "remaining": [],
    "completed": [],
    "pending": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


def get_signal_distribution() -> pd.DataFrame:
    try:
        conn = sqlite3.connect("data/app.db")
        df = pd.read_sql_query(
            "SELECT signal_type, COUNT(*) as count FROM signals "
            "GROUP BY signal_type ORDER BY count DESC",
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame(columns=["signal_type", "count"])


def render_chart():
    df = get_signal_distribution()
    if df.empty:
        st.info("No signals in archive yet. Run a sweep to populate.")
        return
    st.bar_chart(df.set_index("signal_type"))


def render_archive():
    st.subheader("📋 Signal Archive")

    conn = sqlite3.connect("data/app.db")
    df = pd.read_sql_query(
        """
        SELECT
            date(detected_at)   AS date,
            source_name         AS source,
            signal_type         AS type,
            headline,
            why_it_matters,
            who_is_affected     AS who,
            source_url          AS url
        FROM signals
        ORDER BY detected_at DESC
        """,
        conn,
    )
    conn.close()

    if df.empty:
        st.info("No signals in archive yet. Run a sweep to populate.")
        return

    col1, col2 = st.columns(2)
    with col1:
        selected_types = st.multiselect(
            "Filter by type",
            options=sorted(df["type"].unique()),
            default=[],
            placeholder="All types",
        )
    with col2:
        selected_sources = st.multiselect(
            "Filter by source",
            options=sorted(df["source"].unique()),
            default=[],
            placeholder="All sources",
        )

    filtered = df.copy()
    if selected_types:
        filtered = filtered[filtered["type"].isin(selected_types)]
    if selected_sources:
        filtered = filtered[filtered["source"].isin(selected_sources)]

    st.caption(f"{len(filtered)} signal(s) shown of {len(df)} total")

    st.dataframe(
        filtered,
        use_container_width=True,
        hide_index=True,
        column_config={
            "url": st.column_config.LinkColumn(
                "Source", display_text="↗ Open"
            ),
            "date": st.column_config.TextColumn("Date", width="small"),
            "source": st.column_config.TextColumn("Source", width="medium"),
            "type": st.column_config.TextColumn("Type", width="medium"),
            "headline": st.column_config.TextColumn("Headline", width="large"),
            "why_it_matters": st.column_config.TextColumn(
                "Why it matters", width="large"
            ),
            "who": st.column_config.TextColumn("Who", width="medium"),
        },
        column_order=[
            "date", "source", "type", "headline",
            "why_it_matters", "who", "url",
        ],
    )


def render_taxonomy_legend():
    from taxonomy import SIGNAL_TYPES

    with st.expander("ℹ️ Signal Type Definitions"):
        for type_name, definition in SIGNAL_TYPES.items():
            st.markdown(f"**`{type_name}`** — {definition}")
            st.divider()


BADGES = {
    "no_change": ("⬛", "NO CHANGE"),
    "approved": ("🟢", "{n} signals"),
    "skipped": ("🟡", "SKIPPED"),
    "error": ("🔴", "ERROR"),
}


def render_completed(item: dict):
    icon, label = BADGES[item["status"]]
    label = label.format(n=item.get("signal_count", 0))
    with st.container(border=True):
        st.markdown(f"**{icon} {item['source_name']} — {label}**")
        if item["status"] == "approved" and item.get("brief"):
            with st.expander("View brief"):
                st.markdown(item["brief"])
        elif item["status"] == "error" and item.get("fetch_error"):
            st.error(item["fetch_error"])


def reset_to_idle():
    st.session_state.phase = "idle"
    st.session_state.remaining = []
    st.session_state.completed = []
    st.session_state.pending = None


# ---------- header ----------
st.title("🌍 Carbon Market Signal Intelligence")
st.caption(
    "Monitors 11 official carbon market sources for regulatory and policy changes."
)

phase = st.session_state.phase

# ---------- idle ----------
if phase == "idle":
    if st.button("▶ Run Intelligence Sweep", type="primary"):
        st.session_state.phase = "running"
        st.session_state.remaining = list(SOURCES)
        st.session_state.completed = []
        st.session_state.pending = None
        st.rerun()
    render_chart()
    render_archive()
    render_taxonomy_legend()
    if st.session_state.completed:
        st.subheader("Last sweep results")
        for item in st.session_state.completed:
            render_completed(item)

# ---------- running ----------
elif phase == "running":
    st.subheader("Sweep in progress")
    for item in st.session_state.completed:
        render_completed(item)

    if not st.session_state.remaining:
        st.session_state.phase = "done"
        st.rerun()

    source = st.session_state.remaining.pop(0)
    source_name = source["source_name"]
    thread_id = (
        f"{source_name}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    )
    config = {"configurable": {"thread_id": thread_id}}

    with st.spinner(f"Checking {source_name}…"):
        result = graph.invoke(
            {**source, "run_id": thread_id}, config=config
        )

    if "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        st.session_state.pending = {
            "source_name": source_name,
            "signals": payload["signals"],
            "config": config,
            "interrupt_result": result,
        }
        st.session_state.phase = "reviewing"
        st.rerun()
    else:
        if result.get("fetch_error"):
            status = "error"
        else:
            status = "no_change"
        st.session_state.completed.append(
            {
                "source_name": source_name,
                "status": status,
                "brief": result.get("brief", ""),
                "signal_count": 0,
                "fetch_error": result.get("fetch_error"),
            }
        )
        st.rerun()

# ---------- reviewing ----------
elif phase == "reviewing":
    for item in st.session_state.completed:
        render_completed(item)

    pending = st.session_state.pending
    source_name = pending["source_name"]
    signals = pending["signals"]

    st.subheader(f"⏸ Review Required — {source_name}")
    st.write(f"{len(signals)} signal(s) extracted. Approve to generate the brief.")
    for i, sig in enumerate(signals, 1):
        with st.expander(f"{i}. [{sig.get('signal_type', '?')}] {sig.get('headline', '')}"):
            st.json(sig)

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("✅ Approve — generate brief", type="primary"):
            with st.spinner(f"Generating brief for {source_name}…"):
                final = graph.invoke(
                    Command(resume="approve"), config=pending["config"]
                )
            st.session_state.completed.append(
                {
                    "source_name": source_name,
                    "status": "approved",
                    "brief": final.get("brief", ""),
                    "signal_count": len(signals),
                    "fetch_error": None,
                }
            )
            st.session_state.pending = None
            st.session_state.phase = "running"
            st.rerun()
    with col_b:
        if st.button("⏭ Skip"):
            # Drive the graph to a clean terminal state too.
            graph.invoke(Command(resume="skip"), config=pending["config"])
            st.session_state.completed.append(
                {
                    "source_name": source_name,
                    "status": "skipped",
                    "brief": "Skipped by reviewer.",
                    "signal_count": len(signals),
                    "fetch_error": None,
                }
            )
            st.session_state.pending = None
            st.session_state.phase = "running"
            st.rerun()

# ---------- done ----------
elif phase == "done":
    st.success("✅ Sweep complete")
    for item in st.session_state.completed:
        render_completed(item)
    st.divider()
    render_chart()
    render_archive()
    render_taxonomy_legend()
    if st.button("🔁 Run Again"):
        reset_to_idle()
        st.rerun()
