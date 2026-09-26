"""
One-off backfill of the selection ledger (selections.py) from the datasets
the screener actually published before the ledger existed.

The `data` branch is force-pushed as one flat commit per run, so its history
is gone from the branch -- but the old commits are still fetchable by SHA.
These are every run that could be recovered (2026-09-26): the public Events API
listed the push SHAs back to 2026-08-25, and four more (08-20, both 08-21 runs,
08-24) survived as unreachable objects in a local clone. Runs from 2026-06-25 to
2026-08-19 could not be recovered, so a first entry dated 2026-08-20 means the
stock was already selected on the earliest recovered run.

Replays the runs oldest-first through selections.update_ledger -- the same code
every screen runs -- and writes the ledger. With --annotate, also merges it
into a results.json whose generated_at is the last replayed run (the currently
published dataset), so the site shows entry prices before the next screen.

    python backfill_selections.py --out web/public/data/selections.json \
        [--annotate web/public/data/results.json] [--cache /tmp/backfill]
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

import selections

RAW = "https://raw.githubusercontent.com/alloy-and-steel/screener/{sha}/web/public/data/results.json"

# (generated_at, data-branch commit) for every recovered run, oldest first.
RUNS = [
    ("2026-08-20T11:37:47Z", "71942eb1fd14455a19f6446c89184cef158f4122"),
    ("2026-08-21T06:08:02Z", "49db9eec3d7047c7ac03b0d7bca9d42bd0a30e76"),
    ("2026-08-21T11:37:30Z", "2f04c09576553c5117ba8a3181f72c152d3b26fa"),
    ("2026-08-24T11:39:23Z", "f6f12a98e60ea7e608e8251bf3239f2cd4aad5f7"),
    ("2026-08-25T11:38:22Z", "1c679c18793337da06d6fd8641183857d3aff678"),
    ("2026-08-26T11:40:56Z", "e7a8e9ed773e047eced2b44175e13e83bbb4a0b8"),
    ("2026-08-27T21:12:04Z", "641420824e9af8ecb660f218ffbd7415f5834829"),
    ("2026-08-28T21:30:17Z", "37e11553dbbd73de49f6c7bd4434caca561437ba"),
    ("2026-08-31T18:08:10Z", "9ef5b9571fe0e29814ab835d03fca10591d711c1"),
    ("2026-09-02T15:16:11Z", "e489b19f0d1ddcd397d2fe5282e3f255919aa51b"),
    ("2026-09-03T15:11:09Z", "5990a63204277b534b868be4fe402700eedbadca"),
    ("2026-09-04T15:04:29Z", "f03ad087954c798eaa1c899a1903fbf292a17a1f"),
    ("2026-09-07T16:27:57Z", "08c453eebec9eae70d4b25814dae1da27d5c1105"),
    ("2026-09-08T15:18:45Z", "1f28b9bdfe1cdddc0360e67c2471b86e499e4d31"),
    ("2026-09-09T15:22:07Z", "3a384f7aafc7d9906f897ad2970def2668ae8c64"),
    ("2026-09-10T15:04:09Z", "30c98ffc18995e814742ec352dafd9f6e074f6ad"),
    ("2026-09-11T15:04:35Z", "0a6b9a9effbbf965e2bc7c95f3c65de40cdb27c8"),
    ("2026-09-14T17:02:43Z", "11459eb5262177ab5eab43aaa5db6094a2841b0a"),
    ("2026-09-15T15:43:15Z", "fe92b48634889175e7f41fc6131623866bbfb94d"),
    ("2026-09-16T15:33:57Z", "63b7c884d0161f957d2c5ff0e2e9c59f98891c04"),
    ("2026-09-17T15:42:48Z", "c3bedc3c0220d5feb0f6a8311c61eb9c1bfc05c3"),
    ("2026-09-18T15:07:27Z", "081125e7e1fa6b4e604de9776205ea5a91ecaec8"),
    ("2026-09-21T17:06:35Z", "4a6e9300862cecf536649bd49d02ea26b7bc5370"),
    ("2026-09-22T15:38:22Z", "2febe08e6bc2df4e0927c8b0ce0de491b99d8631"),
    ("2026-09-23T15:30:47Z", "108af8c20599b378bde4a1d55406ecefd2a8c089"),
    ("2026-09-24T15:55:31Z", "5b149766ec1551ab16c70a00c0603a744de7739a"),
    ("2026-09-25T15:59:05Z", "0140f42c5b2605815694d752390efcb1a7b4a500"),
]


def fetch(sha: str, cache: Path | None) -> dict:
    if cache is not None and (cache / f"{sha}.json").exists():
        return json.loads((cache / f"{sha}.json").read_text(encoding="utf-8"))
    with urllib.request.urlopen(RAW.format(sha=sha), timeout=60) as resp:
        body = resp.read()
    if cache is not None:
        cache.mkdir(parents=True, exist_ok=True)
        (cache / f"{sha}.json").write_bytes(body)
    return json.loads(body)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--annotate", type=Path)
    ap.add_argument("--cache", type=Path)
    args = ap.parse_args()

    ledger = selections.empty_ledger()
    for at, sha in RUNS:
        data = fetch(sha, args.cache)
        if data["generated_at"] != at:
            raise SystemExit(f"{sha}: generated_at {data['generated_at']} != expected {at}")
        ledger = selections.update_ledger(ledger, data["rows"], at)
        now = sum(1 for e in ledger["tickers"].values() if e["selected"])
        print(f"{at}  {sha[:8]}  selected now {now:3d}  ever {len(ledger['tickers']):3d}")

    selections.save_ledger(args.out, ledger)
    print(f"wrote {args.out}")

    if args.annotate:
        payload = json.loads(args.annotate.read_text(encoding="utf-8"))
        if payload["generated_at"] != ledger["updated_at"]:
            raise SystemExit(f"{args.annotate} is from {payload['generated_at']}, ledger ends at {ledger['updated_at']}")
        selections.annotate_rows(payload["rows"], ledger)
        args.annotate.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        print(f"annotated {args.annotate}")


if __name__ == "__main__":
    main()
