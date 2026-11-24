from __future__ import annotations

import csv
import io
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
        self.assertNotIn("assets/acep.png", page)

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
        self.assertEqual([], __import__("json").loads(self.files["deadlines.json"]))
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

    def test_main_and_archive_outputs_always_exist(self):
        self.assertIn("日本急診相關醫學會議追蹤", self.files["index.html"])
        self.assertIn("目前尚無已結束的收錄會議", self.files["past.html"])


if __name__ == "__main__":
    unittest.main()
