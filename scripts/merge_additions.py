#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "conferences.json"
ADDITIONS = ROOT / "data" / "additions"


def load(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"{path} must contain a JSON array")
    return value


def main() -> None:
    rows = load(DATA)
    by_id = {row["id"]: row for row in rows}
    if len(by_id) != len(rows):
        raise ValueError("base data contains duplicate IDs")

    added = 0
    for path in sorted(ADDITIONS.glob("*.json")):
        for row in load(path):
            existing = by_id.get(row["id"])
            if existing is None:
                by_id[row["id"]] = row
                added += 1
            elif existing != row:
                raise ValueError(f"conflicting record for {row['id']} in {path.name}")

    merged = sorted(by_id.values(), key=lambda row: (row["start"], row["name"]))
    temp = DATA.with_suffix(".json.tmp")
    temp.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(DATA)
    print(f"merged {added} additions; {len(merged)} total conferences")


if __name__ == "__main__":
    main()
