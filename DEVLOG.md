# 開発ログ — 阪大基礎工 留学奨学金・補助金 検索ツール

対象期間: 2026-08-30（フェーズ0〜6 を1日で実施）
設計方針は [`plan.md`](./plan.md)、使い方は [`README.md`](./README.md) を参照。

**公開サイト: <https://kisoko-scholarships.pages.dev/>**
**リポジトリ: <https://github.com/ozwk2960-cloud/kisoko-scholarships>**

## コミット履歴

| ハッシュ | 日時 | 内容 |
|---|---|---|
| `08ef4de` | 2026-08-30 15:42 | init: MVP（フェーズ0〜3）|
| `bfe5cf7` | 2026-08-30 15:56 | feat: 民間財団・阪大スクレイパー追加（フェーズ4）|
| `4f4a7fb` | 2026-08-30 16:17 | feat: 締切ICS・URL共有・解析導線（フェーズ5）|
| `2d09bd8` | 2026-08-30 16:34 | docs: 開発ログ追加 |
| `976c753` | 2026-08-30 16:34 | chore: USER_AGENT・README のリポジトリ URL を確定 |
| `420cc11` | 2026-08-30 17:09 | docs: 公開 URL をフッタ・README・canonical に記載 |

ブランチ `main`、リモート `origin` = GitHub（push 済み・Cloudflare Pages 連携済み）。

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

## フェーズ6 — 本番デプロイ（2026-08-30 夕方）

ユーザー側の GitHub アカウント（`ozwk2960-cloud`）と Cloudflare アカウント
（Google ログイン）を用いて、実際の公開まで実施した。

**GitHub**
- 空の public リポジトリ `ozwk2960-cloud/kisoko-scholarships` を作成。
- `git remote add origin` → `git push -u origin main`。
- 認証は Fine-grained PAT（HTTPS）。**ハマりどころ2点**:
  1. トークン文字列は生成直後の1回しか表示されない（詰まったら Regenerate）。
  2. `.github/workflows/` を含む push には PAT に **Workflows: Read and write**
     権限が必須（Contents だけだと `refusing to allow a Personal Access Token
     to create or update workflow ... without workflow scope` で部分拒否）。
- push 後、`.git/config` からトークンを除去（`git remote set-url` でクリーンな
  URL に戻す）。認証は `credential.helper=osxkeychain` に保存。
- Settings → Actions → Workflow permissions を **Read and write** に設定。
- `scrape` を手動実行（`workflow_dispatch`）→ success。収集データが既存と同一
  だったため新規コミットは発生せず（変化時のみコミットする設計どおり）。
- `ci`（pytest）も push 契機で success。

**Cloudflare Pages**
- ダッシュボード刷新により導線が変化。Workers & Pages → Create application →
  Pages の「Get started」→ **Import an existing Git repository** から連携。
- ビルド設定: Production branch `main` / Framework preset **None** /
  Build command 空 / Build output directory **`public`**。
- 初回デプロイ成功 → `https://kisoko-scholarships.pages.dev/` 発行。
- 検証: `/`=200（35,731B）、`/scholarships.json`=200（76,278B・54件）、
  `/deadlines.ics`=200（`text/calendar`）、`_headers` のセキュリティヘッダ適用を確認。

**仕上げ（`420cc11`）**
- `index.html` に `<link rel="canonical">` とフッタの公開 URL・GitHub リンクを追加。
- `README.md` 冒頭に公開サイト URL を明記。
- `scraper/config.py` の `USER_AGENT` 内 URL を実リポジトリに更新（`976c753`）。
- push → Cloudflare 自動再デプロイ → 反映を確認。

**後片付け**
- 作業中に画面共有・シェル履歴へ露出した PAT 2本（`kisoko-scholarships-push`,
  `kisoko-scholarships-push2`）を GitHub 上で Delete。keychain のエントリも erase。
- 次回ローカルから push する際は PAT を新規発行（Contents + Workflows の
  Read and write、対象リポジトリのみ）。

**運用ループ（確立済み）**: 毎日 JST 06:00 に `scrape` → 変化があれば
`github-actions[bot]` がコミット → `main` 更新で Cloudflare Pages が自動再デプロイ。
手動作業なし。

---

## 現況スナップショット（2026-08-30 時点）

- ファイル 55（うち `tests/fixtures/` の実HTML 19本）。`public/index.html` 約 830 行、
  `scraper/` 約 1,100 行。テスト **39 件パス**（fixture ベース・ネットワーク不要）。
- 収録 **54 件**: JASSO 4 / トビタテ 1 / 船井 2 / 吉田 1 / 孫正義 1 / 大阪大学 45。
  学内推薦フラグ付き 25 件、確定締切 5 件。
- 全6ソースが実サイトに対して `ok` を確認済み。

## 既知の制約・TODO

- ~~**未デプロイ**~~ → フェーズ6 で完了（GitHub push・Cloudflare Pages 連携・
  `USER_AGENT` URL 更新すべて実施済み）。
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
