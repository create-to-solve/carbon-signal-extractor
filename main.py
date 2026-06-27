import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from langgraph.types import Command

from graph import build_graph

load_dotenv()

SOURCES = [
    {"source_name": "UNFCCC_Art64_Rules",
     "source_url": "https://unfccc.int/process-and-meetings/bodies/constituted-bodies/article-64-supervisory-body/rules-and-regulations"},

    {"source_name": "UNFCCC_CARP_Auth",
     "source_url": "https://unfccc.int/process-and-meetings/the-paris-agreement/article-6/article-62/carp/authorizations"},

    {"source_name": "ICVCM",
     "source_url": "https://icvcm.org/assessment-status/"},

    {"source_name": "VCMI",
     "source_url": "https://vcmintegrity.org/vcmi-claims-code-of-practice/"},

    {"source_name": "BEE_India",
     "source_url": "https://beeindia.gov.in/show_content.php?lang=1&level=1&lid=294&ls_id=189"},

    {"source_name": "CERC",
     "source_url": "https://www.cercind.gov.in/Current_reg.html"},

    {"source_name": "PIB_India",
     "source_url": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2223703&lang=1&reg=3"},

    {"source_name": "Berkeley_VROD",
     "source_url": "https://gspp.berkeley.edu/berkeley-carbon-trading-project/offsets-database"},

    {"source_name": "WorldBank_Carbon",
     "source_url": "https://carbonpricingdashboard.worldbank.org/"},

    {"source_name": "ICAP_ETS",
     "source_url": "https://icapcarbonaction.com/en/ets"},

    {"source_name": "ICAP_India",
     "source_url": "https://icapcarbonaction.com/en/ets/indian-carbon-credit-trading-scheme"},
]


def run():
    run_started_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    bar = "=" * 70
    print(bar)
    print(f"=== RUN START {run_started_utc} ===")
    print(bar, flush=True)

    graph = build_graph()

    for source in SOURCES:
        print(f"\n--- Running: {source['source_name']} ---")

        thread_id = f"{source['source_name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        config = {"configurable": {"thread_id": thread_id}}
        print(f"thread_id: {thread_id}")

        result = graph.invoke({**source, "run_id": thread_id}, config=config)

        # If the graph paused at an interrupt, drive the human-in-the-loop here.
        while "__interrupt__" in result:
            payload = result["__interrupt__"][0].value
            print("\n>>> HUMAN REVIEW REQUIRED <<<")
            print(f"Source: {payload['source_name']}")
            print("Extracted signals:")
            print(json.dumps(payload["signals"], indent=2))
            print(payload["prompt"])
            if os.environ.get("CARBON_NONINTERACTIVE"):
                print("Non-interactive mode — auto-skipping.")
                decision = "skip"
            else:
                decision = input("Your decision [approve/skip]: ")
            result = graph.invoke(Command(resume=decision), config=config)

        changed = result.get("content_changed")
        hash_val = (result.get("content_hash") or "")[:12]
        if result.get("fetch_error"):
            print(f"Status: ERROR — {result['fetch_error']}")
        elif changed is False and result.get("previous_hash"):
            print(f"Status: NO CHANGE (hash {hash_val}...)")
        elif changed:
            status = "NEW SOURCE" if not result.get("previous_hash") else "CHANGED"
            print(f"Status: {status} (hash {hash_val}...)")

        print("\n--- Final brief ---")
        print(result.get("brief"))
        print(f"\nSignals found: {len(result.get('signals') or [])}")
        if result.get("fetch_error"):
            print(f"Fetch error: {result['fetch_error']}")

        print("\n--- debug ---")
        print("fetch_error:", result.get("fetch_error"))
        print("raw_text length:", len(result.get("raw_text") or ""))
        print("signals:", result.get("signals"), flush=True)

    run_ended_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(bar)
    print(f"=== RUN END   {run_ended_utc} ===")
    print(bar, flush=True)


if __name__ == "__main__":
    run()
