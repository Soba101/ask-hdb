"""Download HDB resale prices (Jan 2017 on) from data.gov.sg into data/raw/resale.csv.

Re-runnable: it overwrites the file. Raw data is never edited by hand.
The API key is read from .env (DATAGOV_API_KEY). It is optional but avoids rate limits.
"""
import csv
import os
import time
from pathlib import Path

import httpx

DATASET = "d_8b84c4ee58e3cfc0ece0d773c8ca6abc"
URL = "https://data.gov.sg/api/action/datastore_search"
OUT = Path("data/raw/resale.csv")
PAGE = 5000


def load_key() -> str | None:
    # Tiny .env reader so we do not need another dependency.
    env = Path(".env")
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("DATAGOV_API_KEY="):
                return line.split("=", 1)[1].strip() or None
    return os.environ.get("DATAGOV_API_KEY")


def get_page(client: httpx.Client, offset: int) -> dict:
    # Retry with a growing pause when the API says "too many requests".
    for attempt in range(8):
        r = client.get(URL, params={"resource_id": DATASET, "limit": PAGE, "offset": offset})
        if r.status_code == 429:
            time.sleep(2 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()["result"]
    raise RuntimeError("data.gov.sg kept returning 429")


def main() -> None:
    key = load_key()
    headers = {"x-api-key": key} if key else {}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    with httpx.Client(headers=headers, timeout=60) as client:
        offset = 0
        while True:
            result = get_page(client, offset)
            rows.extend(result["records"])
            offset += PAGE
            print(f"fetched {len(rows)} of {result.get('total')}")
            if offset >= result["total"]:
                break
            time.sleep(0.5)
    fields = [f["id"] for f in result["fields"] if f["id"] != "_id"]
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
