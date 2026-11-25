#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "conferences.json"
TRANSLATIONS = ROOT / "data" / "conference_names_zh-Hant.json"
SOURCES = ROOT / "data" / "history_sources"
ADDITION = ROOT / "data" / "additions" / "history-2025-2026.json"
CUTOFF = date(2026, 11, 25)
REGIONS = {
    "北海道": "北海道",
    **{f"{name}県": "東北" for name in ("青森", "岩手", "宮城", "秋田", "山形", "福島")},
    **{f"{name}県": "關東" for name in ("茨城", "栃木", "群馬", "埼玉", "千葉", "神奈川")},
    "東京都": "關東",
    **{f"{name}県": "中部" for name in ("新潟", "富山", "石川", "福井", "山梨", "長野", "岐阜", "静岡", "愛知")},
    **{f"{name}県": "近畿" for name in ("三重", "滋賀", "兵庫", "奈良", "和歌山")},
    "京都府": "近畿",
    "大阪府": "近畿",
    **{f"{name}県": "中國" for name in ("鳥取", "島根", "岡山", "広島", "山口")},
    **{f"{name}県": "四國" for name in ("徳島", "香川", "愛媛", "高知")},
    **{f"{name}県": "九州" for name in ("福岡", "佐賀", "長崎", "熊本", "大分", "宮崎", "鹿児島")},
    "沖縄県": "沖繩",
    "線上": "線上",
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def expected_queries(events: list[dict]) -> set[tuple[str, int]]:
    result = set()
    for event in events:
        years = [2025] if event["start"].startswith("2026") else [2025, 2026]
        result.update((event["societyCode"], year) for year in years)
    return result


def validate_event(event: dict, name_zh: str, query: tuple[str, int], topics: dict) -> dict:
    required = {
        "id", "societyCode", "name", "start", "end", "city", "prefecture", "region",
        "venue", "topic", "topicKey", "officialUrl", "sourceCheckedAt", "archiveOnly",
    }
    missing = required - event.keys()
    if missing:
        raise ValueError(f"{query} event missing {sorted(missing)}")
    if not name_zh.strip():
        raise ValueError(f"{query} has empty translation")
    if event["societyCode"] != query[0] or int(event["start"][:4]) != query[1]:
        raise ValueError(f"{query} does not match event {event['id']}")
    if date.fromisoformat(event["end"]) >= CUTOFF:
        raise ValueError(f"{event['id']} was not finished before {CUTOFF}")
    if event.get("archiveOnly") is not True:
        raise ValueError(f"{event['id']} must be archiveOnly")
    if (event["topic"], event["topicKey"]) != topics[event["societyCode"]]:
        raise ValueError(f"{event['id']} topic differs from current series")
    event = dict(event)
    event["prefecture"] = event["prefecture"].replace("縣", "県")
    expected_region = REGIONS.get(event["prefecture"])
    if not expected_region:
        raise ValueError(f"{event['id']} has unsupported prefecture {event['prefecture']}")
    event["region"] = expected_region
    return event


def main() -> None:
    existing = load(DATA)
    current = [event for event in existing if not event.get("archiveOnly")]
    topics = {event["societyCode"]: (event["topic"], event["topicKey"]) for event in current}
    queries = {}
    history = []
    names = {}
    allowed_statuses = {"confirmed", "not_held", "not_found", "not_expired"}

    for path in sorted(SOURCES.glob("batch*.json")):
        for item in load(path):
            query = (item["query"]["societyCode"], int(item["query"]["year"]))
            if query in queries:
                raise ValueError(f"duplicate query {query} in {path.name} and {queries[query]}")
            queries[query] = path.name
            if item["status"] not in allowed_statuses:
                raise ValueError(f"unsupported status {item['status']} for {query}")
            candidates = []
            if item["status"] == "confirmed":
                candidates.append(item)
            candidates.extend(item.get("additionalEvents", []))
            for candidate in candidates:
                if not candidate.get("evidence"):
                    raise ValueError(f"{query} has no source evidence")
                event = validate_event(candidate["event"], candidate["nameZh"], query, topics)
                if event["id"] in names:
                    raise ValueError(f"duplicate history id {event['id']}")
                history.append(event)
                names[event["id"]] = candidate["nameZh"]

    expected = expected_queries(current)
    if set(queries) != expected:
        missing = sorted(expected - set(queries))
        extra = sorted(set(queries) - expected)
        raise ValueError(f"history query coverage differs; missing={missing}, extra={extra}")

    history.sort(key=lambda event: (event["start"], event["id"]))
    all_events = history + current
    base_names = load(TRANSLATIONS)
    translations = {
        event["id"]: names[event["id"]] if event["id"] in names else base_names[event["id"]]
        for event in all_events
    }
    ADDITION.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DATA.write_text(json.dumps(all_events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    TRANSLATIONS.write_text(json.dumps(translations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"queries={len(queries)} history={len(history)} current={len(current)} total={len(all_events)}")


if __name__ == "__main__":
    main()
