from __future__ import annotations

import csv
import io
import json
import re
import unittest
from datetime import date
from pathlib import Path

import render


ROOT = Path(__file__).resolve().parents[1]


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = render.load_events(ROOT / "data" / "conferences.json")
        cls.map_svg = (ROOT / "assets" / "map-full.svg").read_text(encoding="utf-8")
        cls.files = render.build_files(cls.events, cls.map_svg, date(2026, 11, 25))

    def test_source_has_expected_codes(self):
        codes = {event["societyCode"] for event in self.events}
        self.assertTrue({"JSAEM", "JADM", "JSICM", "JSEM", "JSCT", "JAAM"} <= codes)
        self.assertTrue(all(re.fullmatch(r"[A-Z0-9-]+", code) for code in codes))

    def test_japan_map_and_credits_are_rendered(self):
        page = self.files["index.html"]
        self.assertEqual(47, len(re.findall(r'data-code="\d+"', page)))
        self.assertIn("版型與追蹤架構沿用學長", page)
        self.assertIn("https://96311123.github.io/EM-conference2/", page)
        self.assertIn("https://github.com/geolonia/japanese-prefectures", page)
        self.assertIn("GFDL", page)
        self.assertIn("山上有草一直燒資訊有限公司製作", page)
        self.assertLess(page.index("版型與追蹤架構沿用學長"), page.index("山上有草一直燒資訊有限公司製作"))
        self.assertIn('rel="icon" href="data:image/svg+xml,', page)
        self.assertNotIn("assets/acep.png", page)

    def test_addition_batches_match_merged_source(self):
        by_id = {event["id"]: event for event in self.events}
        for path in sorted((ROOT / "data" / "additions").glob("*.json")):
            for event in json.loads(path.read_text(encoding="utf-8")):
                merged = {key: by_id[event["id"]][key] for key in event}
                self.assertEqual(event, merged, f"conflict in {path.name}")

    def test_every_conference_has_a_traditional_chinese_translation(self):
        translations = json.loads(
            (ROOT / "data" / "conference_names_zh-Hant.json").read_text(encoding="utf-8")
        )
        self.assertEqual({event["id"] for event in self.events}, set(translations))
        self.assertEqual(45, len(translations))
        self.assertTrue(all(value.strip() for value in translations.values()))
        self.assertEqual(
            "第55屆日本急診醫學會總會暨學術集會",
            translations["jaam-55"],
        )
        page = self.files["index.html"]
        self.assertEqual(len(self.events), page.count('class="card-title-zh"'))
        self.assertIn('class="title-zh"', page)

    def test_filter_controls_and_registry_cover_source(self):
        page = self.files["index.html"]
        match = re.search(
            r'<script id="conference-filter-data" type="application/json">(.*?)</script>',
            page,
        )
        self.assertIsNotNone(match)
        registry = json.loads(match.group(1))
        self.assertEqual({event["id"] for event in self.events}, {event["id"] for event in registry})
        self.assertEqual(
            {event["topicKey"] for event in self.events},
            {event["topic"] for event in registry},
        )
        self.assertTrue(all(event["nameZh"].strip() for event in registry))
        self.assertTrue(all(re.fullmatch(r"#[0-9a-f]{6}", event["color"]) for event in registry))
        self.assertTrue({event["topicKey"] for event in self.events} <= render.TOPIC_LABELS.keys())
        self.assertIn('id="filter-prefecture"', page)
        self.assertIn('id="filter-topic"', page)
        self.assertIn('id="filter-time"', page)
        self.assertIn('<option value="days:30">未來 30 天</option>', page)
        self.assertIn('<option value="year:2027">2027 年</option>', page)
        self.assertIn('<option value="神奈川県">神奈川県</option>', page)
        self.assertNotIn('<option value="神奈川縣">', page)

    def test_filter_hooks_exist_for_every_event(self):
        page = self.files["index.html"]
        for event in self.events:
            event_id = re.escape(event["id"])
            self.assertEqual(4, len(re.findall(fr'data-filter-id="{event_id}"', page)))
        self.assertRegex(page, r'data-filter-ids="[^"]*jss-stroke-52[^"]*cvit-35[^"]*"')

    def test_filter_resizes_grouped_map_flags(self):
        page = self.files["index.html"]
        self.assertIn("flagFace.setAttribute('x',String(flagX))", page)
        self.assertIn("flagFace.setAttribute('width',String(flagWidth))", page)
        self.assertIn("flagFace.setAttribute('stroke',flagColor)", page)

    def test_shared_coordinate_uses_one_group_marker(self):
        page = self.files["index.html"]
        groups = {}
        for event in self.events:
            key = (round(event["lat"], 6), round(event["lng"], 6))
            groups[key] = groups.get(key, 0) + 1
        shared = [count for count in groups.values() if count > 1]
        self.assertEqual(len(shared), page.count('data-location-count="') - page.count('data-location-count="1"'))
        self.assertIn("同座標的會議共用旗子", page)

    def test_deadlines_are_tba_and_not_calendar_events(self):
        page = self.files["index.html"]
        calendar = self.files["conferences.ics"]
        self.assertIn("目前沒有官方已確認的投稿截止日期", page)
        self.assertEqual([], json.loads(self.files["deadlines.json"]))
        self.assertEqual(len(self.events), calendar.count("BEGIN:VEVENT"))
        self.assertNotIn("VALARM", calendar)

    def test_calendar_end_date_is_exclusive(self):
        calendar = self.files["conferences.ics"]
        self.assertIn("DTSTART;VALUE=DATE:20270304", calendar)
        self.assertIn("DTEND;VALUE=DATE:20270306", calendar)

    def test_csv_preserves_japanese_text(self):
        rows = list(csv.DictReader(io.StringIO(self.files["conferences.csv"].lstrip("\ufeff"))))
        self.assertEqual(len(self.events), len(rows))
        target = next(row for row in rows if row["id"] == "jsaem-63")
        self.assertEqual("福岡国際会議場・福岡サンパレス", target["venue"])
        self.assertEqual("第63屆日本腹部急症醫學會總會", target["nameZh"])

    def test_main_and_archive_outputs_always_exist(self):
        self.assertIn("日本急診相關醫學會議追蹤", self.files["index.html"])
        self.assertIn("目前尚無已結束的收錄會議", self.files["past.html"])


if __name__ == "__main__":
    unittest.main()
