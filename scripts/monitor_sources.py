#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "conferences.json"
WATCHLIST = ROOT / "data" / "watchlist.json"
DEADLINES = ROOT / "data" / "submission_deadlines.json"
STATE = ROOT / "data" / "source-health.json"
CHANGES = ROOT / "CHANGES.md"
CHANGELOG = ROOT / "CHANGELOG.md"
USER_AGENT = "JapanEmergencyConferenceTracker/1.0 (+https://github.com/brianann2339/japan-em-conference-map)"
NORMALIZATION_VERSION = 2


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_sources(data_path: Path = DATA, watchlist_path: Path = WATCHLIST,
                 deadlines_path: Path | None = None) -> list[dict]:
    sources = [
        {
            "id": f'conference:{row["id"]}',
            "name": row["name"],
            "url": row["officialUrl"],
            "kind": "conference",
        }
        for row in load_json(data_path)
        if not row.get("archiveOnly")
    ]
    for row in load_json(watchlist_path):
        if row.get("manual"):
            continue
        sources.append({
            "id": f'watch:{row["id"]}',
            "name": row["name"],
            "url": row["url"],
            "kind": "watchlist",
        })
    deadlines_path = deadlines_path or data_path.with_name(DEADLINES.name)
    deadline_urls = set()
    for row in load_json(deadlines_path) if deadlines_path.exists() else []:
        key = (row["eventId"], row["officialUrl"])
        if key in deadline_urls:
            continue
        deadline_urls.add(key)
        url_hash = hashlib.sha256(row["officialUrl"].encode("utf-8")).hexdigest()[:10]
        sources.append({
            "id": f'deadline:{row["eventId"]}:{url_hash}',
            "name": f'{row["eventId"]} — 投稿資料',
            "url": row["officialUrl"],
            "kind": "deadline",
        })
    ids = [source["id"] for source in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("source IDs must be unique")
    return sources


def normalize_html(content: str) -> str:
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["head", "script", "style", "noscript", "svg"]):
        tag.decompose()
    text = unicodedata.normalize("NFKC", soup.get_text(" ", strip=True))
    return re.sub(r"\s+", " ", text).strip()


def content_hash(content: str) -> str:
    return hashlib.sha256(normalize_html(content).encode("utf-8")).hexdigest()


def fetch_url(url: str, timeout: int = 25) -> dict:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "ja,en;q=0.7"},
            timeout=timeout,
        )
    except requests.Timeout:
        return {"error": "timeout"}
    except requests.RequestException:
        return {"error": "request-error"}
    if not response.ok:
        return {
            "status": response.status_code,
            "finalUrl": response.url,
            "error": f"http-{response.status_code}",
        }
    return {
        "status": response.status_code,
        "finalUrl": response.url,
        "contentHash": content_hash(response.text),
        "error": None,
    }


def timestamp() -> str:
    return datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds")


def fingerprint(entry: Optional[dict]) -> tuple:
    if not entry:
        return ()
    return (
        entry.get("status"),
        entry.get("finalUrl"),
        entry.get("contentHash"),
        entry.get("error"),
    )


def observe(source: dict, previous: Optional[dict], fetcher: Callable[[str], dict], now: str) -> dict:
    result = fetcher(source["url"])
    if result.get("error") and previous and previous.get("contentHash"):
        entry = dict(previous)
        entry.update({
            "name": source["name"],
            "url": source["url"],
            "kind": source["kind"],
            "error": result["error"],
        })
        if result.get("status") is not None:
            entry["status"] = result["status"]
        if result.get("finalUrl"):
            entry["finalUrl"] = result["finalUrl"]
    else:
        entry = {
            "name": source["name"],
            "url": source["url"],
            "kind": source["kind"],
            "status": result.get("status"),
            "finalUrl": result.get("finalUrl", source["url"]),
            "contentHash": result.get("contentHash"),
            "error": result.get("error"),
        }
    if fingerprint(entry) != fingerprint(previous):
        entry["lastChangedAt"] = now
    elif previous and previous.get("lastChangedAt"):
        entry["lastChangedAt"] = previous["lastChangedAt"]
    return entry


def write_json_atomic(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def change_report(changed: list[dict], failures: list[dict], now: str) -> str:
    lines = ["# 官方來源監測結果", "", f"時間：{now}（Asia/Tokyo）", ""]
    if changed:
        lines.extend(["## 來源頁面狀態有變動", ""])
        lines.extend(f'- [{item["name"]}]({item["url"]})' for item in changed)
        lines.append("")
    if failures:
        lines.extend(["## 讀取失敗", ""])
        lines.extend(
            f'- [{item["name"]}]({item["url"]})：`{item["error"]}`'
            for item in failures
        )
        lines.append("")
    lines.append("來源變動只代表頁面內容或連線狀態不同；正式會議資料必須重新查證後才可更新。")
    return "\n".join(lines) + "\n"


def append_changelog(path: Path, changed: list[dict], now: str) -> None:
    if not changed:
        return
    lines = ["", f"## {now}（Asia/Tokyo）", "", "官方來源監測發現變動，待人工複核：", ""]
    lines.extend(f'- [{item["name"]}]({item["url"]})' for item in changed)
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def set_output(name: str, value: str) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def run_monitor(
    *,
    sources: list[dict],
    state_path: Path,
    changes_path: Path,
    changelog_path: Path,
    fetcher: Callable[[str], dict] = fetch_url,
    initialize: bool = False,
    now: Optional[str] = None,
) -> dict:
    now = now or timestamp()
    if initialize and state_path.exists():
        raise ValueError("source-health.json already exists; refusing to replace the baseline")
    if not initialize and not state_path.exists():
        raise ValueError("source-health.json is missing; run with --initialize first")
    previous_state = {} if initialize else load_json(state_path)
    previous = previous_state.get("sources", {})
    normalization_changed = (
        not initialize
        and previous_state.get("normalizationVersion") != NORMALIZATION_VERSION
    )
    current = {}
    changed = []
    failures = []
    new_failures = []

    for source in sources:
        old = previous.get(source["id"])
        entry = observe(source, old, fetcher, now)
        current[source["id"]] = entry
        if entry.get("error"):
            failures.append({**source, "error": entry["error"]})
            if initialize or fingerprint(entry) != fingerprint(old):
                new_failures.append({**source, "error": entry["error"]})
        if not initialize and not normalization_changed and fingerprint(entry) != fingerprint(old):
            changed.append(source)

    state = {
        "version": 1,
        "normalizationVersion": NORMALIZATION_VERSION,
        "sources": current,
    }
    state_changed = state != previous_state
    if initialize or state_changed:
        write_json_atomic(state_path, state)
    if changed or new_failures:
        changes_path.write_text(change_report(changed, new_failures, now), encoding="utf-8")
    if changed:
        append_changelog(changelog_path, changed, now)
    set_output("changed", "true" if changed else "false")
    set_output("failed", "true" if new_failures else "false")
    set_output("change_count", str(len(changed)))
    set_output("failure_count", str(len(new_failures)))
    return {"changed": changed, "failures": failures, "stateChanged": state_changed}


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--initialize", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = run_monitor(
        sources=load_sources(),
        state_path=STATE,
        changes_path=CHANGES,
        changelog_path=CHANGELOG,
        initialize=args.initialize,
    )
    print(
        f'monitored {len(load_sources())} sources; '
        f'{len(result["changed"])} changed; {len(result["failures"])} failed'
    )


if __name__ == "__main__":
    main()
