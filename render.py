#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


TOPIC_HUES = {
    "emergency": "#c4283c",
    "ems": "#1f6f78",
    "disaster": "#33518c",
    "trauma": "#9d3a2e",
    "critical": "#2f6a56",
    "infection": "#8a6820",
    "burn": "#a8562b",
    "pediatric": "#5c4b8a",
    "toxicology": "#526b73",
    "resuscitation": "#b7374c",
    "shock": "#7c3e4d",
    "nursing": "#7b567f",
    "respiratory": "#32717b",
    "transport": "#2d6570",
    "cardiology": "#9f3540",
    "neuro": "#4a5f91",
    "pocus": "#5a6f3b",
    "radiology": "#805c2b",
    "coagulation": "#6d456d",
    "environment": "#2f6a56",
    "sports": "#3d698f",
}

MONTH_ABBR = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"]
REQUIRED_FIELDS = {
    "id", "name", "start", "end", "city", "prefecture", "region", "venue",
    "mapVenue", "topic", "topicKey", "lat", "lng", "mapPrecision",
    "officialUrl", "mapSourceUrl", "sourceCheckedAt", "societyCode",
}


def load_events(path: Path) -> list[dict]:
    events = json.loads(path.read_text(encoding="utf-8"))
    validate_events(events)
    return events


def validate_events(events: list[dict]) -> None:
    if not isinstance(events, list) or not events:
        raise ValueError("conference data must be a non-empty list")
    seen = set()
    for index, event in enumerate(events, start=1):
        missing = REQUIRED_FIELDS - event.keys()
        if missing:
            raise ValueError(f"record {index} missing fields: {', '.join(sorted(missing))}")
        if event["id"] in seen:
            raise ValueError(f"duplicate id: {event['id']}")
        seen.add(event["id"])
        if not re.fullmatch(r"[A-Z0-9-]+", event["societyCode"]):
            raise ValueError(f"invalid societyCode: {event['id']}")
        start = date.fromisoformat(event["start"])
        end = date.fromisoformat(event["end"])
        date.fromisoformat(event["sourceCheckedAt"])
        if start > end:
            raise ValueError(f"start after end: {event['id']}")
        if event["mapPrecision"] not in {"venue", "complex"}:
            raise ValueError(f"unsupported mapPrecision: {event['id']}")
        if not (-90 <= event["lat"] <= 90 and -180 <= event["lng"] <= 180):
            raise ValueError(f"coordinate out of range: {event['id']}")


def prepare(events: list[dict]) -> list[dict]:
    rows = []
    for event in events:
        row = dict(event)
        row["society"] = event["societyCode"]
        row["_start"] = date.fromisoformat(event["start"])
        row["_end"] = date.fromisoformat(event["end"])
        row["_year"] = row["_start"].year
        row["_month"] = row["_start"].month
        rows.append(row)
    return sorted(rows, key=lambda row: (row["_start"], row["name"]))


def tokyo_today() -> date:
    return datetime.now(ZoneInfo("Asia/Tokyo")).date()


def is_past(row: dict, today: date) -> bool:
    return row["_end"] < today


def split_archive(rows: list[dict], today: date) -> tuple[list[dict], list[dict]]:
    return (
        [row for row in rows if not is_past(row, today)],
        [row for row in rows if is_past(row, today)],
    )


def next_up(rows: list[dict], today: date) -> dict | None:
    return next((row for row in rows if row["_end"] >= today), None)


def society_code(row: dict) -> str:
    return row["society"]


def color_for(row: dict) -> str:
    return TOPIC_HUES.get(row["topicKey"], "#526b73")


def date_range(row: dict) -> str:
    if row["start"] == row["end"]:
        return row["start"]
    return f'{row["start"]} – {row["end"]}'


def short_date_range(row: dict) -> str:
    start = row["_start"]
    end = row["_end"]
    if start == end:
        return f"{start.month}/{start.day}"
    if start.month == end.month:
        return f"{start.month}/{start.day}–{end.day}"
    return f"{start.month}/{start.day}–{end.month}/{end.day}"


def location_text(row: dict) -> str:
    if row["city"].startswith(row["prefecture"]):
        return row["city"]
    return f'{row["prefecture"]} · {row["city"]}'


def source_checked_at(events: list[dict]) -> str:
    return max(event["sourceCheckedAt"] for event in events)


def assign_lanes(rows: list[dict]) -> dict[str, int]:
    lanes: list[set[int]] = []
    result = {}
    for row in rows:
        month = row["_month"]
        for lane, occupied in enumerate(lanes):
            if month not in occupied:
                occupied.add(month)
                result[row["id"]] = lane
                break
        else:
            lanes.append({month})
            result[row["id"]] = len(lanes) - 1
    return result


def band(row: dict) -> str:
    code = society_code(row)
    topic = row["topic"]
    color = color_for(row)
    return (
        f'<span class="code-block" style="color:{color};border-color:{color}">'
        f'<b>{html.escape(code)}</b><small>{html.escape(topic)}</small></span>'
    )


ICON_CAL = (
    '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" '
    'aria-hidden="true"><rect x="1.8" y="3.2" width="12.4" height="11" rx="1"/>'
    '<path d="M1.8 6.6h12.4M5 1.8v2.6M11 1.8v2.6"/></svg>'
)
ICON_PIN = (
    '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" '
    'aria-hidden="true"><path d="M8 14.5s5-4.6 5-8.2A5 5 0 0 0 3 6.3c0 3.6 5 8.2 5 8.2Z"/>'
    '<circle cx="8" cy="6.2" r="1.9"/></svg>'
)


def build_ics(rows: list[dict], stamp_day: str) -> str:
    stamp = date.fromisoformat(stamp_day).strftime("%Y%m%dT000000Z")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Japan Emergency Conference Tracker//TW//ZH-Hant",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:日本急診相關醫學會議",
        "X-WR-TIMEZONE:Asia/Tokyo",
    ]
    for row in rows:
        uid = hashlib.sha256(row["id"].encode()).hexdigest()[:24] + "@japan-em-conference"
        dtend = row["_end"] + timedelta(days=1)
        description = f'{row["topic"]}\\n官方來源：{row["officialUrl"]}'
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{stamp}",
            f'DTSTART;VALUE=DATE:{row["_start"].strftime("%Y%m%d")}',
            f'DTEND;VALUE=DATE:{dtend.strftime("%Y%m%d")}',
            f'SUMMARY:{ics_escape(society_code(row) + " — " + row["name"])}',
            f'LOCATION:{ics_escape(location_text(row) + " · " + row["venue"])}',
            f'DESCRIPTION:{ics_escape(description)}',
            f'URL:{row["officialUrl"]}',
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ])
    lines.append("END:VCALENDAR")
    return "\r\n".join(part for line in lines for part in fold_ics_line(line)) + "\r\n"


def ics_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold_ics_line(line: str) -> list[str]:
    parts = []
    current = ""
    size = 0
    for char in line:
        char_size = len(char.encode("utf-8"))
        if size + char_size > 75:
            parts.append(current)
            current = " " + char
            size = 1 + char_size
        else:
            current += char
            size += char_size
    parts.append(current)
    return parts


def build_csv(events: list[dict]) -> str:
    fields = list(dict.fromkeys(key for event in events for key in event))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for event in events:
        writer.writerow(event)
    return "\ufeff" + stream.getvalue()


def deadline_data(rows: list[dict]) -> list[dict]:
    return []


CSS = """
:root{
  --paper:#e8edef; --surface:#fdfdfc; --ink:#13222a; --muted:#5f747e;
  --rule:#c6d1d6; --rule-soft:#dde5e8;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:Newsreader,"Iowan Old Style","Source Serif 4",Georgia,
              "Noto Serif TC","Noto Serif JP","PingFang TC","Microsoft JhengHei",serif;
  font-size:17px; line-height:1.55; font-variant-numeric:tabular-nums;
}
.wrap{max-width:1080px; margin:0 auto; padding:2.5rem 1.5rem 5rem}
a{color:inherit; text-decoration-thickness:1px; text-underline-offset:2px}
a:focus-visible,button:focus-visible{outline:2px solid var(--ink); outline-offset:3px}
.masthead{display:flex; justify-content:space-between; align-items:baseline;
  gap:1rem; flex-wrap:wrap; border-bottom:1px solid var(--ink); padding-bottom:.6rem}
.masthead h1{font-size:1.5rem; font-weight:600; margin:0; letter-spacing:.01em}
.masthead .stamp{color:var(--muted); font-size:.85rem}
.intro{margin:.65rem 0 0; color:var(--muted); font-size:.95rem; line-height:1.6; max-width:55rem}
.hero{margin:2.6rem 0 3rem}
.hero .lede{color:var(--muted); font-size:.95rem; margin:0 0 .5rem}
.hero .title{font-size:clamp(1.7rem,4.4vw,2.6rem); line-height:1.2;
  font-weight:300; margin:0 0 .7rem; max-width:28ch}
.hero .meta{font-size:1.05rem; margin:0}
.hero .count{color:var(--muted); font-size:.95rem; margin:.55rem 0 0}
.hero .count b{color:var(--ink); font-weight:600; font-size:1.25rem}
h2{font-size:1.05rem; font-weight:600; margin:0 0 1rem;
   padding-bottom:.35rem; border-bottom:1px solid var(--rule)}
.grid{background:var(--surface); border:1px solid var(--rule); padding:1rem .9rem 1.2rem;
      overflow-x:auto}
.gridrow{display:grid; grid-template-columns:3.4rem repeat(12,1fr);
  column-gap:2px; row-gap:3px; min-width:640px}
.months{margin-bottom:.4rem; border-bottom:1px solid var(--rule-soft); padding-bottom:.3rem}
.months span{font-size:.72rem; color:var(--muted); text-align:center}
.months span:first-child{text-align:left}
.yr{font-size:.9rem; color:var(--muted); align-self:center}
.yr.now{color:var(--ink); font-weight:600}
.bar{grid-row:auto; border-left:3px solid currentColor; background:#fff;
  padding:.18rem .35rem; font-size:.73rem; line-height:1.25; min-width:0;
  border-top:1px solid var(--rule-soft); border-right:1px solid var(--rule-soft);
  border-bottom:1px solid var(--rule-soft)}
.bar b{display:block; font-weight:600; font-size:.78rem}
.bar span{color:var(--muted); display:block; white-space:nowrap;
  overflow:hidden; text-overflow:ellipsis}
.yearband{grid-column:1/-1; height:1px; background:var(--rule-soft); margin:.25rem 0}
.legend{display:flex; gap:.6rem 1.4rem; flex-wrap:wrap; margin:1rem 0 0; font-size:.8rem}
.legend span{display:flex; align-items:center; gap:.55rem;
  border-left:3px solid currentColor; padding:.2rem 0 .2rem .55rem}
.legend .lg-txt{display:flex; flex-direction:column; line-height:1.25}
.legend .lg-txt b{font-weight:600; font-size:.82rem}
.legend em{font-style:normal; color:var(--muted)}
.cards{display:grid; grid-template-columns:repeat(auto-fill,minmax(232px,1fr));
  gap:1.6rem 1.3rem; margin-top:.3rem}
.card{display:block; color:inherit; text-decoration:none; min-width:0}
.card .band{aspect-ratio:16/10; display:flex; align-items:center;
  justify-content:center; padding:1.1rem; position:relative;
  border:1px solid var(--rule); background:#fff}
.code-block{width:100%; min-height:6rem; display:flex; flex-direction:column;
  align-items:center; justify-content:center; gap:.3rem; border-top:5px solid currentColor;
  background:linear-gradient(180deg,currentColor 0 5px,#fff 5px 100%)}
.code-block b{font-family:"Inter","Helvetica Neue",Arial,sans-serif;
  font-size:1.55rem; letter-spacing:.04em; line-height:1}
.code-block small{font-size:.76rem; color:var(--muted); letter-spacing:.02em; text-align:center}
.card .band em{position:absolute; right:.45rem; bottom:.35rem; font-style:normal;
  font-size:.72rem; color:var(--muted)}
.card .soc-line{display:block; font-size:.76rem; font-weight:600;
  margin:.6rem 0 -.35rem}
.card .card-title{display:block; font-weight:600; font-size:1rem; line-height:1.3;
  margin:.7rem 0 .45rem}
.card:hover .card-title,.card:focus-visible .card-title{text-decoration:underline}
.card .meta{display:flex; align-items:flex-start; gap:.4rem;
  font-size:.88rem; color:var(--muted); margin:.18rem 0}
.card .meta svg{flex:0 0 auto; width:.9rem; height:.9rem; margin-top:.22rem}
.card .meta .place{color:var(--ink)}
.card .venue{display:block; color:var(--muted); font-size:.78rem; line-height:1.35; margin-top:.12rem}
.card .precision{display:block; color:#7a5525; font-size:.76rem; margin-top:.28rem}
.card.past{opacity:.52}
.archive-link{margin:2rem 0 0; font-size:.9rem}
.archive-link a{color:var(--muted)}
.archive-link a:hover{color:var(--ink)}
.dl{background:var(--surface); border:1px solid var(--rule); padding:.2rem 1rem .8rem}
.dl ol{list-style:none; margin:0; padding:0}
.dl li{display:grid; grid-template-columns:6rem 1fr auto; gap:.8rem;
  align-items:baseline; padding:.6rem 0; border-bottom:1px solid var(--rule-soft)}
.dl li:last-child{border-bottom:0}
.dl .when{font-size:.88rem; color:var(--muted); white-space:nowrap}
.dl .what b{font-weight:600}
.dl .what span{color:var(--muted); font-size:.85rem; display:block}
.dl .left{font-size:.85rem; white-space:nowrap; text-align:right}
.dl li.tba .when,.dl li.tba .left{color:var(--muted); font-style:italic}
.dl .note{margin:.7rem 0 0; font-size:.8rem; color:var(--muted)}
footer{margin-top:3.5rem; padding-top:1rem; border-top:1px solid var(--rule);
  font-size:.82rem; color:var(--muted)}
footer p{margin:.35rem 0}
footer ul{margin:.4rem 0; padding-left:1.1rem}
.template-credit{margin:1.25rem 0; padding:.75rem .9rem; color:var(--ink);
  border-left:4px solid #1d3550; background:rgba(255,255,255,.58)}
.license-note{font-size:.78rem}
@media (max-width:640px){
  body{font-size:16px}
  .wrap{padding:1.6rem 1rem 3rem}
  .dl li{grid-template-columns:5.5rem 1fr; gap:.5rem}
  .dl .left{display:none}
}
"""


MAP_CSS = """
.worldmap{margin:2.2rem 0 2.6rem}
.wm-head{display:flex; justify-content:space-between; align-items:flex-end; gap:1rem;
  flex-wrap:wrap; border-bottom:1px solid var(--rule); margin-bottom:1rem; padding-bottom:.35rem}
.worldmap h2{border:0; margin:0; padding:0; font-size:1.35rem; letter-spacing:.02em}
.wm-tabs{display:flex; gap:.3rem; flex-wrap:wrap}
.wm-tabs button{font:inherit; font-size:.82rem; padding:.18rem .6rem; cursor:pointer;
  border:1px solid var(--rule); background:var(--surface); color:var(--muted); border-radius:2px}
.wm-tabs button[aria-pressed="true"]{background:#1d3550; border-color:#1d3550; color:#fff}
.wm-board{background:#b0a497; border-radius:14px; padding:1.1rem 1.1rem 1.2rem;
  background-image:radial-gradient(rgba(255,255,255,.09) 1px,transparent 1.3px),
    radial-gradient(rgba(0,0,0,.07) 1px,transparent 1.3px);
  background-size:5px 5px,7px 7px; background-position:0 0,2px 3px;
  box-shadow:inset 0 0 0 1px rgba(0,0,0,.08),0 2px 10px rgba(19,34,42,.12);
  font-family:"Inter","Helvetica Neue",Arial,"Noto Sans JP","Noto Sans TC",sans-serif}
.m-svg{display:block; width:100%; height:auto; max-height:670px}
.m-year[hidden]{display:none}
.jp-map .prefecture{fill:#1e262d!important; stroke:#b0a497!important;
  stroke-width:1.15!important; stroke-linejoin:round!important}
.jp-map .boundary-line{stroke:#b0a497!important}
.m-lead{stroke:#fbf8f3; stroke-width:1.5}
.m-card{fill:#fbfaf7; filter:url(#m-shadow)}
.m-t{font-size:14px; font-weight:700; fill:#13222a}
.m-s{font-size:10.5px; fill:#26333b}
.m-pole{stroke:#e9e2d6; stroke-width:1.8}
.m-knob{fill:#d9ab33; stroke:#6e5414; stroke-width:.6}
.m-base{fill:rgba(0,0,0,.52)}
.m-flagface{fill:#fff; stroke-width:2; filter:url(#m-shadow)}
.m-flag-txt{font-size:10px; font-weight:700}
.m-flag{cursor:pointer; transition:transform .12s}
.m-callout,.m-lead{opacity:0; pointer-events:none; transition:opacity .12s}
.m-item:hover .m-callout,.m-item:hover .m-lead,
.m-item:focus .m-callout,.m-item:focus .m-lead{opacity:1}
.m-item:hover .m-flag,.m-item:focus .m-flag{transform:scale(1.25)}
.m-item:hover .m-flagface,.m-item:focus .m-flagface{stroke-width:2.8}
.m-item:focus{outline:none}
.ms-strip{display:flex; gap:.9rem; margin-top:.9rem; align-items:stretch}
.ms-strip[hidden]{display:none}
.ms-flag{flex:0 0 auto; display:flex; align-items:center; gap:.6rem; color:#fff;
  background:#1d3550; padding:.6rem 1.6rem .6rem .9rem; font-size:.82rem; line-height:1.2;
  clip-path:polygon(0 0,calc(100% - 14px) 0,100% 50%,calc(100% - 14px) 100%,0 100%);
  border-radius:6px 0 0 6px}
.ms-flag svg{width:1.7rem; height:1.7rem; stroke:#fff}
.ms-flag b{display:block; font-size:1.55rem; font-weight:700; margin-top:.1rem}
.ms-cells{flex:1; display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr));
  background:#fbfaf7; border-radius:6px; box-shadow:0 1px 4px rgba(0,0,0,.18)}
.ms-cell{display:block; padding:.55rem .8rem .6rem; text-decoration:none; color:#13222a;
  border-left:1px solid #ddd6cc; border-top:1px solid #ddd6cc; min-width:0}
.ms-cell b{display:block; font-size:.95rem; font-weight:700; padding-left:.55rem;
  border-left:4px solid var(--c); margin-bottom:.25rem; line-height:1.15}
.ms-cell span{display:flex; align-items:center; gap:.35rem; font-size:.78rem; color:#33414a;
  line-height:1.3; margin-top:.12rem}
.ms-cell span svg{flex:0 0 auto; width:.8rem; height:.8rem}
.ms-cell:hover b{text-decoration:underline}
.wm-note{font-size:.78rem; color:var(--muted); margin:.5rem 0 0}
.m-stage{position:relative; overflow:hidden; border-radius:6px}
.m-stage .m-svg{touch-action:pan-y; user-select:none; -webkit-user-select:none}
.m-stage.zoomed .m-svg{touch-action:none; cursor:grab}
.m-stage.zoomed .m-svg:active{cursor:grabbing}
.jp-map .prefecture,.m-lead,.m-pole{vector-effect:non-scaling-stroke}
.m-zoom{position:absolute; right:.5rem; top:.5rem; z-index:2; display:flex; flex-direction:column;
  border-radius:6px; overflow:hidden; box-shadow:0 1px 4px rgba(0,0,0,.3)}
.m-zoom button{font:600 1.05rem/1 "Inter","Helvetica Neue",Arial,sans-serif; width:2rem; height:2rem;
  border:0; border-top:1px solid #ddd6cc; background:#fbfaf7; color:#13222a; cursor:pointer}
.m-zoom button:first-child{border-top:0}
.m-zoom button:hover{background:#fff}
.m-zoom button:focus-visible{outline:2px solid #1d3550; outline-offset:-2px}
@media (max-width:700px){
  .wm-board{padding:.6rem; border-radius:10px}
  .m-callout,.m-lead{display:none}
  .m-flag{transform:scale(1.45)}
  .ms-strip{flex-direction:column}
  .ms-flag{clip-path:none; border-radius:6px; padding:.5rem .8rem}
  .ms-flag b{display:inline; font-size:1.1rem; margin-left:.3rem}
  .ms-flag br{display:none}
  .ms-cell{border-left:0; border-top:1px solid #ddd6cc}
  .ms-cell:first-child{border-top:0}
  .m-zoom{right:.3rem; top:auto; bottom:.3rem; opacity:.92}
  .m-zoom button{width:1.7rem; height:1.7rem; font-size:.9rem}
}
"""


def conference_cards(rows: list[dict], today: date) -> str:
    cards = []
    for row in rows:
        color = color_for(row)
        past = is_past(row, today)
        precision = (
            f'<span class="precision">{html.escape(row.get("mapNote") or "地圖點為園區代表位置")}</span>'
            if row["mapPrecision"] == "complex" else ""
        )
        cards.append(
            f'<a class="card{" past" if past else ""}" href="{html.escape(row["officialUrl"])}" '
            f'target="_blank" rel="noopener">'
            f'<span class="band">{band(row)}<em>{row["_year"]}</em></span>'
            f'<span class="soc-line" style="color:{color}">{html.escape(society_code(row))} · '
            f'{html.escape(row["topic"])}</span>'
            f'<span class="card-title">{html.escape(row["name"])}</span>'
            f'<span class="meta" style="color:{color}">{ICON_CAL}'
            f'<span>{html.escape(date_range(row))}</span></span>'
            f'<span class="meta" style="color:{color}">{ICON_PIN}'
            f'<span class="place">{html.escape(location_text(row))}'
            f'<span class="venue">{html.escape(row["venue"])}</span>{precision}</span></span>'
            f'</a>'
        )
    return '<div class="cards">' + "".join(cards) + "</div>"


def season_grid(rows: list[dict], today: date) -> str:
    years = sorted({row["_year"] for row in rows})
    months = '<div class="gridrow months"><span>月份</span>' + "".join(
        f"<span>{month}</span>" for month in MONTH_ABBR
    ) + "</div>"
    bands = []
    for year in years:
        year_rows = [row for row in rows if row["_year"] == year]
        lanes = assign_lanes(year_rows)
        lane_count = max(lanes.values(), default=0) + 1
        bars = []
        for row in year_rows:
            lane = lanes[row["id"]] + 1
            color = color_for(row)
            bars.append(
                f'<div class="bar" style="grid-column:{row["_month"] + 1};grid-row:{lane};'
                f'color:{color}" title="{html.escape(row["name"])}">'
                f'<b>{html.escape(society_code(row))}</b>'
                f'<span>{html.escape(short_date_range(row))}</span>'
                f'<span>{html.escape(row["city"])}</span></div>'
            )
        now = " now" if year == today.year else ""
        bands.append(
            f'<div class="gridrow"><span class="yr{now}" style="grid-row:span {lane_count}">{year}</span>'
            + "".join(bars) + "</div>"
        )

    legend_rows = {}
    for row in rows:
        legend_rows.setdefault(row["society"], row)
    legend = "".join(
        f'<span style="color:{color_for(row)}"><span class="lg-txt">'
        f'<b>{html.escape(code)}</b><em>{html.escape(row["topic"])}</em>'
        f'</span></span>'
        for code, row in legend_rows.items()
    )
    return f'<div class="grid">{months}{"".join(bands)}</div><p class="legend">{legend}</p>'


def deadline_section(rows: list[dict]) -> str:
    return (
        '<div class="dl"><p class="note">目前沒有官方已確認的投稿截止日期。'
        '未確認日期不會寫入 ICS 行事曆；來源頁已納入每日變動監測，'
        '確認公告後才會顯示。</p></div>'
    )


def extract_svg_inner(svg_text: str) -> str:
    match = re.search(r"<svg[^>]*>(.*)</svg>\s*$", svg_text, re.S)
    if not match:
        raise ValueError("map-full.svg has no SVG root")
    return match.group(1)


def project(lat: float, lng: float) -> tuple[float, float]:
    # map-full.svg 是斜向排版；仿射校準讓經緯度落在同一張原始 SVG 上，錨點不另行錯開。
    x = 50.9356161 * lng - 1.28151287 * lat - 6482.24677
    y = 1.62873639 * lng - 63.3232243 * lat + 2702.51930
    return x, y


def coordinate_groups(rows: list[dict]) -> list[list[dict]]:
    groups: dict[tuple[float, float], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(round(row["lat"], 6), round(row["lng"], 6))].append(row)
    return list(groups.values())


def truncate_map_name(value: str, limit: int = 19) -> str:
    return value if len(value) <= limit else value[:limit] + "…"


def map_marker(group: list[dict]) -> str:
    first = group[0]
    x, y = project(first["lat"], first["lng"])
    color = color_for(first) if len({row["society"] for row in group}) == 1 else "#1d3550"
    label = society_code(first) if len(group) == 1 else f'{society_code(first)}+{len(group) - 1}'
    face_width = max(42, len(label) * 7 + 14)
    face_x = x - face_width / 2
    callout_width = 286
    callout_height = 34 + len(group) * 31
    callout_x = x + 28 if x < 500 else x - callout_width - 28
    callout_x = max(5, min(1000 - callout_width - 5, callout_x))
    callout_y = max(5, min(1000 - callout_height - 5, y - callout_height / 2))
    leader_x = callout_x if callout_x > x else callout_x + callout_width
    title = f'{first["mapVenue"]} · {len(group)} 場' if len(group) > 1 else first["mapVenue"]
    lines = []
    for index, row in enumerate(group):
        line_y = callout_y + 42 + index * 31
        lines.append(
            f'<rect x="{callout_x + 10:.1f}" y="{line_y - 14:.1f}" width="4" height="18" '
            f'rx="1" fill="{color_for(row)}"/>'
            f'<text x="{callout_x + 21:.1f}" y="{line_y - 2:.1f}" class="m-t">'
            f'{html.escape(society_code(row))} · {html.escape(truncate_map_name(row["name"]))}</text>'
            f'<text x="{callout_x + 21:.1f}" y="{line_y + 12:.1f}" class="m-s">'
            f'{html.escape(short_date_range(row))} · {html.escape(row["city"])}</text>'
        )
    description = "；".join(f'{society_code(row)} {row["name"]}' for row in group)
    return (
        f'<a href="{html.escape(first["officialUrl"])}" class="m-item" '
        f'data-location-count="{len(group)}" aria-label="{html.escape(description)}">'
        f'<title>{html.escape(description)}</title>'
        f'<line x1="{x:.1f}" y1="{y - 18:.1f}" x2="{leader_x:.1f}" '
        f'y2="{callout_y + callout_height / 2:.1f}" class="m-lead"/>'
        f'<g class="m-callout"><rect x="{callout_x:.1f}" y="{callout_y:.1f}" '
        f'width="{callout_width}" height="{callout_height}" rx="5" class="m-card"/>'
        f'<text x="{callout_x + 12:.1f}" y="{callout_y + 21:.1f}" class="m-s">'
        f'{html.escape(title)}</text>{"".join(lines)}</g>'
        f'<g class="m-z" data-x="{x:.1f}" data-y="{y:.1f}"><g class="m-flag">'
        f'<line x1="{x:.1f}" y1="{y - 44:.1f}" x2="{x:.1f}" y2="{y:.1f}" class="m-pole"/>'
        f'<circle cx="{x:.1f}" cy="{y - 45:.1f}" r="3.2" class="m-knob"/>'
        f'<ellipse cx="{x:.1f}" cy="{y + 2:.1f}" rx="7" ry="3" class="m-base"/>'
        f'<rect x="{face_x:.1f}" y="{y - 40:.1f}" width="{face_width}" height="24" rx="2" '
        f'class="m-flagface" stroke="{color}"/>'
        f'<text x="{x:.1f}" y="{y - 24:.1f}" text-anchor="middle" class="m-flag-txt" '
        f'fill="{color}">{html.escape(label)}</text></g></g></a>'
    )


def map_strip(year: int, rows: list[dict]) -> str:
    cells = []
    for row in rows:
        cells.append(
            f'<a class="ms-cell" href="{html.escape(row["officialUrl"])}" '
            f'target="_blank" rel="noopener" style="--c:{color_for(row)}">'
            f'<b>{html.escape(society_code(row))}</b>'
            f'<span>{ICON_PIN}{html.escape(row["city"])}</span>'
            f'<span>{ICON_CAL}{html.escape(short_date_range(row))}</span></a>'
        )
    return (
        f'<div class="ms-strip" data-year="{year}"><div class="ms-flag">{ICON_CAL}'
        f'<span>Upcoming<br>Japan Conferences <b>{year}</b></span></div>'
        f'<div class="ms-cells">{"".join(cells)}</div></div>'
    )


ZOOM_CONTROLS = (
    '<div class="m-zoom" role="group" aria-label="地圖縮放">'
    '<button type="button" data-z="in" aria-label="放大">+</button>'
    '<button type="button" data-z="out" aria-label="縮小">−</button>'
    '<button type="button" data-z="reset" aria-label="還原" title="還原">⤢</button></div>'
)


def japan_map_section(rows: list[dict], map_svg: str) -> str:
    years = sorted({row["_year"] for row in rows})
    if not years:
        return ""
    active_year = years[0]
    tabs = "".join(
        f'<button type="button" data-year="{year}" data-title="{year}" '
        f'aria-pressed="{"true" if year == active_year else "false"}">{year}</button>'
        for year in years
    )
    map_years = []
    strips = []
    for year in years:
        year_rows = [row for row in rows if row["_year"] == year]
        markers = "".join(map_marker(group) for group in coordinate_groups(year_rows))
        hidden = "" if year == active_year else " hidden"
        map_years.append(f'<g class="m-year" data-year="{year}"{hidden}>{markers}</g>')
        strip = map_strip(year, year_rows)
        if hidden:
            strip = strip.replace(f'data-year="{year}"', f'data-year="{year}" hidden', 1)
        strips.append(strip)
    svg_inner = extract_svg_inner(map_svg)
    svg = (
        '<svg class="m-svg jp-map geolonia-svg-map" viewBox="0 0 1000 1000" '
        'role="img" aria-label="日本急診相關醫學會議地圖">'
        '<defs><filter id="m-shadow" x="-10%" y="-10%" width="120%" height="140%">'
        '<feDropShadow dx="0" dy="1.5" stdDeviation="1.6" flood-opacity=".28"/>'
        '</filter></defs><g class="m-layer">'
        f'{svg_inner}{"".join(map_years)}</g></svg>'
    )
    return (
        '<section class="worldmap" aria-labelledby="wm-title">'
        '<div class="wm-head"><h2 id="wm-title">日本急診相關醫學會議地圖 '
        f'<span class="wm-year">{active_year}</span></h2>'
        f'<div class="wm-tabs" role="group" aria-label="選擇年份">{tabs}</div></div>'
        f'<div class="wm-board"><div class="m-stage">{ZOOM_CONTROLS}{svg}</div>{"".join(strips)}</div>'
        '<p class="wm-note">旗桿底端對應會場座標；滑鼠移到旗子或以鍵盤聚焦可看會議資訊，'
        '下方每場會議分開列示。同座標的會議共用旗子，沒有用假位移拆開。'
        '縮放可使用右上角按鈕、Ctrl／⌘＋滾輪、雙擊或手機雙指；放大後可拖曳。</p></section>'
    )


MAP_JS = r"""
(function(){
  var box = document.querySelector('.worldmap');
  if(!box) return;
  var btns = box.querySelectorAll('.wm-tabs button');
  function show(y){
    box.querySelectorAll('[data-year]').forEach(function(el){
      if(el.tagName === 'BUTTON'){
        el.setAttribute('aria-pressed', el.dataset.year === y ? 'true' : 'false');
        return;
      }
      if(el.dataset.year === y) el.removeAttribute('hidden');
      else el.setAttribute('hidden','');
    });
    var b = box.querySelector('.wm-tabs button[data-year="' + y + '"]');
    box.querySelector('.wm-year').textContent = b ? b.dataset.title : y;
  }
  btns.forEach(function(b){ b.addEventListener('click', function(){ show(b.dataset.year); }); });
  box.querySelectorAll('.m-item').forEach(function(a){
    function lift(){ if(a.parentNode.lastElementChild !== a) a.parentNode.appendChild(a); }
    a.addEventListener('mouseenter', lift); a.addEventListener('focus', lift);
  });
})();

(function(){
  document.querySelectorAll('.m-stage').forEach(function(stage){
    var svg = stage.querySelector('svg.m-svg'), layer = svg.querySelector('.m-layer');
    var vb = svg.viewBox.baseVal, W = vb.width, H = vb.height;
    var k = 1, tx = 0, ty = 0, KMAX = 10;
    var marks = Array.prototype.slice.call(svg.querySelectorAll('.m-z'));
    function clamp(){
      k = Math.min(KMAX, Math.max(1, k));
      tx = Math.min(0, Math.max(W - W * k, tx));
      ty = Math.min(0, Math.max(H - H * k, ty));
    }
    function apply(){
      clamp();
      layer.setAttribute('transform', 'translate(' + tx + ',' + ty + ') scale(' + k + ')');
      var inv = 1 / k;
      marks.forEach(function(m){
        var x = +m.dataset.x, y = +m.dataset.y;
        m.setAttribute('transform', 'translate(' + x + ',' + y + ') scale(' + inv + ') translate(' + (-x) + ',' + (-y) + ')');
      });
      stage.classList.toggle('zoomed', k > 1.001);
    }
    function pt(cx, cy){
      var p = svg.createSVGPoint(); p.x = cx; p.y = cy;
      return p.matrixTransform(svg.getScreenCTM().inverse());
    }
    function zoomAt(f, sx, sy){
      var nk = Math.min(KMAX, Math.max(1, k * f)); f = nk / k;
      tx = sx - (sx - tx) * f; ty = sy - (sy - ty) * f; k = nk; apply();
    }
    stage.querySelectorAll('.m-zoom button').forEach(function(b){
      b.addEventListener('click', function(){
        if(b.dataset.z === 'reset'){ k = 1; tx = ty = 0; apply(); return; }
        zoomAt(b.dataset.z === 'in' ? 1.6 : 1 / 1.6, W / 2, H / 2);
      });
    });
    svg.addEventListener('wheel', function(e){
      if(!(e.ctrlKey || e.metaKey)) return;
      e.preventDefault(); var p = pt(e.clientX, e.clientY);
      zoomAt(Math.exp(-e.deltaY * .01), p.x, p.y);
    }, {passive:false});
    svg.addEventListener('dblclick', function(e){
      e.preventDefault(); var p = pt(e.clientX, e.clientY);
      zoomAt(e.shiftKey ? .5 : 2, p.x, p.y);
    });
    var pts = {}, last = null, moved = 0, pinch = null;
    svg.addEventListener('pointerdown', function(e){
      pts[e.pointerId] = {x:e.clientX,y:e.clientY}; moved = 0;
      var ids = Object.keys(pts);
      if(ids.length === 2){
        var a = pts[ids[0]], b = pts[ids[1]];
        pinch = {d:Math.hypot(a.x-b.x,a.y-b.y),k:k};
      }
      last = {x:e.clientX,y:e.clientY};
    });
    svg.addEventListener('pointermove', function(e){
      if(!pts[e.pointerId]) return;
      pts[e.pointerId] = {x:e.clientX,y:e.clientY};
      var ids = Object.keys(pts);
      if(ids.length === 2 && pinch){
        var a = pts[ids[0]], b = pts[ids[1]];
        var c = pt((a.x+b.x)/2,(a.y+b.y)/2);
        zoomAt(pinch.k*Math.hypot(a.x-b.x,a.y-b.y)/pinch.d/k,c.x,c.y);
        moved += 10; return;
      }
      if(k <= 1.001 || !last) return;
      var p0 = pt(last.x,last.y), p1 = pt(e.clientX,e.clientY);
      tx += p1.x-p0.x; ty += p1.y-p0.y;
      moved += Math.abs(e.clientX-last.x)+Math.abs(e.clientY-last.y);
      last = {x:e.clientX,y:e.clientY}; apply();
      if(moved > 4 && !svg.hasPointerCapture(e.pointerId)) svg.setPointerCapture(e.pointerId);
    });
    function up(e){ delete pts[e.pointerId]; if(Object.keys(pts).length < 2) pinch = null; last = null; }
    svg.addEventListener('pointerup',up); svg.addEventListener('pointercancel',up);
    svg.addEventListener('click',function(e){ if(moved > 4){ e.preventDefault(); e.stopPropagation(); }},true);
    apply();
  });
})();
"""


COUNTDOWN_JS = r"""
(function(){
  function tokyoDay(){
    var p = new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'})
      .formatToParts(new Date()).reduce(function(a,x){ if(x.type !== 'literal') a[x.type] = x.value; return a; },{});
    return Date.UTC(+p.year,+p.month-1,+p.day);
  }
  function daysUntil(iso){ return Math.round((Date.parse(iso+'T00:00:00Z')-tokyoDay())/86400000); }
  var el = document.querySelector('.count[data-start]');
  if(!el) return;
  var d = daysUntil(el.dataset.start), e = daysUntil(el.dataset.end || el.dataset.start);
  if(d > 1) el.innerHTML = '<b>'+d+'</b> 天後開幕';
  else if(d === 1) el.innerHTML = '<b>明天</b> 開幕';
  else if(d === 0) el.innerHTML = '<b>今天</b> 開幕';
  else if(e >= 0) el.innerHTML = '<b>進行中</b>';
  else el.innerHTML = '<b>已閉幕</b>';
})();
"""


def source_list(rows: list[dict]) -> str:
    return "".join(
        f'<li><a href="{html.escape(row["officialUrl"])}" target="_blank" rel="noopener">'
        f'{html.escape(society_code(row))} — {html.escape(row["name"])}</a></li>'
        for row in rows
    )


def footer_html(rows: list[dict], checked_at: str) -> str:
    return f"""
<footer>
  <p>官方資料查核至 {html.escape(checked_at)}。資料來源：</p>
  <ul>{source_list(rows)}</ul>
  <p>會議日期、城市與會場請以官方公告為準。訂閱
     <a href="conferences.ics">ICS 行事曆</a>，或下載
     <a href="conferences.csv">CSV</a>／<a href="conferences.json">JSON</a>。</p>
  <p class="template-credit">版型與追蹤架構沿用學長的
    <a href="https://96311123.github.io/EM-conference2/" target="_blank" rel="noopener">「急診國際年會追蹤」</a>；
    <a href="https://github.com/96311123/EM-conference2/" target="_blank" rel="noopener">原始碼 repository</a>。</p>
  <p class="license-note">日本地圖 SVG 來源：
    <a href="https://github.com/geolonia/japanese-prefectures" target="_blank" rel="noopener">Geolonia japanese-prefectures / map-full.svg</a>，
    源自 Wikipedia「日本地図.svg」，依
    <a href="https://www.gnu.org/licenses/fdl-1.3.html" target="_blank" rel="noopener">GNU Free Documentation License（GFDL）</a>使用。
    專案內保留原始 SVG 與授權說明。</p>
</footer>"""


def render_html(rows: list[dict], all_rows: list[dict], today: date, checked_at: str,
                map_svg: str, archive_count: int) -> str:
    upcoming = next_up(rows, today)
    if upcoming:
        days = max((upcoming["_start"] - today).days, 0)
        hero = (
            '<section class="hero"><p class="lede">下一場</p>'
            f'<p class="title">{html.escape(upcoming["name"])}</p>'
            f'<p class="meta">{html.escape(date_range(upcoming))}　·　'
            f'{html.escape(location_text(upcoming))}　·　{html.escape(upcoming["venue"])}</p>'
            f'<p class="count" data-start="{upcoming["start"]}" data-end="{upcoming["end"]}">'
            f'<b>{days}</b> 天後開幕</p></section>'
        )
    else:
        hero = (
            '<section class="hero"><p class="lede">下一場</p>'
            '<p class="title">目前沒有尚未結束的收錄會議。</p></section>'
        )
    archive_link = (
        f'<p class="archive-link"><a href="past.html">查看已結束的 {archive_count} 場歷屆會議</a></p>'
        if archive_count else '<p class="archive-link"><a href="past.html">查看歷屆會議頁</a></p>'
    )
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>日本急診相關醫學會議追蹤</title>
<meta name="description" content="追蹤日本國內急診、EMS、重症、敗血症、創傷、毒物、心臟、航空、潛水、登山與運動醫學等急性照護相關會議。">
<meta property="og:title" content="日本急診相關醫學會議追蹤">
<meta property="og:locale" content="zh_TW">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,300;6..72,400;6..72,600&display=swap" rel="stylesheet">
<style>{CSS}{MAP_CSS}</style>
</head>
<body><div class="wrap">
<header class="masthead">
  <h1>日本急診相關醫學會議追蹤</h1>
  <p class="stamp">資料查核 {html.escape(checked_at)}</p>
</header>
<p class="intro">收錄日本國內與急診醫學相關的急診、院前／EMS、災難、創傷、重症、敗血症／感染、毒物、心臟急症、航空、潛水／高壓氧、登山與運動醫學等會議；日期、城市、會場與連結均取自官方頁面。</p>
{japan_map_section(rows, map_svg)}
{hero}
<section>
  <h2>即將舉行的場次</h2>
  {conference_cards(rows, today)}
  {archive_link}
</section>
<section style="margin-top:3rem">
  <h2>年度節奏</h2>
  {season_grid(rows, today)}
</section>
<section style="margin-top:3rem">
  <h2>投稿死線</h2>
  {deadline_section(rows)}
</section>
{footer_html(all_rows, checked_at)}
</div><script>{COUNTDOWN_JS}{MAP_JS}</script></body></html>
"""


def render_archive(rows: list[dict], all_rows: list[dict], today: date, checked_at: str) -> str:
    content = (
        conference_cards(rows, today)
        if rows else '<div class="dl"><p class="note">目前尚無已結束的收錄會議。</p></div>'
    )
    grid = season_grid(rows, today) if rows else ""
    return f"""<!DOCTYPE html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>歷屆會議 — 日本急診相關醫學會議追蹤</title>
<meta name="robots" content="noindex">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,300;6..72,400;6..72,600&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">
<header class="masthead"><h1>歷屆會議</h1><p class="stamp"><a href="index.html">回到主頁</a></p></header>
<section style="margin-top:2.4rem"><p class="intro">已結束的日本急診相關醫學會議。</p></section>
{f'<section style="margin-top:2rem"><h2>年度節奏</h2>{grid}</section>' if grid else ''}
<section style="margin-top:3rem"><h2>全部歷屆場次</h2>{content}</section>
{footer_html(all_rows, checked_at)}
</div></body></html>"""


def build_files(events: list[dict], map_svg: str, today: date | None = None) -> dict[str, str]:
    validate_events(events)
    rows = prepare(events)
    today = today or tokyo_today()
    checked_at = source_checked_at(events)
    current, archive = split_archive(rows, today)
    deadlines = deadline_data(current)
    return {
        "index.html": render_html(current, rows, today, checked_at, map_svg, len(archive)),
        "past.html": render_archive(archive, rows, today, checked_at),
        "conferences.json": json.dumps(events, ensure_ascii=False, indent=2) + "\n",
        "conferences.csv": build_csv(events),
        "conferences.ics": build_ics(rows, checked_at),
        "deadlines.json": json.dumps(deadlines, ensure_ascii=False, indent=2) + "\n",
    }


def write_site(events: list[dict], map_svg: str, outdir: Path, license_text: str,
               today: date | None = None) -> None:
    files = build_files(events, map_svg, today)
    outdir.mkdir(parents=True, exist_ok=True)
    for relative, content in files.items():
        path = outdir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    assets = outdir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "map-full.svg").write_text(map_svg, encoding="utf-8")
    (assets / "MAP-LICENSE.md").write_text(license_text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the Japan emergency conference tracker")
    parser.add_argument("--input", type=Path, default=Path("data/conferences.json"))
    parser.add_argument("--map", dest="map_path", type=Path, default=Path("assets/map-full.svg"))
    parser.add_argument("--license", type=Path, default=Path("MAP-LICENSE.md"))
    parser.add_argument("--out", type=Path, default=Path("docs"))
    args = parser.parse_args()
    write_site(
        load_events(args.input),
        args.map_path.read_text(encoding="utf-8"),
        args.out,
        args.license.read_text(encoding="utf-8"),
    )


if __name__ == "__main__":
    main()

