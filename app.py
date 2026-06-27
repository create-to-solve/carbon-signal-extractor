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


# ---------- archive / chart helpers ----------
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


# ---------- today tab ----------
def get_today_data():
    conn = sqlite3.connect("data/app.db")

    recent_runs = pd.read_sql_query(
        """
        SELECT
            sr.source_name,
            sr.fetched_at,
            sr.status,
            sr.content_length,
            sr.run_id
        FROM source_runs sr
        INNER JOIN (
            SELECT source_name, MAX(fetched_at) as max_fetched
            FROM source_runs
            GROUP BY source_name
        ) latest
        ON sr.source_name = latest.source_name
        AND sr.fetched_at = latest.max_fetched
        ORDER BY sr.fetched_at DESC
        """,
        conn,
    )

    recent_signals = pd.read_sql_query(
        """
        SELECT source_name, COUNT(*) as signal_count
        FROM signals
        WHERE detected_at >= datetime('now', '-24 hours')
        GROUP BY source_name
        """,
        conn,
    )

    timeline = pd.read_sql_query(
        """
        SELECT date(detected_at) as day, COUNT(*) as signals
        FROM signals
        GROUP BY day
        ORDER BY day
        """,
        conn,
    )

    conn.close()
    return recent_runs, recent_signals, timeline


def render_today():
    st.subheader("📅 Today")

    recent_runs, recent_signals, timeline = get_today_data()

    if recent_runs.empty:
        st.info("No sweep has been run yet. Click 'Run Intelligence Sweep' to start.")
        return

    last_run_time = recent_runs["fetched_at"].max()
    changed = (recent_runs["status"] == "changed").sum()
    no_change = (recent_runs["status"] == "unchanged").sum()
    errors = (recent_runs["status"] == "error").sum()
    new_sources = (recent_runs["status"] == "new").sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Last Run", pd.to_datetime(last_run_time).strftime("%d %b %H:%M"))
    col2.metric(
        "Changed",
        int(changed) + int(new_sources),
        delta=None if changed == 0 else f"{changed} source(s)",
    )
    col3.metric("No Change", int(no_change))
    col4.metric(
        "Errors",
        int(errors),
        delta_color="inverse" if errors > 0 else "off",
    )

    st.divider()

    changed_sources = recent_runs[recent_runs["status"].isin(["changed", "new"])]
    if not changed_sources.empty:
        st.markdown("**🟢 Changed — pending your review**")
        for _, row in changed_sources.iterrows():
            sig_count = recent_signals[
                recent_signals["source_name"] == row["source_name"]
            ]["signal_count"].values
            sig_text = (
                f"{sig_count[0]} signal(s) saved"
                if len(sig_count) > 0
                else "auto-skipped (cloud run)"
            )
            st.markdown(
                f"- **{row['source_name']}** — detected "
                f"{pd.to_datetime(row['fetched_at']).strftime('%H:%M')} — {sig_text}"
            )
        st.caption(
            "Open Streamlit and run a sweep to review and approve these signals."
        )
        st.divider()

    error_sources = recent_runs[recent_runs["status"] == "error"]
    if not error_sources.empty:
        st.markdown("**🔴 Errors**")
        for _, row in error_sources.iterrows():
            st.markdown(f"- **{row['source_name']}** — fetch failed")
        st.divider()

    if changed_sources.empty and error_sources.empty:
        st.success("All sources checked — no changes detected since last run.")

    if not timeline.empty and len(timeline) > 1:
        st.markdown("**📈 Signals detected over time**")
        st.bar_chart(timeline.set_index("day"))


# ---------- source monitor tab ----------
def get_source_monitor_data():
    conn = sqlite3.connect("data/app.db")

    df = pd.read_sql_query(
        """
        SELECT
            sr.source_name,
            MAX(sr.fetched_at)                                          AS last_checked,
            MAX(CASE WHEN sr.status IN ('changed','new')
                THEN sr.fetched_at END)                                 AS last_changed,
            COUNT(*)                                                    AS total_runs,
            SUM(CASE WHEN sr.status = 'error' THEN 1 ELSE 0 END)        AS errors,
            ROUND(
                100.0 * SUM(CASE WHEN sr.status = 'error' THEN 1 ELSE 0 END)
                / COUNT(*), 1
            )                                                           AS error_pct,
            COALESCE(sig.signal_count, 0)                               AS total_signals,
            latest.status                                               AS last_status
        FROM source_runs sr
        LEFT JOIN (
            SELECT source_name, COUNT(*) as signal_count
            FROM signals GROUP BY source_name
        ) sig ON sr.source_name = sig.source_name
        LEFT JOIN (
            SELECT source_name, status
            FROM source_runs
            WHERE (source_name, fetched_at) IN (
                SELECT source_name, MAX(fetched_at)
                FROM source_runs GROUP BY source_name
            )
        ) latest ON sr.source_name = latest.source_name
        GROUP BY sr.source_name
        ORDER BY last_checked DESC
        """,
        conn,
    )

    conn.close()
    return df


def render_source_monitor():
    st.subheader("🔍 Source Monitor")

    df = get_source_monitor_data()

    if df.empty:
        st.info("No source runs recorded yet.")
        return

    def status_badge(status):
        badges = {
            "unchanged": "⬛ NO CHANGE",
            "changed":   "🟢 CHANGED",
            "new":       "🟢 NEW",
            "error":     "🔴 ERROR",
        }
        return badges.get(status, status)

    df["Status"] = df["last_status"].apply(status_badge)
    df["Last Checked"] = (
        pd.to_datetime(df["last_checked"]).dt.strftime("%d %b %H:%M")
    )
    df["Last Changed"] = (
        pd.to_datetime(df["last_changed"]).dt.strftime("%d %b %H:%M").fillna("Never")
    )

    display_df = df[[
        "source_name", "Status", "Last Checked", "Last Changed",
        "total_runs", "error_pct", "total_signals",
    ]].rename(columns={
        "source_name":   "Source",
        "total_runs":    "Runs",
        "error_pct":     "Error %",
        "total_signals": "Signals",
    })

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Source":       st.column_config.TextColumn("Source", width="medium"),
            "Status":       st.column_config.TextColumn("Last Status", width="medium"),
            "Last Checked": st.column_config.TextColumn("Last Checked", width="medium"),
            "Last Changed": st.column_config.TextColumn("Last Changed", width="medium"),
            "Runs":         st.column_config.NumberColumn("Runs", width="small"),
            "Error %":      st.column_config.NumberColumn(
                "Error %", width="small", format="%.1f%%"
            ),
            "Signals":      st.column_config.NumberColumn("Signals", width="small"),
        },
    )

    st.caption(
        f"{len(df)} sources monitored · "
        f"{int(df['total_runs'].sum())} total runs · "
        f"{int(df['total_signals'].sum())} signals in archive"
    )


# ---------- completed result card ----------
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


def render_tabs():
    tab1, tab2, tab3 = st.tabs([
        "📅 Today", "📋 Signal Archive", "🔍 Source Monitor"
    ])
    with tab1:
        render_today()
    with tab2:
        render_chart()
        render_archive()
        render_taxonomy_legend()
    with tab3:
        render_source_monitor()


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
    render_tabs()

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
    if st.button("🔁 Run Again"):
        reset_to_idle()
        st.rerun()
    st.divider()
    render_tabs()
