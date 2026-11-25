from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import monitor_sources


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / "source-health.json"
        self.changes = self.root / "CHANGES.md"
        self.changelog = self.root / "CHANGELOG.md"
        self.changelog.write_text("# 更新記錄\n", encoding="utf-8")
        self.sources = [
            {"id": "conference:test", "name": "測試會議", "url": "https://example.test/", "kind": "conference"}
        ]

    def tearDown(self):
        self.temp.cleanup()

    def fetcher(self, html="<main>初版</main>"):
        return lambda url: {
            "status": 200,
            "finalUrl": url,
            "contentHash": monitor_sources.content_hash(html),
            "error": None,
        }

    def run_monitor(self, fetcher, initialize=False, now="2026-11-25T09:30:00+09:00"):
        return monitor_sources.run_monitor(
            sources=self.sources,
            state_path=self.state,
            changes_path=self.changes,
            changelog_path=self.changelog,
            fetcher=fetcher,
            initialize=initialize,
            now=now,
        )

    def test_initialize_creates_baseline_without_change_log_entry(self):
        result = self.run_monitor(self.fetcher(), initialize=True)
        self.assertEqual([], result["changed"])
        self.assertTrue(self.state.exists())
        self.assertEqual("# 更新記錄\n", self.changelog.read_text(encoding="utf-8"))
        self.assertFalse(self.changes.exists())

    def test_unchanged_run_does_not_rewrite_files(self):
        self.run_monitor(self.fetcher(), initialize=True)
        before = self.state.stat().st_mtime_ns
        self.run_monitor(self.fetcher())
        self.assertEqual(before, self.state.stat().st_mtime_ns)
        self.assertFalse(self.changes.exists())

    def test_page_change_updates_state_and_logs_url(self):
        self.run_monitor(self.fetcher(), initialize=True)
        result = self.run_monitor(self.fetcher("<main>第二版</main>"))
        self.assertEqual(1, len(result["changed"]))
        self.assertIn("https://example.test/", self.changes.read_text(encoding="utf-8"))
        self.assertIn("2026-11-25T09:30:00+09:00", self.changelog.read_text(encoding="utf-8"))

    def test_failure_preserves_previous_hash(self):
        self.run_monitor(self.fetcher(), initialize=True)
        before = json.loads(self.state.read_text(encoding="utf-8"))["sources"]["conference:test"]["contentHash"]
        result = self.run_monitor(lambda url: {"error": "timeout"})
        after = json.loads(self.state.read_text(encoding="utf-8"))["sources"]["conference:test"]["contentHash"]
        self.assertEqual(before, after)
        self.assertEqual(1, len(result["failures"]))
        self.assertIn("timeout", self.changes.read_text(encoding="utf-8"))

    def test_normalization_removes_script_style_noscript_and_svg(self):
        first = '<head><title>動態標題一</title></head><main>急診  會議</main><script>nonce=1</script><style>x{}</style><svg><text>A</text></svg>'
        second = '<head><title>動態標題二</title></head><main>急診\n會議</main><script>nonce=2</script><noscript>fallback</noscript>'
        self.assertEqual(monitor_sources.content_hash(first), monitor_sources.content_hash(second))

    def test_load_sources_excludes_archive_only_events(self):
        data = self.root / "conferences.json"
        watchlist = self.root / "watchlist.json"
        data.write_text(json.dumps([
            {"id": "current", "name": "目前場次", "officialUrl": "https://example.test/current"},
            {"id": "past", "name": "歷屆場次", "officialUrl": "https://example.test/past", "archiveOnly": True},
        ]), encoding="utf-8")
        watchlist.write_text("[]", encoding="utf-8")
        sources = monitor_sources.load_sources(data, watchlist)
        self.assertEqual(["conference:current"], [source["id"] for source in sources])

    def test_normalization_version_change_rebaselines_without_change_report(self):
        self.run_monitor(self.fetcher(), initialize=True)
        state = json.loads(self.state.read_text(encoding="utf-8"))
        state["normalizationVersion"] = monitor_sources.NORMALIZATION_VERSION - 1
        self.state.write_text(json.dumps(state), encoding="utf-8")

        result = self.run_monitor(self.fetcher("<main>新版</main>"))

        self.assertEqual([], result["changed"])
        self.assertFalse(self.changes.exists())
        updated = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(monitor_sources.NORMALIZATION_VERSION, updated["normalizationVersion"])

    def test_load_sources_excludes_manual_watchlist_entries(self):
        data = self.root / "conferences.json"
        watchlist = self.root / "watchlist.json"
        data.write_text(
            json.dumps([{"id": "test", "name": "測試會議", "officialUrl": "https://old.test/"}]),
            encoding="utf-8",
        )
        watchlist.write_text(
            json.dumps([
                {
                    "id": "manual-test",
                    "name": "人工追蹤來源",
                    "url": "https://manual.test/",
                    "status": "manual",
                    "reason": "無法穩定抓取",
                    "manual": True,
                }
            ]),
            encoding="utf-8",
        )

        sources = monitor_sources.load_sources(data, watchlist)

        self.assertEqual(1, len(sources))
        self.assertEqual("conference:test", sources[0]["id"])


if __name__ == "__main__":
    unittest.main()
