# 日本急診相關醫學會議追蹤

以日本地圖、會議卡片、年度節奏與投稿死線整理日本國內急診及急性照護相關醫學會議。目前收錄 45 場已由官方來源確認日期與會場的未來會議，以及 92 場 2025／2026 已結束的歷屆會議；可用都道府縣、領域與自訂日期區間交集篩選，會議與區間有任一天重疊即納入。所有結果區會同步更新；選擇都道府縣時，地圖會自動聚焦符合條件的會場區域。各會議並附官方日文名稱及繁體中文譯名；歷屆頁另列出下一屆尚未完整公告的固定系列與官方追蹤入口。

- 公開網站：<https://brianann2339.github.io/japan-em-conference-map/>
- GitHub repository：<https://github.com/brianann2339/japan-em-conference-map>

版型與追蹤架構沿用學長的[「急診國際年會追蹤」](https://96311123.github.io/EM-conference2/)及其[公開 repository](https://github.com/96311123/EM-conference2/)。日本地圖採用 Geolonia `japanese-prefectures` 的 `map-full.svg`；來源與 GFDL 說明見 [MAP-LICENSE.md](MAP-LICENSE.md)。

## 重新產生網站

```bash
python3 build.py
```

`build.py` 讀取 `data/conferences.json`、`data/conference_names_zh-Hant.json`、`data/watchlist.json` 與 `assets/map-full.svg`，先產生 GitHub Pages 使用的 `docs/`，再同步完全相同的內容到 Sites 使用的 `dist/`。歷屆資料的逐批官方查核證據保留於 `data/history_sources/`，由 `scripts/import_history_sources.py` 驗證查核覆蓋率後匯入。

若只需產生單一輸出目錄：

```bash
python3 render.py --out docs
```

## 驗證

```bash
python3 -m py_compile render.py build.py tests/test_render.py
python3 -m json.tool data/conferences.json >/dev/null
python3 -m unittest discover -s tests -v
```

## 官方來源監測

第一次建立來源內容基準：

```bash
python3 scripts/monitor_sources.py --initialize
```

之後檢查官方會議頁及 `data/watchlist.json`：

```bash
python3 scripts/monitor_sources.py --check
```

監測程式會去除網頁的 script、style、noscript 與 SVG 後，比對可見文字的雜湊。來源內容或連線狀態改變時，才更新 `data/source-health.json`、`CHANGES.md` 與 `CHANGELOG.md`。歷屆資料保留官方來源供查閱，但不重複監測已封存或可能失效的舊大會頁；同系列目前及未來屆次的官方頁仍照常監測。無法穩定自動抓取的官方來源會在 watchlist 標記 `manual: true`，略過網路請求並交由人工追蹤，不會被當成新失敗開 issue。雜湊變動只代表來源需要複核，不會直接改寫 `data/conferences.json`。

GitHub Actions 每日 09:30（Asia/Tokyo）執行來源監測、測試、build 與 GitHub Pages 部署；有變動或讀取失敗時建立 issue。直接修改正式資料、renderer 或測試後，也會執行同一套驗證與部署流程。

另有每日 10:00（Asia/Tokyo）的語意複核任務：只在官方名稱、日期、城市、會場與來源均確認且測試通過後，才更新資料、追加 `CHANGELOG.md` 並推送 `main`；無確認變動時不建立 commit。

本專案不包含國際學會爬蟲。會議資料只來自 `data/conferences.json` 中已查核的日本會議；投稿死線未獲官方確認前一律顯示「尚未公布」，也不寫入 ICS。每次已確認資料更新另記錄於 [CHANGELOG.md](CHANGELOG.md)。
