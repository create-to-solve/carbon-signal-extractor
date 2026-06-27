import hashlib

import db
from state import SignalState


def check_change(state: SignalState) -> dict:
    source_name = state["source_name"]
    run_id = state.get("run_id") or "unknown"

    if state.get("fetch_error"):
        db.save_run(source_name, run_id, None, 0, "error")
        return {
            "content_hash": None,
            "previous_hash": None,
            "content_changed": False,
        }

    raw_text = state.get("raw_text") or ""
    current_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    previous_hash = db.get_last_hash(source_name)

    if previous_hash is None:
        status = "new"
        changed = True
    elif current_hash != previous_hash:
        status = "changed"
        changed = True
    else:
        status = "unchanged"
        changed = False

    db.save_run(source_name, run_id, current_hash, len(raw_text), status)

    return {
        "content_hash": current_hash,
        "previous_hash": previous_hash,
        "content_changed": changed,
    }
