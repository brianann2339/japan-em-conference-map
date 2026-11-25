#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path

from render import load_deadlines, load_events, load_watchlist, write_site


ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
DIST = ROOT / "dist"


def reset_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def main() -> None:
    events = load_events(ROOT / "data" / "conferences.json")
    watchlist = load_watchlist(ROOT / "data" / "watchlist.json")
    deadlines = load_deadlines(ROOT / "data" / "submission_deadlines.json")
    map_svg = (ROOT / "assets" / "map-full.svg").read_text(encoding="utf-8")
    license_text = (ROOT / "MAP-LICENSE.md").read_text(encoding="utf-8")

    reset_directory(DOCS)
    write_site(events, map_svg, DOCS, license_text, watchlist=watchlist, deadlines=deadlines)
    reset_directory(DIST)
    shutil.copytree(DOCS, DIST, dirs_exist_ok=True)


if __name__ == "__main__":
    main()
