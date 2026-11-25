# 更新記錄

## 2026-11-25（Asia/Tokyo）

- 建立沿用學長「急診國際年會追蹤」版型與追蹤架構的日本版網站。
- 換用日本地圖並保留地圖資料來源與 GFDL 授權說明。
- 收錄 45 場已由官方頁確認名稱、日期與會場的日本急診相關會議。
- 會議與地圖座標依官方來源及地理物件分批核對；園區或校區代表點另行標示。
- 新增保守的官方來源監測層；頁面變動只建立待複核記錄，不直接改寫正式會議資料。
- 依北海道救急醫學會官方 PDF 新增第 51 回學術集會（2027-10-30，札幌）。
- 將第 43 回日本救急醫學會中國四國地方會改連至可用的官方大會頁。
- 自動監測略過無法穩定抓取的 JSACS 人工來源，並排除網頁 `<head>` 的動態內容以降低誤報。
- 修正日本蘇生學會第 45 回大會的地圖點：原值是 Google 地圖視窗中心，改用東京慈惠會醫科大學西新橋校區／附屬醫院代表點。
- 修正日本 Shock 學會與日本精神科救急學會的順天堂大學 7 號館地圖點：原值是 Google 地圖視窗中心，改用 OSM 的 7 號館（A 棟）建物中心。
- 補齊 STROKE 2027 的三個聯合學術集會完整名稱。
- 新增都道府縣、領域與時間三條件交集篩選，並同步更新地圖、卡片、年度節奏與下一場資訊。
- 為 45 場會議補上臺灣醫學用語的繁體中文譯名，同時保留官方日文名稱。
- 在所有頁面最底部新增「山上有草一直燒資訊有限公司製作」署名。
- 將固定的 30／90／180 天與年度選項改為可輸入或選擇起日、迄日的自訂日期區間；會議與區間有任一天重疊即納入。
- 修正篩選後卡片、地圖清單與圖例仍顯示未符合項目的 CSS 衝突；選擇都道府縣時自動聚焦符合條件的會場區域，並提高地圖縮放上限。
- 新增 82 場由官方來源核實的 2025／2026 歷屆會議；歷屆頁保留日文名稱、繁中譯名、日期、城市、會場與來源，ICS 維持只輸出未結束場次。
- 地圖下方的會議摘要列在縮寫後加上繁中領域，例如「JNST（腦神經外傷）」。
- 再次稽核「2025、2026 曾舉辦但下一屆尚未完整公告」的固定系列，補入 JSCCM、JSACS、JSER、JCTS 與 JUHMS 全國學術總會共 10 場歷屆會議，歷屆總數增為 92 場。
- 歷屆頁新增 5 個待續辦系列的可見追蹤清單與官方入口；同時修正全國 Medical Control 協議會已公布 2027-02-05 場次的過期追蹤狀態。
- 新增令和8年度第2回全國 Medical Control 協議會、近畿急診醫學研究會第134回與 WCICC2029，未來場次增為 48 場。
- 補入 WADEM 2025 東京及全國 Medical Control 協議會 2025／2026 三場歷屆紀錄，歷屆總數增為 96 場。
- 對照學長網站的世界級系列並逐一核查官方公告；目前 2025 年以後確認在日本舉辦者為 WADEM 2025 東京與 WCICC2029 京都。
- 對每年兩次、每兩年一次及由非年度制改為年度制的系列新增 `cadence` 標示，並補查同年度第二場。
- 新增 28 場會議共 71 個官方確認的投稿／發表申請期限；卡片顯示下一個截止日，投稿列表與既有篩選同步，未公告期限不推估。
- 官方來源監測擴充至會議、待公告系列及投稿頁共 97 個入口；本次新入口均已建立基準，沒有讀取失敗。
- 將單一語意複核任務改為每週二 23:00（Asia/Tokyo），並停用重複的 GitHub Actions 每日排程；資料推送後仍自動測試、build 與部署。

## 2026-11-25T12:44:30+09:00（Asia/Tokyo）

官方來源監測複核完成：

- 第35回全國救護隊員研討會只新增出演者及參加資訊，會名、日期與會場未變。
- 建立第42屆日本救命醫療學會與日本交通科學學會下一屆學術講演會的監測基準。

## 2026-11-25T13:24:19+09:00（Asia/Tokyo）

官方來源監測發現變動，待人工複核：

- [令和8年度第2回全国メディカルコントロール協議会連絡会](https://www.mhlw.go.jp/content/10800000/001724499.pdf)
- [第134回近畿救急医学研究会（日本救急医学会近畿地方会）](https://www.jaam-kinki.jp/meeting.html)
- [第20回世界集中治療医学会学術集会（WCICC2029）](https://www.jsicm.org/en/news/news251118.html)
- [第135回近畿救急医学研究会](https://www.jaam-kinki.jp/meeting.html)
- [jca-39 — 投稿資料](https://www.jca39.com/cfa.html)
- [jsr-45 — 投稿資料](https://jsr45.umin.jp/subject.html)
- [jssi-39 — 投稿資料](https://med-gakkai.jp/39jssi/endai/)
- [jsasem-72 — 投稿資料](https://jsasem72.com/abstract.html)
- [jaam-chubu-29 — 投稿資料](https://jaam29.com/cfa.html)
- [jspm-21 — 投稿資料](https://jspm21.global-convention.jp/)
- [jsts-2 — 投稿資料](https://2nd.jsts-mw.jp/abstracts)
- [juhms-kanto-tohoku-25 — 投稿資料](https://www.juhms.net/syukai/chihoukai/kanto/)
- [siret-13 — 投稿資料](https://kenkyuukai.m3.com/event/event_detail.asp?id=86881)
- [ems-symp-35 — 投稿資料](https://www.knt.co.jp/ec/2027/99sympo_35/endai.html)
- [ems-symp-35 — 投稿資料](https://www.knt.co.jp/ec/2027/99sympo_35/shitei_endai.html)
- [jnst-50 — 投稿資料](https://neurotrauma50.umin.jp/cfa.html)
- [jaam-kanto-77 — 投稿資料](https://jaam77kanto.umin.jp/smaq.html)
- [jaam-kanto-77 — 投稿資料](https://jaam77kanto.umin.jp/kyumei.html)
- [jaam-kanto-77 — 投稿資料](https://jaam77kanto.umin.jp/subject64.html)
- [jaam-kanto-77 — 投稿資料](https://jaam77kanto.umin.jp/subject77.html)
- [jaam-kanto-77 — 投稿資料](https://jaam77kanto.umin.jp/council.html)
- [jaam-kanto-77 — 投稿資料](https://jaam77kanto.umin.jp/liaison-meeting.html)
- [jaam-kanto-77 — 投稿資料](https://jaam77kanto.umin.jp/session.html)
- [jsaem-63 — 投稿資料](https://www.jsaem63.org/abstract.html)
- [jsaem-63 — 投稿資料](https://www.jsaem63.org/young_discussant.html)
- [jaam-kinki-133 — 投稿資料](https://www.k-gakkai.jp/133jaam-kinki/abstract.html)
- [jss-stroke-52 — 投稿資料](https://www.congre.co.jp/stroke2027/cfa.html)
- [jss-stroke-52 — 投稿資料](https://www.congre.co.jp/stroke2027/kusano.html)
- [jadm-32 — 投稿資料](https://site2.convention.co.jp/32jadm/cfa/index.html)
- [jcs-91-apsc — 投稿資料](https://www.congre.co.jp/jcs2027/cfa/index.html)
- [jcs-91-apsc — 投稿資料](https://www.congre.co.jp/jcs2027/en/cfa/index.html)
- [jcs-91-apsc — 投稿資料](https://www.congre.co.jp/jcs2027/en/yia_students/index.html)
- [jss-41 — 投稿資料](https://jss41.umin.ne.jp/abstracts.html)
- [jsicm-54 — 投稿資料](https://jsicm.org/meeting/jsicm54/cfa/index.html)
- [jaid-101-jsc-75 — 投稿資料](https://www.c-linkage.co.jp/jaid101-jsc75/encore.html)
- [jaid-101-jsc-75 — 投稿資料](https://www.c-linkage.co.jp/jaid101-jsc75/specify_abstract.html)
- [jsbi-53 — 投稿資料](https://shun-convention.jp/jsbi53/kobo_abstract.html)
- [jast-41 — 投稿資料](https://shun-convention.jp/jast2027/abstract.html)
- [jaam-chushi-43 — 投稿資料](https://med-gakkai.jp/jaam-cs43/endai/)
- [jsth-49 — 投稿資料](https://www.c-linkage.co.jp/jsth49/call_for_papers.html)
- [jsth-49 — 投稿資料](https://www.c-linkage.co.jp/jsth49/general_abstract.html)
- [jsoa-2027 — 投稿資料](https://www.congre.co.jp/jsoa2027/contents/abstract_i.html)
- [jrcm-49 — 投稿資料](https://jsrcm49.umin.jp/abstract.html)
- [jsem-30 — 投稿資料](https://site2.convention.co.jp/jsem30/endai/)
- [cvit-35 — 投稿資料](https://www.congre.co.jp/cvit2027/cfa.html)
- [cvit-35 — 投稿資料](https://www.congre.co.jp/cvit2027/application.html)

上述 46 項是本次新增會議／投稿來源建立監測基準所產生的首次差異，已逐項以官方頁複核並納入正式資料；監測結果為 97 個來源、0 個讀取失敗。
