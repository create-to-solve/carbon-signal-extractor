from typing import Optional, TypedDict


class SignalState(TypedDict):
    source_name: str
    source_url: str
    run_id: Optional[str]

    raw_text: Optional[str]
    fetch_error: Optional[str]

    content_hash: Optional[str]
    previous_hash: Optional[str]
    content_changed: Optional[bool]

    signals: Optional[list]

    brief: Optional[str]
