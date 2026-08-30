# 開発ログ — 阪大基礎工 留学奨学金・補助金 検索ツール

対象期間: 2026-08-30（フェーズ0〜5 を1日で実施）
設計方針は [`plan.md`](./plan.md)、使い方は [`README.md`](./README.md) を参照。

## コミット履歴

| ハッシュ | 日時 | 内容 |
|---|---|---|
| `08ef4de` | 2026-08-30 15:42 | init: MVP（フェーズ0〜3）|
| `bfe5cf7` | 2026-08-30 15:56 | feat: 民間財団・阪大スクレイパー追加（フェーズ4）|
| `4f4a7fb` | 2026-08-30 16:17 | feat: 締切ICS・URL共有・解析導線（フェーズ5）|

ブランチ `main`、リモート未設定（GitHub push は未実施）。

---

## フェーズ0 — リポジトリ雛形

- `git init`、`user.name=ozawakiyoshi` / `user.email=ozwk2960@gmail.com`（このリポジトリのみ）。
- `.gitignore`（`public/scholarships.json` は生成物だがコミット対象のため除外しない旨コメント）。
- `requirements.txt`（requests / beautifulsoup4 / lxml / python-dateutil / jsonschema / pytest）。
- `README.md` 骨子、`public/scholarships.sample.json`（手書き4件）。
- ディレクトリ: `public/ scraper/sources/ tests/fixtures/ .github/workflows/`。
- **判明事項**: ローカル Python は 3.9.6（Actions 用は 3.12 想定）。以降のコードは
  `from __future__ import annotations` で 3.9 互換を維持。

## フェーズ1 — フロントエンド MVP（`public/index.html`、単一ファイル・依存ゼロ）

- `scholarships.json` を fetch、無ければ `scholarships.sample.json` にフォールバック。
- フィルタ8種: 学年/課程・専攻分野・留学先・留学種別・学内推薦・阪大対象のみ・
  締切（過去を隠す/30日以内）・フリーワード。加えて「一致するものだけ表示（厳格化）」トグル。
- 決定的スコアリング（AI不使用、plan §5-3 準拠）: 学年+30 / 専攻+20 / 留学先+15 /
  種別+10 / 阪大対象+15 / 推薦両立+10、締切近接 +12〜−50、金額0〜10、鮮度+3。
  同点は締切昇順→タイトル昇順。各カードに「この順位の理由」バッジ。
- 白＋青（`#1a56db`）、カードUI、860px 以下で1カラム＋パネル開閉。
- ブラウザ実機で全フィルタ・スコア・鮮度バナー・0件ガイド・リセットを確認。

## フェーズ2 — スクレイパー基盤 + JASSO / トビタテ

**基盤**
- `models.py`: `Scholarship` dataclass、`to_dict()`、`make_id()`、軽量自己検証。
- `normalize.py`: 和文日付→ISO、金額抽出（範囲は下限採用・10,000円未満と年号を除外）、
  表記ゆれ吸収。取れなければ `None`（推測しない）。
- `sources/base.py`: UA明示・タイムアウト20s・指数バックオフ最大3回・4xxは即中断・
  ポライトディレイ3s・robots.txt確認。例外は `source_status.ok=false` に変換。
  テストは `fetcher` 差し替えでネットワーク非依存。
- `merge.py`: 成功=置換＋`first_seen`引継ぎ、失敗/0件=前回データ保持＋`stale_since`、
  id重複排除、`(source,title,deadline)` 二次ガード、安定ソート。
- `schema.json`（JSON Schema draft 2020-12）。
- `run.py`: 全ソース実行→マージ→**スキーマ検証（失敗時は既存を上書きしない・exit 1）**
  →書き出し。`--dry-run` 対応。

**判明事項**
- JASSO は URL 構造を刷新済み（`scholarship_j` → `scholarship_a`）。旧URLは全404。
  → index ページ→年度別ページ（`{program}/YYYY.html`）方式にし、新年度公開に自動追従。
  現時点で **学部2027 が募集中（締切 2026-10-01）**、大学院/学部2026 は募集終了。
- トビタテは JS・画像主体で締切日をHTMLから取れない。→ ニュース見出しから
  「大学生等（第N期）」の募集開始/終了と期番号だけ取得、金額等は `config.py` に手入力。
  第18期は募集終了として検知。サイトの meta 記述が募集状況とずれるため説明文も固定化。
- 協定派遣（haken）は個人公募がなく年度ページが「採用者専用」→ `enabled=False`。

**成果**: 5件（JASSO 4・トビタテ 1）。フェイルセーフを実証（片方を404化→前回保持）。

## フェーズ3 — 自動化（GitHub Actions + Cloudflare Pages）

- `.github/workflows/scrape.yml`: cron `0 21 * * *`（JST 06:00）＋手動実行。
  `concurrency` で多重防止、`permissions: contents: write`。
  **コミット制御**: 内容変化なし→skip、`generated_at`/`fetched_at` だけの差分→skip
  （`git checkout` で戻す）、実質変化あり→ `github-actions[bot]` でコミット（`[skip ci]`）。
  ローカルでスキップ判定ロジックを実証。
- `.github/workflows/ci.yml`: push / PR で `pytest` ＋ 生成JSONのスキーマ検証。
- `public/_headers`: セキュリティヘッダ、`scholarships.json` を `max-age=3600`。
- README にデプロイ手順（GitHub public リポジトリ作成→Settings で Read/write 権限→
  Cloudflare Pages「Connect to Git」/ 出力 `public` / ビルドなし）を具体化。
- 初回 git コミット `08ef4de` を作成。

## フェーズ4 — 民間財団・阪大スクレイパー（2→6ソース、5→54件）

| ソース | 方式 | 結果 |
|---|---|---|
| 船井情報科学振興財団 `funai.py` | 応募要項の `dt/dd` を解析。「応募期間」から**締切を動的取得**、「支援内容」から金額テキスト | 博士 締切 **2026-09-30**（募集中）/ 学部 2025-09-30（終了）|
| 吉田育英会 `yoshida.py` | 要項ページから「20XX年度採用分の募集」を検出（詳細はPDF→支援内容は手入力）| 2027年度採用分 募集中 |
| 孫正義育英財団 `masason.py` | 募集要項「今期の募集は終了」＋トップニュースの「第N期」 | 第10期・募集終了。留学専用でない旨タグ |
| 大阪大学 `osaka_u.py` | 留学助成制度ページの2表を行単位で解析。**セクションで学内推薦の有無を判定** | **45件**。掲示日450日超・JASSO/トビタテ重複を除外。学内ログイン要リンクは公開ページにフォールバック |

**判明事項・変更**
- `www.ysf.or.jp` は `/robots.txt` に **403** を返す（WAF）。Python 標準の robotparser は
  403 を「全面禁止」と解釈するため、`base.py` を **RFC 9309 準拠**に変更
  （4xx＝取得不能＝許可、429 のみ保守的に不許可）。
- 阪大ページのおかげで「学内推薦の有無」データが実用レベルに（25件にフラグ）。
- `merge.py`: `source_status.count` を重複排除後の実件数に修正。
- 2ソース同時故障のフェイルセーフを再検証（前回45件保持・スキーマ有効）。
- コミット `bfe5cf7`。

## フェーズ5 — 締切ICS / URL共有 / 解析導線

- `scraper/ics.py`: 確定した未来の締切（`deadline_type=fixed`）を VEVENT 化した
  `public/deadlines.ics` を生成。7日前アラーム、`DTSTAMP` は `first_seen` 由来で安定。
  RFC 5545 のライン折り返しはオクテット単位でマルチバイトを分割しない。
  `run.py` が JSON と同時に書き出す。現在 5 件が確定締切。
- `index.html`:
  - 絞り込み条件を URL クエリ（`?d/f/r/t/nom/osaka/past/soon/strict/q`）に同期。
    リロード・共有リンクで状態復元。「🔗 この検索を共有」でURLコピー。
  - 各カードに「📅 締切を追加」（1件分 .ics を data URI ダウンロード）。締切未定は非表示。
  - フッタに `deadlines.ics` 購読リンク。
  - Cloudflare Web Analytics 用スニペットをコメントで用意（トークン差し替え式）。
- `_headers`: `deadlines.ics` に `text/calendar` とキャッシュ。
- `scrape.yml`: `deadlines.ics` も差分判定・コミット対象に追加。
- ブラウザで URL 復元・共有コピー・カレンダーボタン表示を確認。
- コミット `4f4a7fb`。

---

## 現況スナップショット（2026-08-30 時点）

- ファイル 55（うち `tests/fixtures/` の実HTML 19本）。`public/index.html` 約 830 行、
  `scraper/` 約 1,100 行。テスト **39 件パス**（fixture ベース・ネットワーク不要）。
- 収録 **54 件**: JASSO 4 / トビタテ 1 / 船井 2 / 吉田 1 / 孫正義 1 / 大阪大学 45。
  学内推薦フラグ付き 25 件、確定締切 5 件。
- 全6ソースが実サイトに対して `ok` を確認済み。

## 既知の制約・TODO

- **未デプロイ**: GitHub リモート未設定。README 手順で push → Cloudflare Pages 連携が必要。
  併せて `scraper/config.py` の `USER_AGENT` 内 URL を実リポジトリ URL に更新。
- 金額など要項ベースの安定情報は `config.py` に手入力（`CURATED_*`）。
  募集要項公開時期（例年 夏〜秋）に公式資料と突き合わせて更新する運用。
- 阪大の各行は `target_degree` 未設定 → 「一致するものだけ表示（厳格）」＋学年指定時は
  除外される（設計どおり）。
- 2件構成ソース（船井）は片方のプログラムが落ちるともう片方も欠落（フェイルセーフで
  前回分は保持）。JASSO も同様に年度単位の失敗は全体失敗になる。
- JASSO 大学院・トビタテの金額は Web 検索由来のキュレーション値。PDF 解析（pdfminer 等）は
  将来対応。
- public リポジトリは 60 日無操作で `schedule` が停止 → Actions タブから再有効化。
- 阪大の政府奨学金系エントリ（スイス/フランス政府奨学金など）は締切未定でスコアが低め。
