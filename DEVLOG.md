# 開発ログ — 阪大基礎工 留学奨学金・補助金 検索ツール

対象期間: 2026-08-30〜08-31（フェーズ0〜6 を初日、フェーズ7 を翌日）
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
| `c45210f` | 2026-08-31 | docs: フェーズ6（本番デプロイ）を開発ログに追記 |
| `d190db4` | 2026-08-31 | docs: 運用方針を記録 + 作業メモ類を gitignore（誤コミット `730397c` のリカバリ）|
| `95dcb23` | 2026-08-31 | ci: `[skip ci]` 除去でサイト反映を確実化 + 月次 keepalive（フェーズ7）|

ブランチ `main`、リモート `origin` = GitHub（push 済み・Cloudflare Pages 連携済み）。
GitHub 反映は `95dcb23` まで。この後の DEVLOG 追記コミットは別途 push が必要。

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

**運用ループ（この時点）**: 毎日 JST 06:00 に `scrape` → 変化があれば
`github-actions[bot]` がコミット → `main` 更新で Cloudflare Pages が自動再デプロイ。
手動作業なし。（→ フェーズ7 で keepalive と `[skip ci]` 修正を追加）

## フェーズ7 — 運用堅牢化（2026-08-31）

デプロイ後、「公開の期限切れ」に相当するものを棚卸しし、日程管理が不要になるよう対策。

**棚卸し結果**: サイトが止まる期限は存在しない。
- Cloudflare Pages / `.pages.dev` / GitHub public リポジトリ / Cloudflare↔GitHub 連携
  … いずれも無期限。
- PAT は期限つきだが、Actions（`GITHUB_TOKEN` を使用）にも Cloudflare にも無関係。
  影響はローカルからの `git push` だけ。
- 唯一の実リスク = **GitHub Actions `schedule` は60日間リポジトリ無活動で自動停止**
  （public リポジトリ）。停止時は管理者宛に GitHub が自動メール通知。

**対策（コミット `95dcb23`）**
1. **月次 keepalive**: `scrape.yml` に「毎月1日、空コミットを1つ push」するステップを追加
   （`if: github.event_name == 'schedule'` かつ `date +%d == 01`）。最大でも約30日ごとに
   活動が記録され、60日ルールに構造的に到達しない。人間の日程管理が不要になる。
2. **`[skip ci]` 由来のデプロイ抜けを修正**: 日次データコミットのメッセージに付けていた
   `[skip ci]` は、**Cloudflare Pages も**（大文字小文字を問わず）検知してビルドを
   スキップする。このままだと「毎日収集・コミットするがサイトに反映されない」状態に
   なるところだった（データ未変化のため顕在化前に発見）。データコミットから `[skip ci]`
   を除去し、代わりに `ci.yml` の push トリガに `paths-ignore`（`public/scholarships.json`,
   `public/deadlines.ics`）を設定して pytest の二重実行を回避。
   - keepalive の空コミットには `[skip ci]` を残す（配信物に影響しないためビルド不要）。

**この push 時の小ハマり**: コミットメッセージに説明として書いた「（[skip ci] 除去）」の
文字列を GitHub が拾い、この push の `ci` 実行自体がスキップされた（実害なし・ローカルで
39件パス済み・コード/データ変更なし）。以後の通常コミットでは `ci` は走る。

**後片付け**: 今回発行した PAT（`kisoko-push-202608` 相当）も使用後に Delete、keychain
も erase。ローカル push が必要になったら都度発行する運用（Contents + Workflows の
Read and write、対象リポジトリのみ、の Fine-grained PAT）。

**確立した運用ループ（最終形）**
```
毎日 06:00 JST  scrape 実行
  ├─ データに実質変化あり → github-actions[bot] がコミット → push
  │                          → Cloudflare Pages が自動再デプロイ（[skip ci] なし）
  ├─ タイムスタンプのみ / 変化なし → コミットせず
  └─ 毎月1日 → 空コミット（keepalive）で活動記録 → schedule 停止を防止
push / PR（人間の変更） → ci（pytest + スキーマ検証）。ただし public/*.json,
  *.ics のみの push は paths-ignore でスキップ。
```
運用上、人間が定期的に行う作業は無し（募集要項切替時期の `config.py` 見直しは任意）。

**公開範囲の方針（2026-08-31 確認）**: サイト・GitHub リポジトリとも **完全公開**
（認証なし、検索エンジンのインデックス対象）。掲載内容は公表済みの公募情報と一次リンク
のみのため問題なし。「学内向けに広く使ってほしい」目的に合致するため、Cloudflare Access
による限定公開や `noindex` は導入しない。
- 共有方法: URL をそのまま配布。絞り込み状態は「🔗 この検索を共有」でURL化。
  締切カレンダーは `deadlines.ics` を各自のカレンダーに URL 購読。

## フェーズ8 — 絞り込み精度の全面見直し（2026-11-09）

**きっかけ**: 「学部／システム科学／交換留学／学内推薦が不要」で検索すると、大学院生向けの
【INPEX教育交流財団】が出てくる（利用者報告）。阪大の留学助成ページより便利に絞り込めることが
このツールの存在意義なので、全体を再点検した。

### 原因（3つ重なっていた）
1. **フロントが「不明」と「確認済みの不一致」を区別していなかった**。通常モードでは不一致を除外せず、
   学年・種別が空の制度は素通りしていた。
2. **阪大由来 43 件のデータが空 or 決め打ち**。`target_degree` / `study_type` は空、
   `target_fields` は常に「全分野」、`destination_countries` は常に「全世界」。確認していない値を
   事実として入れており、「不明は推測で埋めない」の方針にも反していた。
3. **直接応募 21 件は阪大ページに【対象】が無く**、そのままでは何も判定できない。

### 対応
- **フロント（`public/index.html`）**: 条件ごとの判定を 4 値（na / match / mismatch / unknown）に変更。
  - mismatch（確認済みで条件に合わない）は**常に除外**。
  - unknown は通常モードでは残して**カードに「要確認」を明示**、スコア加点なし。
    「確認できたものだけ表示」をオンにすると unknown も除外。
  - 「全分野／理工系／理系／自然科学／工学」は基礎工のどの専攻にも一致扱い。
  - 判定ロジックは `MATCH-LOGIC:START/END` で区切り、node から単体テスト可能にした。
  - 留学先キーワードに インドネシア・ベトナム・フィリピン・ハワイ を追加。
- **スクレイパー（`scraper/sources/osaka_u.py`）**: 決め打ちをやめ、【対象】とタイトルに
  **明記された語だけ**を解析（学部生→bachelor、本学大学院の正規生→master+doctor、
  博士前期課程→master、理系→理工系、交換留学／語学、留学先の国名）。読めなければ空＝要確認。
- **公式情報の補正表（`config.OSAKA_CURATED`）**: 【対象】が無い直接応募の制度を、財団・機関の公式ページで
  確認できた事実だけ手で記録（財団名キーなので年度が変わっても効く）。INPEX は
  修士・博士のみ／留学先 インドネシア・オーストラリア・UAE。
- **テスト**: 39 → **51 件**。`tests/test_frontend_logic.py`（node で判定ロジックを実行。
  利用者の検索条件を実データで再現）、阪大の解析・補正のテスト、2026-11 時点の阪大ページの
  スナップショット fixture を追加。

### 結果
利用者の検索条件では INPEX が消え、残るのは「学部を確認済み」の 1 件と「要確認」の 6 件
（要確認の理由はカードに表示）。厳格モードでは 0 件。

### 残っている限界（正直に）
- 学年・種別が確認できていない制度は「要確認」のまま: アポロ／福井県／経団連GL／大蔵共助会／
  SEKAIA／竹中育英会／寺浦／東京GP／フクシマ短期 ほか。公式ページが PDF／JS 描画で自動で読めない。
- **村田海外留学奨学会は公式サイトが自動アクセスに 403**。ヘッダ偽装などの回避はせず未確認のまま。
- 阪大の行には締切が無いため、募集終了済みの年度でも「締切未定」と表示される
  （補正表に年度ごとの締切を書くと次年度に古くなるため入れていない）。
- 阪大一覧に「フランス政府奨学金」が 2027 年度と 2026-2027 年度で 2 件ある（原ページの重複）。
- 吉田育英会は今回の実行で 503（一時的）。前回分を保持してマージされた。
- 補正表の内容は各財団の募集要項の改訂で変わりうる。募集要項公開時期に見直す。

### 公開と後片付け（2026-11-09）
- コミット `b1b2777` を `git push origin main`（`7e9f634..b1b2777`）で公開。Workflows 権限は不要（workflow 未変更）。
- 公開サイトで確認: 「学部／システム科学／交換留学／推薦不要」は 7 件・INPEX なし・全件に「要確認」表示。
- 後片付け: 使い捨ての fine-grained PAT（Contents: Read and write のみ）を GitHub 上で削除、
  キーチェーンの認証情報も `git credential-osxkeychain erase` で消去済み。

## 誤コミットとリカバリ（2026-08-31）

`git add -A` で開発ログをコミットした際、ユーザーがプロジェクト直下に置いていた作業
メモ 128 ファイル（スクショ `.png`、`.docx` / `.rtf` / `.pdf`、**トークン名の `.rtf`
を含む**）を巻き込んで `730397c` を作成してしまった。push 前に気付き、
`git reset --soft HEAD~1` で取り消し。GitHub 側への影響なし（当該時点で未 push）。
再発防止として `.gitignore` に `スクショ*/` と `*.docx *.rtf *.pdf *.png *.jpg`
（`tests/**/*.png` は例外許可）を追加（コミット `d190db4`）。今後この種のファイルは
自動で無視される。露出したトークンはいずれも GitHub 上で Delete 済み＝無効。

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
- 阪大の各行の `target_degree` 等は【対象】の明記分＋`OSAKA_CURATED` のみ。不明は空で「要確認」表示（フェーズ8）。
- 2件構成ソース（船井）は片方のプログラムが落ちるともう片方も欠落（フェイルセーフで
  前回分は保持）。JASSO も同様に年度単位の失敗は全体失敗になる。
- JASSO 大学院・トビタテの金額は Web 検索由来のキュレーション値。PDF 解析（pdfminer 等）は
  将来対応。
- public リポジトリは 60 日無操作で `schedule` が停止 → Actions タブから再有効化。
- 阪大の政府奨学金系エントリ（スイス/フランス政府奨学金など）は締切未定でスコアが低め。
