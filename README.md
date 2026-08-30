# 阪大基礎工 留学奨学金・補助金 検索ツール

大阪大学基礎工学部/基礎工学科および理工学系の学生が、海外留学時に応募できる
**公的・民間の奨学金/補助金の公募情報**を、無料・リアルタイムに近い鮮度で
一元検索できるツールです。

- **コストゼロ設計**: 検索・マッチング判定に有料 AI API を一切使いません。
- Python スクレイパーが 1 日 1 回情報を収集して `public/scholarships.json` を更新。
- フロントエンドは静的 HTML/CSS/JS の 1 ファイル。ブラウザ内 JavaScript で
  高速にフィルタリング・スコアリングして点数順に表示します。

詳しい設計は [`plan.md`](./plan.md) を参照してください。

---

## ディレクトリ構成

```
├── plan.md                 設計計画
├── requirements.txt        スクレイパー用パッケージ
├── public/                 Cloudflare Pages の公開ルート（静的サイト）
│   ├── index.html          検索 UI（1 ファイル完結）
│   ├── scholarships.json   スクレイパーが自動生成（コミット対象）
│   └── scholarships.sample.json  開発用サンプルデータ
├── scraper/                収集スクリプト（サイト別）
├── tests/                  pytest（fixtures を使ったオフラインテスト）
└── .github/workflows/      GitHub Actions（定期スクレイプ）
```

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
git remote add origin https://github.com/<ユーザー名>/kisoko-scholarships.git
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
