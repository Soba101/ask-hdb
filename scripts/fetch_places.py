"""Download the three approved place datasets from data.gov.sg into data/raw/places/ (git-ignored)."""

import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/places"
# Dataset ids were approved by the user on 2026-10-20.
DATASETS = {
    "mrt_exits.geojson": "d_b39d3a0871985372d7e1637193335da5",  # LTA MRT Station Exit
    "schools.csv": "d_688b934f82c1059ed0a6993d2a829089",  # MOE general information of schools
    "hdb_buildings.geojson": "d_16b157c52ed637edd6ba1232e026258d",  # HDB Existing Buildings
}


def download(client, name, dataset_id, headers):
    url = None
    for attempt in range(5):
        r = client.get(
            f"https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download",
            headers=headers, timeout=30,
        )
        if r.status_code == 429:
            time.sleep(5 * (attempt + 1))
            continue
        r.raise_for_status()
        body = r.json()
        if "url" not in body.get("data", {}):
            raise RuntimeError(f"{name}: unexpected poll-download response")
        url = body["data"]["url"]
        break
    if url is None:
        raise RuntimeError(f"{name}: rate limited, try again later")
    tmp = OUT / (name + ".part")
    with client.stream("GET", url, timeout=120) as resp:
        resp.raise_for_status()
        with open(tmp, "wb") as f:
            f.writelines(resp.iter_bytes())
    tmp.replace(OUT / name)
    print(f"{name}: {(OUT / name).stat().st_size / 1e6:.2f} MB")


def main():
    load_dotenv()
    OUT.mkdir(parents=True, exist_ok=True)
    key = os.getenv("DATAGOV_API_KEY")
    headers = {"x-api-key": key} if key else {}
    with httpx.Client(follow_redirects=True) as client:
        for name, dataset_id in DATASETS.items():
            if (OUT / name).exists():
                print(f"{name}: already downloaded")
                continue
            download(client, name, dataset_id, headers)


if __name__ == "__main__":
    main()
