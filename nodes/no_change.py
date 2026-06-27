from state import SignalState


def no_change(state: SignalState) -> dict:
    if state.get("fetch_error"):
        return {
            "brief": (
                f"Source unavailable — {state['source_name']} "
                f"fetch failed: {state['fetch_error']}"
            ),
            "signals": [],
        }
    return {
        "brief": f"No changes detected for {state['source_name']} since last run.",
        "signals": [],
    }
