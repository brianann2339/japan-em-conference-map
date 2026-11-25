from __future__ import annotations

import csv
import html
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
        cls.watchlist = render.load_watchlist(ROOT / "data" / "watchlist.json")
        cls.deadlines = render.load_deadlines(ROOT / "data" / "submission_deadlines.json")
        cls.map_svg = (ROOT / "assets" / "map-full.svg").read_text(encoding="utf-8")
        cls.today = date(2026, 11, 25)
        cls.current, cls.archive = render.split_archive(render.prepare(cls.events), cls.today)
        cls.files = render.build_files(
            cls.events, cls.map_svg, cls.today, cls.watchlist, cls.deadlines
        )

    def test_source_has_expected_codes(self):
        codes = {event["societyCode"] for event in self.events}
        self.assertTrue({
            "JSAEM", "JADM", "JSICM", "JSEM", "JSCT", "JAAM",
            "JSCCM", "JSACS", "JSER", "JCTS", "WADEM", "WCICC", "NATIONAL-MC",
        } <= codes)
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

    def test_prefecture_codes_match_map_groups(self):
        self.assertEqual(set(range(1, 48)), set(render.PREFECTURE_CODES.values()))
        for prefecture, code in render.PREFECTURE_CODES.items():
            label = prefecture if prefecture == "北海道" else prefecture[:-1]
            self.assertRegex(
                self.map_svg,
                fr'<g[^>]+data-code="{code}"[^>]*>\s*<title>{re.escape(label)} /',
            )

    def test_addition_batches_match_merged_source(self):
        by_id = {event["id"]: event for event in self.events}
        for path in sorted((ROOT / "data" / "additions").glob("*.json")):
            for event in json.loads(path.read_text(encoding="utf-8")):
                merged = {key: by_id[event["id"]][key] for key in event}
                self.assertEqual(event, merged, f"conflict in {path.name}")

    def test_history_sources_cover_all_tracked_series_and_match_archive(self):
        current = [event for event in self.events if not event.get("archiveOnly")]
        expected = {
            (event.get("seriesCode", event["societyCode"]), year)
            for event in current
            for year in ([2025] if event["start"].startswith("2026") else [2025, 2026])
        }
        items = [
            item
            for path in sorted((ROOT / "data" / "history_sources").glob("batch*.json"))
            for item in json.loads(path.read_text(encoding="utf-8"))
        ]
        queries = [
            (item["query"].get("seriesCode", item["query"]["societyCode"]), item["query"]["year"])
            for item in items
        ]
        regular = [query for query, item in zip(queries, items) if not item.get("supplemental")]
        self.assertEqual(expected, set(regular))
        self.assertEqual(len(expected), len(regular))
        self.assertEqual(len(queries), len(set(queries)))
        candidates = []
        for item in items:
            if item["status"] == "confirmed":
                candidates.append(item)
            candidates.extend(item.get("additionalEvents", []))
        self.assertTrue(all(candidate["evidence"] for candidate in candidates))
        self.assertEqual(
            {event["id"] for event in self.archive},
            {candidate["event"]["id"] for candidate in candidates},
        )

    def test_archive_lists_only_explicit_pending_series(self):
        page = self.files["past.html"]
        visible = [item for item in self.watchlist if item.get("showOnArchive")]
        self.assertEqual(5, len(visible))
        self.assertEqual(5, page.count('data-tracking-id="'))
        for item in visible:
            self.assertIn(f'data-tracking-id="{item["id"]}"', page)
            self.assertIn(item["displayCode"], page)
            self.assertIn(item["nameZh"], page)
            self.assertIn(item["url"], page)
        self.assertNotIn('data-tracking-id="national-mc-next"', page)
        self.assertNotIn('data-tracking-id="j-cimels"', page)
        self.assertIn("下一屆日期、城市或會場仍未完整公告", page)

    def test_juhms_annual_and_regional_series_stay_distinct(self):
        annual = [event for event in self.archive if event.get("seriesCode") == "JUHMS-ANNUAL"]
        regional = [
            event for event in self.archive
            if event["societyCode"] == "JUHMS" and event.get("seriesCode") != "JUHMS-ANNUAL"
        ]
        self.assertEqual(2, len(annual))
        self.assertTrue(regional)
        self.assertTrue(all(event["societyCode"] == "JUHMS" for event in annual))
        self.assertIn("hist-juhms-annual-2025", self.files["past.html"])
        self.assertIn("hist-juhms-2025", self.files["past.html"])

    def test_every_conference_has_a_traditional_chinese_translation(self):
        translations = json.loads(
            (ROOT / "data" / "conference_names_zh-Hant.json").read_text(encoding="utf-8")
        )
        self.assertEqual({event["id"] for event in self.events}, set(translations))
        self.assertEqual(len(self.events), len(translations))
        self.assertTrue(all(value.strip() for value in translations.values()))
        self.assertEqual(
            "第55屆日本急診醫學會總會暨學術集會",
            translations["jaam-55"],
        )
        page = self.files["index.html"]
        self.assertEqual(len(self.current), page.count('class="card-title-zh"'))
        self.assertIn('class="title-zh"', page)

    def test_localized_pages_and_switchers_are_rendered(self):
        expected = {
            "index.html": ("zh-Hant", "日本急診相關醫學會議追蹤"),
            "index-ja.html": ("ja", "日本の救急関連医学会議トラッカー"),
            "index-en.html": ("en", "Japan Emergency Medicine Conference Tracker"),
            "past.html": ("zh-Hant", "歷屆會議"),
            "past-ja.html": ("ja", "過去の会議"),
            "past-en.html": ("en", "Past conferences"),
        }
        for filename, (locale, title) in expected.items():
            page = self.files[filename]
            self.assertIn(f'<html lang="{locale}">', page)
            self.assertIn(title, page)
            self.assertEqual(1, page.count(f'lang="{locale}" aria-current="page"'))
            self.assertIn('class="language-switcher"', page)
        self.assertIn('href="index.html" lang="zh-Hant"', self.files["index-en.html"])
        self.assertIn('href="index-ja.html" lang="ja"', self.files["index.html"])
        self.assertIn('href="index-en.html" lang="en"', self.files["index-ja.html"])
        self.assertIn('href="past-en.html"', self.files["past-en.html"])
        self.assertIn("20th World Congress of Intensive and Critical Care", self.files["index-en.html"])
        self.assertIn("Official Japanese title (verified English title not available)", self.files["index-en.html"])

    def test_localized_pages_preserve_filter_machine_keys(self):
        registries = []
        for filename in ("index.html", "index-ja.html", "index-en.html"):
            match = re.search(
                r'<script id="conference-filter-data" type="application/json">(.*?)</script>',
                self.files[filename],
            )
            self.assertIsNotNone(match)
            registries.append(json.loads(match.group(1)))
        baseline = [(item["id"], item["prefecture"], item["topic"], item["start"], item["end"])
                    for item in registries[0]]
        for registry in registries[1:]:
            self.assertEqual(
                baseline,
                [(item["id"], item["prefecture"], item["topic"], item["start"], item["end"])
                 for item in registry],
            )
        self.assertIn('<option value="東京都" data-map-code="13">Tokyo</option>', self.files["index-en.html"])
        self.assertIn('<option value="critical">Intensive and critical care</option>', self.files["index-en.html"])
        self.assertIn('<option value="critical">重症／集中治療</option>', self.files["index-ja.html"])

    def test_page_i18n_payload_uses_a_stable_key_order(self):
        for filename in ("index.html", "index-ja.html", "index-en.html"):
            match = re.search(
                r'<script id="page-i18n" type="application/json">(.*?)</script>',
                self.files[filename],
            )
            self.assertIsNotNone(match)
            self.assertEqual(list(render.PAGE_I18N_KEYS), list(json.loads(match.group(1))))

    def test_localized_archive_tracking_text_is_complete(self):
        visible = [item for item in self.watchlist if item.get("showOnArchive")]
        for item in visible:
            self.assertIn(item["nameEn"], self.files["past-en.html"])
            self.assertIn(html.escape(item["reasonEn"]), self.files["past-en.html"])
            self.assertIn(item["reasonJa"], self.files["past-ja.html"])
        self.assertEqual(set(render.TEXT["zh-Hant"]), set(render.TEXT["ja"]))
        self.assertEqual(set(render.TEXT["zh-Hant"]), set(render.TEXT["en"]))
        self.assertEqual(set(render.TOPIC_LABELS), set(render.TOPIC_LABELS_JA))
        self.assertEqual(set(render.TOPIC_LABELS), set(render.TOPIC_LABELS_EN))

    def test_japanese_and_english_pages_use_japanese_city_forms(self):
        for filename in ("index-ja.html", "index-en.html", "past-ja.html", "past-en.html"):
            page = self.files[filename]
            self.assertNotIn("千代田區", page)
            self.assertNotIn("橫濱市", page)
            self.assertNotIn("神戶市", page)
            self.assertNotIn("鹿兒島市", page)
        self.assertIn("東京都千代田区", self.files["index-ja.html"])
        self.assertIn("横浜市", self.files["index-ja.html"])
        self.assertIn("鹿児島市", self.files["index-ja.html"])
        self.assertIn("Online", self.files["past-en.html"])
        self.assertIn("オンライン", self.files["past-ja.html"])

    def test_filter_controls_and_registry_cover_source(self):
        page = self.files["index.html"]
        match = re.search(
            r'<script id="conference-filter-data" type="application/json">(.*?)</script>',
            page,
        )
        self.assertIsNotNone(match)
        registry = json.loads(match.group(1))
        self.assertEqual({event["id"] for event in self.current}, {event["id"] for event in registry})
        self.assertEqual(
            {event["topicKey"] for event in self.current},
            {event["topic"] for event in registry},
        )
        self.assertTrue(all(event["nameZh"].strip() for event in registry))
        self.assertTrue(all(re.fullmatch(r"#[0-9a-f]{6}", event["color"]) for event in registry))
        self.assertTrue({event["topicKey"] for event in self.events} <= render.TOPIC_LABELS.keys())
        self.assertIn('id="filter-prefecture"', page)
        self.assertIn('id="filter-topic"', page)
        self.assertIn('id="filter-start" type="date"', page)
        self.assertIn('id="filter-end" type="date"', page)
        self.assertIn('id="filter-date-error" role="alert" hidden>起日不可晚於迄日。</span>', page)
        self.assertNotIn('id="filter-time"', page)
        self.assertNotIn('value="days:30"', page)
        self.assertNotIn('value="year:2027"', page)
        self.assertIn('<option value="神奈川県" data-map-code="14">神奈川県</option>', page)
        self.assertNotIn('<option value="神奈川縣">', page)
        self.assertIn('<option value="東京都" data-map-code="13">東京都</option>', page)

    def test_date_range_uses_inclusive_overlap_and_validates_order(self):
        page = self.files["index.html"]
        self.assertIn("var day = 86400000", page)
        self.assertIn("dateValue(event.end) < dateValue(startDate.value)", page)
        self.assertIn("dateValue(event.start) > dateValue(endDate.value)", page)
        self.assertIn("startDate.value > endDate.value", page)
        self.assertIn("startDate.setAttribute('aria-invalid','true')", page)
        self.assertIn("var matches = valid ? events.filter(selected) : lastMatches", page)
        self.assertIn("count.textContent = message('show_count',matches.length)", page)

    def test_filter_hooks_exist_for_every_event(self):
        page = self.files["index.html"]
        for event in self.current:
            event_id = re.escape(event["id"])
            deadline_count = sum(item["eventId"] == event["id"] for item in self.deadlines)
            self.assertEqual(
                4 + deadline_count,
                len(re.findall(fr'data-filter-id="{event_id}"', page)),
            )
        self.assertRegex(page, r'data-filter-ids="[^"]*jss-stroke-52[^"]*cvit-35[^"]*"')
        self.assertIn('[hidden]{display:none!important}', page)

    def test_prefecture_filter_dispatches_map_fit(self):
        page = self.files["index.html"]
        self.assertIn("KMAX = 24", page)
        self.assertIn("map:fit-prefecture", page)
        self.assertIn("visibleVenueBounds", page)
        self.assertIn(".prefecture[data-code=", page)
        self.assertIn("svg.querySelectorAll('.m-z,.m-cz')", page)
        self.assertIn("transform-origin:50% 100%", page)

    def test_filter_resizes_grouped_map_flags(self):
        page = self.files["index.html"]
        self.assertIn("flagFace.setAttribute('x',String(flagX))", page)
        self.assertIn("flagFace.setAttribute('width',String(flagWidth))", page)
        self.assertIn("flagFace.setAttribute('stroke',flagColor)", page)

    def test_map_strip_labels_include_topics(self):
        page = self.files["index.html"]
        for event in self.current:
            label = f'{event["societyCode"]}（{render.topic_with_cadence(event)}）'
            self.assertIn(f'<b>{label}</b>', page)

    def test_nonannual_cadence_is_visible(self):
        page = self.files["index.html"]
        archive = self.files["past.html"]
        self.assertIn("JAAM-KINKI（急診醫學・地方會（每年2次））", page)
        self.assertIn("NATIONAL-MC（院前救急・醫療管制（每年2次））", page)
        self.assertIn("WCICC（世界重症・集中治療（自2028起每年1次；此前非年度制））", page)
        self.assertIn("WADEM", archive)
        self.assertIn("世界災難・急診醫學（每2年1次）", archive)
        self.assertNotIn("國際災難・急診醫學（每2年1次）", archive)

    def test_shared_coordinate_uses_one_group_marker(self):
        page = self.files["index.html"]
        groups = {}
        for event in self.current:
            key = (event["start"][:4], round(event["lat"], 6), round(event["lng"], 6))
            groups[key] = groups.get(key, 0) + 1
        shared = [count for count in groups.values() if count > 1]
        self.assertEqual(len(shared), page.count('data-location-count="') - page.count('data-location-count="1"'))
        self.assertIn("同座標的會議共用旗子", page)

    def test_official_deadlines_are_rendered_and_not_calendar_events(self):
        page = self.files["index.html"]
        calendar = self.files["conferences.ics"]
        exported = json.loads(self.files["deadlines.json"])
        self.assertTrue(exported)
        self.assertEqual(len(self.deadlines), len(exported))
        self.assertTrue(all(item["officialUrl"].startswith("https://") for item in exported))
        self.assertIn('class="deadline-item upcoming"', page)
        self.assertIn('class="deadline-item closed"', page)
        self.assertIn("每週二 23:00（日本時間）複核", page)
        self.assertIn("JST", page)
        self.assertEqual(len(self.current), calendar.count("BEGIN:VEVENT"))
        self.assertNotIn("VALARM", calendar)
        self.assertNotIn("投稿", calendar)

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
        self.assertNotIn("目前尚無已結束的收錄會議", self.files["past.html"])
        self.assertEqual(len(self.archive), self.files["past.html"].count('class="card past"'))
        self.assertIn("hist-jaam-2025", self.files["past.html"])
        self.assertIn("hist-jaam-2026", self.files["past.html"])
        self.assertEqual({"2025": 52, "2026": 44}, {
            year: sum(event["start"].startswith(year) for event in self.archive)
            for year in ("2025", "2026")
        })


if __name__ == "__main__":
    unittest.main()
