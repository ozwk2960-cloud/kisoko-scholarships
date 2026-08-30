# 阪大基礎工 留学奨学金・補助金 検索ツール

**公開サイト: <https://kisoko-scholarships.pages.dev/>**

大阪大学基礎工学部/基礎工学科および理工学系の学生が、海外留学時に応募できる
**公的・民間の奨学金/補助金の公募情報**を、無料・リアルタイムに近い鮮度で
一元検索できるツールです。

- **コストゼロ設計**: 検索・マッチング判定に有料 AI API を一切使いません。
- Python スクレイパーが 1 日 1 回情報を収集して `public/scholarships.json` を更新。
- フロントエンドは静的 HTML/CSS/JS の 1 ファイル。ブラウザ内 JavaScript で
  高速にフィルタリング・スコアリングして点数順に表示します。

詳しい設計は [`plan.md`](./plan.md) を参照してください。

### 情報取得元（スクレイパー）

| ソース | 取得内容 | 方式 |
|---|---|---|
| JASSO 海外留学支援制度 | 学部／大学院 学位取得型の年度別募集・締切・募集終了判定 | index→年度ページの HTML 解析 |
| トビタテ！留学JAPAN | 新・日本代表プログラム（大学生等）の期・募集状況 | ニュース見出し＋UVページ、金額は要項ベースで手入力 |
| 船井情報科学振興財団 | 大学院（博士）／学部 留学奨学金の締切・支援内容 | 応募要項の dt/dd 解析（締切は動的取得） |
| 吉田育英会 | 日本人派遣留学プログラムの対象年度・募集状況 | 要項ページ（詳細は PDF のため手入力併用） |
| 孫正義育英財団 | 財団生募集の期・募集状況（留学専用ではない） | 募集要項＋トップニュース、支援内容は手入力 |
| 大阪大学 留学助成制度 | 学内一覧に掲載の各奨学金（**学内推薦の有無つき**、約45件） | 一覧表の2セクションを行単位で解析 |

金額・対象学年など公募要項に載る安定情報は `scraper/config.py` に出典コメント付きで
手入力しており、募集要項公開時期に見直す運用とする。

---

## ディレクトリ構成

```
├── plan.md                 設計計画
├── requirements.txt        スクレイパー用パッケージ
├── public/                 Cloudflare Pages の公開ルート（静的サイト）
│   ├── index.html          検索 UI（1 ファイル完結）
│   ├── scholarships.json   スクレイパーが自動生成（コミット対象）
│   ├── deadlines.ics       確定した締切のカレンダー（自動生成・購読用）
│   ├── _headers            Cloudflare Pages 用ヘッダ／キャッシュ設定
│   └── scholarships.sample.json  開発用サンプルデータ
├── scraper/                収集スクリプト（サイト別）
├── tests/                  pytest（fixtures を使ったオフラインテスト）
└── .github/workflows/      GitHub Actions（定期スクレイプ／CI）
```

### 便利機能

- **検索条件の共有**: 絞り込み条件は URL クエリに反映される（`?d=doctor&f=情報&nom=none` など）。
  結果ヘッダの「🔗 この検索を共有」で現在の URL をコピーできる。
- **締切カレンダー**: `deadlines.ics` を Google カレンダー等に「URL で追加」すると、
  確定している締切（`deadline_type=fixed` かつ未来）が自動で反映される（毎日更新）。
  各カードの「📅 締切を追加」で1件だけカレンダーに入れることも可能。
- **アクセス解析（任意）**: Cloudflare Pages の Web Analytics を「自動セットアップ」に
  すればコード不要で計測できる（Cookie 不使用）。手動トークンで入れる場合は
  `public/index.html` 末尾のコメントアウト済みスニペットを有効化する。

---

## ローカル開発

### フロントエンド（スクレイパー不要）

```bash
cd public
python3 -m http.server 8000
# ブラウザで http://localhost:8000 を開く
```

`index.html` は `scholarships.json` が無い場合 `scholarships.sample.json` に
フォールバックします。

### スクレイパー

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m scraper.run            # public/scholarships.json を更新
python -m scraper.run --dry-run  # 標準出力に JSON を表示（ファイルは書き換えない）
pytest                           # テスト（fixture ベース・ネットワーク不要）
```

---

## デプロイ手順

### 1. GitHub リポジトリを作成して push

```bash
git config user.name  "あなたの名前"
git config user.email "あなたのメール"
git add -A && git commit -m "init: 留学奨学金検索ツール MVP"

# GitHub 上で空の public リポジトリ（例: kisoko-scholarships）を作成してから
git remote add origin https://github.com/ozwk2960-cloud/kisoko-scholarships.git
git push -u origin main
```

push 後、`scraper/config.py` の `USER_AGENT` 内の URL を実リポジトリ URL に更新すること。

### 2. GitHub Actions

- リポジトリ Settings → Actions → General →「Workflow permissions」を
  **Read and write permissions** にする（`scrape` ジョブが JSON をコミットするため）。
- Actions タブ → `scrape` → **Run workflow** で初回手動実行。
  `public/scholarships.json` が生成・コミットされる。
- 以降は毎日 **JST 06:00（UTC 21:00）** に自動実行。
  - 内容に変化がある時だけコミットする（`generated_at` だけの差分ではコミットしない）。
  - 一部ソースが失敗しても前回データを保持し、`source_status.ok=false` を立てる。
  - スキーマ検証に失敗した場合はコミットせずジョブが赤くなる。
- `ci` ワークフローが push / PR ごとに `pytest` を実行し、パーサ破損を検知する。
- 注: public リポジトリではリポジトリ無操作が 60 日続くと `schedule` が自動停止する。
  データ変化があればコミットで活動が記録されるため通常は問題ないが、長期間変化が
  無い場合は Actions タブから再有効化する。

### 3. Cloudflare Pages

1. Cloudflare ダッシュボード → Workers & Pages → Create → Pages → **Connect to Git**。
2. 対象リポジトリを選択し、以下を設定：
   | 項目 | 値 |
   |---|---|
   | Production branch | `main` |
   | Framework preset | None |
   | Build command | （空欄） |
   | Build output directory | `public` |
3. Deploy 実行。以降、`main` への push（＝Actions のデータ更新コミット）ごとに自動再デプロイ。
4. 発行された `*.pages.dev` の URL を README とフッタ（`index.html` の `footMeta` 付近）に記載。
   （本リポジトリでは `https://kisoko-scholarships.pages.dev/` を設定済み）
5. 任意: カスタムドメイン、Cloudflare Web Analytics（無料）を追加。

`public/_headers` でセキュリティヘッダと `scholarships.json` のキャッシュ（1時間）を設定済み。

---

## 免責・運用方針

- 本ツールは公表済みの公募情報を集約する**入口**です。応募資格・締切・金額は
  必ず各奨学金の**公式ページ**で最新情報を確認してください。
- スクレイピングは各サイトの `robots.txt` と利用規約を尊重し、1 日 1 回・
  低頻度でのみ実行します。収集するのは事実情報（タイトル・締切・金額・URL）に限り、
  本文は 200 字以内の要約と一次情報リンクのみを保持します。
- 情報の取得日時は UI 上部に「最終更新」として表示されます。
