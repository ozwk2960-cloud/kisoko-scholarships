# plan.md — 阪大基礎工 留学奨学金・補助金 検索ツール 設計計画

## Context（この計画の目的）

大阪大学基礎工学部/基礎工学科および理工学系の学生が、海外留学時に応募できる
**公的・民間の奨学金/補助金の公募情報**を、**無料・リアルタイムに近い鮮度**で
一元検索できるツールを作る。既存の情報は JASSO・トビタテ・各財団サイトに
分散しており、学生が毎回巡回するのは非効率。締切を見逃すリスクも高い。

本ツールは「Python で 1 日 1 回スクレイピング → `scholarships.json` を自動更新 →
静的フロントエンドが JS だけで絞り込み/スコアリング」という構成で、
**AI API を含む有料サービスを一切使わずコストゼロ**で運用する。
第一段階（MVP）の成果物はこの `plan.md`（開発手順・ディレクトリ構造・
スクレイピング対象 URL 設計案）である。

### 確定した前提（ヒアリング結果）
- スクレイピング技術: **軽量版（requests + BeautifulSoup + lxml）**。JS 描画ページは
  公式 PDF / 一覧 HTML / RSS を優先的に狙う。Playwright は必要が判明したソースだけ後日追加。
- MVP 初期対象: **JASSO + トビタテ！留学JAPAN の 2 件**。土台が固まってから財団・阪大を追加。
- 阪大情報: **公開ページ（ログイン不要分）のみ**。学内限定ポータルは対象外、UI から公式ページへリンク誘導。
- ホスティング: **新規 GitHub リポジトリを作る前提**。GitHub Actions（cron）+ Cloudflare Pages。

---

## 1. 全体アーキテクチャ

```
┌─────────────────┐   1日1回 (cron)    ┌──────────────────────┐
│ GitHub Actions  │ ───────────────▶ │ scraper/ (Python)     │
│ scheduled job   │                   │  各サイト別スクレイパー  │
└─────────────────┘                   └──────────┬───────────┘
        │                                        │ 正規化・マージ・重複排除
        │ git commit & push                      ▼
        │                             ┌──────────────────────┐
        └────────────────────────────▶│ public/scholarships.json │ (生成物をコミット)
                                      └──────────┬───────────┘
                                                 │ Cloudflare Pages が
                                                 │ public/ を自動デプロイ
                                                 ▼
                                      ┌──────────────────────┐
                                      │ public/index.html     │
                                      │  fetch(json) → JSでフィルタ│
                                      │  → スコアリング → 点数順表示 │
                                      └──────────────────────┘
```

- **バックエンドは存在しない**（サーバーレスですらなく、ビルド時生成の静的サイト）。
- フロントは `public/` 配下の完全静的ファイル。`scholarships.json` も `public/` に置き同一オリジンで `fetch`。
- スクレイピング失敗時は **前回の JSON を保持**（後述のフェイルセーフ）。

---

## 2. ディレクトリ構造

```
基礎工用奨学金・補助金検索ツール開発/
├── plan.md                     # 本ファイル（成果物）
├── README.md                   # セットアップ/デプロイ手順
├── requirements.txt            # requests, beautifulsoup4, lxml, python-dateutil, jsonschema
├── .gitignore
│
├── public/                     # ← Cloudflare Pages の公開ルート
│   ├── index.html              # 1ファイル完結MVP（CSS/JSインライン）
│   ├── scholarships.json       # スクレイパーが自動生成（コミット対象）
│   └── scholarships.sample.json# 開発用サンプル（手書き, 数件）
│
├── scraper/
│   ├── __init__.py
│   ├── run.py                  # エントリポイント: 全ソース実行→マージ→検証→書き出し
│   ├── config.py               # 対象URL・セレクタ・レート制御の定義
│   ├── models.py               # Scholarship dataclass + 正規化ヘルパ
│   ├── normalize.py            # 日付/金額/対象学年などの表記ゆれ吸収
│   ├── merge.py                # 複数ソース統合・重複排除（キー: source+title+deadline）
│   ├── schema.json             # scholarships.json の JSON Schema（jsonschemaで検証）
│   └── sources/
│       ├── base.py             # BaseSource: fetch(), parse(), 共通リトライ/UA/robots確認
│       ├── jasso.py            # JASSO 海外留学支援制度
│       ├── tobitate.py         # トビタテ！留学JAPAN
│       ├── osaka_u.py          # （フェーズ4）阪大 留学・奨学金 公開ページ
│       ├── yoshida.py          # （フェーズ4）吉田育英会
│       ├── funai.py            # （フェーズ4）船井情報科学振興財団
│       └── masason.py          # （フェーズ4）孫正義育英財団
│
├── tests/
│   ├── fixtures/               # 各サイトの保存済みHTML（オフラインテスト用）
│   ├── test_normalize.py
│   ├── test_merge.py
│   ├── test_schema.py          # 生成JSONがschemaに適合するか
│   └── test_sources_parse.py   # fixtures を parse() に通し件数・必須項目を検証
│
└── .github/
    └── workflows/
        └── scrape.yml          # cron: '0 21 * * *' (JST 6:00) 手動実行(dispatch)も可
```

---

## 3. データスキーマ（`public/scholarships.json`）

```jsonc
{
  "generated_at": "2026-08-30T21:00:00Z",   // 最終更新(UTC)
  "source_status": [                          // 各ソースの成否（UIで鮮度バッジ表示）
    { "source": "JASSO", "ok": true,  "count": 12, "fetched_at": "..." },
    { "source": "トビタテ", "ok": false, "error": "HTTP 503", "stale_since": "..." }
  ],
  "scholarships": [
    {
      "id": "jasso-2026-kaigai-shien-001",   // 安定ID（source + slug）
      "source": "JASSO",                      // 情報取得元
      "source_url": "https://www.jasso.go.jp/...",  // 一次情報へのリンク（必須）
      "title": "2026年度 海外留学支援制度（大学院学位取得型）",
      "provider": "日本学生支援機構",           // 実施団体
      "category": "public",                   // public | university | private
      "amount_text": "月額 89,000〜148,000円 + 授業料",
      "amount_monthly_jpy": 89000,            // 数値化できた分（絞り込み用, null可）
      "target_degree": ["master", "doctor"],  // bachelor|master|doctor|research
      "target_fields": ["理工系", "全分野"],    // 専攻タグ（緩め）
      "eligible_universities": ["大阪大学", "全国"], // 阪大対象かの判定に使用
      "requires_university_nomination": true, // 学内推薦の要否（不明時 null）
      "destination_countries": ["全世界"],     // 留学先（"欧州","米国"等 or "全世界"）
      "study_type": ["学位取得", "研究"],       // 学位取得 | 交換留学 | 研究 | 語学 | インターン
      "duration_text": "1年以上",
      "deadline": "2026-10-15",               // ISO date（学内締切）or null（通年/不明）
      "deadline_type": "fixed",               // fixed | rolling | annual | unknown
      "application_period_text": "2026年9月上旬〜10月中旬",
      "description": "…要約（原文抜粋、200字以内）…",
      "tags": ["返済不要", "併給不可"],
      "last_seen": "2026-08-30",              // 直近スクレイプで存在確認できた日
      "first_seen": "2026-07-01"
    }
  ]
}
```

- **必須フィールド**: `id, source, source_url, title, provider, category, last_seen`。
- 解析できなかった項目は **`null` を明示**（欠損とハルシネーションを区別）。
- スクレイパーは推測で値を埋めない。学内推薦・金額など曖昧なものは `null` + `*_text` に原文。

---

## 4. スクレイピング設計

### 4-1. 対象 URL 設計案（実装時に各ページ構造を要確認）

| フェーズ | source キー | 起点 URL（候補） | 取得対象 | 想定手段 |
|---|---|---|---|---|
| **2 (MVP)** | JASSO | `https://www.jasso.go.jp/ryugaku/scholarship_j/shk_sei/` 海外留学支援制度トップ | 制度一覧・募集要項ページ・PDF 内の締切/金額 | 一覧HTML + 詳細HTML。PDF は `pdfminer.six` を将来検討、まずはHTML本文 |
| **2 (MVP)** | トビタテ | `https://tobitate-mext.jasso.go.jp/`（新・日本代表プログラム 大学派遣） | 募集スケジュール・対象・支援内容ページ | HTML。JS描画なら「よくある質問」「募集要項PDF」ページを直接狙う |
| **4** | 阪大 | `https://www.osaka-u.ac.jp/ja/campus/life/scholarship` /`.../international/action/students_dispatch` | 公開されている派遣留学・奨学金一覧、学内締切 | HTML。ログイン必須ページは除外 |
| **4** | 吉田育英会 | `https://www.ysfellow.or.jp/`（海外留学部門） | 募集要項・応募資格・締切 | HTML |
| **4** | 船井情報科学振興財団 | `https://funaifoundation.jp/`（海外留学奨学金） | 募集要項・対象（情報科学分野）・締切 | HTML |
| **4** | 孫正義育英財団 | `https://masason-foundation.org/`（募集ページ） | 募集時期・対象・支援内容 | HTML。通年/不定期のため `deadline_type: rolling/unknown` 中心 |

> フェーズ3は「フロント + Actions + Cloudflare」を JASSO/トビタテだけで通す配管確立に充てる。

### 4-2. 各スクレイパーの共通方針（`sources/base.py`）
- **robots.txt を起動時に確認**（`urllib.robotparser`）。Disallow ならそのソースをスキップし `source_status` に記録。
- User-Agent は素性を明示（例: `KisokoScholarshipBot/0.1 (+<repo URL>; contact <email>)`）。
- **アクセス間隔 2〜5 秒**、リクエスト数はソースあたり数十以内。1 日 1 回のみ。
- タイムアウト 20 秒、指数バックオフで最大 3 リトライ。
- 取得 HTML は `tests/fixtures/` 更新用にオプションで保存可能（`--save-fixtures`）。
- パースは CSS セレクタ主体、**セレクタは `config.py` に集約**して HTML 変更時の修正を局所化。

### 4-3. フェイルセーフ（鮮度と信頼性）
- `run.py` は **全ソース成功を前提にしない**。成功分だけ新データ、失敗ソースは
  **既存 `scholarships.json` の該当 source エントリを流用**し `source_status.ok=false` を立てる。
- 生成 JSON は書き出し前に `schema.json` で検証。検証失敗時は **既存ファイルを上書きしない**（非ゼロ終了）。
- 1 ソースの全消失（前回 N 件 → 今回 0 件）は異常とみなし、そのソースは前回分を維持して警告。
- Actions は差分がある時のみ commit（`git diff --quiet` 判定）。

### 4-4. 法的・倫理的配慮（README にも明記）
- 収集するのは**公表済みの公募情報の事実（タイトル・締切・金額・URL）**のみ。原文の大量転載はせず要約 200 字以内 + 一次情報リンク必須。
- robots.txt / 各サイト利用規約を尊重。低頻度・低負荷アクセス。
- ツールはあくまで**入口**であり、応募可否は必ず公式ページで確認する旨を UI に常時表示。

---

## 5. フロントエンド設計（`public/index.html` 単一ファイル）

### 5-1. 技術
- 依存ライブラリなし（Vanilla JS）。CSS はインライン `<style>`。
- 起動時 `fetch('./scholarships.json')` → メモリ保持 → 入力変更で即時再描画（数百件なら十分高速）。
- レスポンシブ: CSS Grid / Flexbox、モバイル 1 カラム / PC 2〜3 カラム。
- 配色: 白背景 + 青系アクセント（`#1a56db` 系）、角丸カード、余白広め。ダーク対応は任意（後回し可）。

### 5-2. 絞り込み条件（フィルタ UI）
| 条件 | UI | JSON マッピング |
|---|---|---|
| 学年/課程 | セグメント（学部/修士/博士/研究生） | `target_degree` |
| 専攻分野 | チップ選択（情報/物性/化学工学/システム… + 「全分野」） | `target_fields` |
| 留学先 | セレクト（全世界/北米/欧州/アジア/オセアニア…） | `destination_countries` |
| 留学種別 | チェック（学位取得/交換/研究/語学/インターン） | `study_type` |
| 学内推薦 | ラジオ（不問/推薦不要のみ/推薦ありでも可） | `requires_university_nomination` |
| 阪大対象のみ | トグル | `eligible_universities` に「大阪大学」or「全国」 |
| 締切 | トグル「締切が過ぎたものを隠す」/「30日以内」 | `deadline` |
| フリーワード | テキスト（title/provider/description 部分一致） | 複数フィールド |

### 5-3. スコアリング（点数順表示、AI 不使用の決定的ロジック）
```
score = 0
+ 条件一致ボーナス:
  - target_degree が選択学年に一致 ............ +30（未選択時は加点なし）
  - target_fields が選択専攻に一致/「全分野」 .... +20
  - destination_countries が選択先を包含 ....... +15
  - study_type 一致 ........................... +10
  - 阪大対象（eligible に阪大/全国） ............ +15
  - 学内推薦条件がユーザー希望と両立 ............ +10
+ 締切の近さ:
  - 残り 7日以内 +12 / 8〜30日 +8 / 31〜90日 +4 / 過去 −50 / 不明 0
+ 金額:
  - amount_monthly_jpy を 0〜10 点に正規化（10万円以上で満点）
+ 情報の鮮度:
  - last_seen が 3日以内 +3

除外（score にせずリスト非表示 or 末尾）:
  - 「締切が過ぎたものを隠す」ON かつ deadline < 今日
  - ハードフィルタ（阪大対象のみ ON で非対象）に不一致
```
- 同点は締切昇順 → title 昇順。
- 各カードに「なぜこの順位か」を小さくバッジ表示（例: 「専攻一致 / 締切23日」）。

### 5-4. 表示要素
- ヘッダ: ツール名、`generated_at` を「最終更新: YYYY/MM/DD」で表示、失敗ソースがあれば黄色帯で告知。
- カード: タイトル / 実施団体 / 金額テキスト / 締切（残り日数バッジ） / 種別タグ / 「公式ページを見る」ボタン。
- 該当 0 件時のガイド文、フィルタ全解除ボタン。

---

## 6. インフラ

### 6-1. GitHub Actions（`.github/workflows/scrape.yml`）
- トリガー: `schedule: cron '0 21 * * *'`（UTC 21:00 = JST 翌 6:00）+ `workflow_dispatch`。
- ジョブ: `actions/checkout` → `setup-python@v5`（3.12）→ `pip install -r requirements.txt`
  → `python -m scraper.run` → 差分あれば `git commit`（`github-actions[bot]`）→ `git push`。
- 権限: `permissions: contents: write`。所要時間 1〜2 分想定（無料枠内で余裕）。
- 失敗しても既存 JSON は壊さない設計なので、通知は Actions 標準のメールで足りる。

### 6-2. Cloudflare Pages
- GitHub リポジトリ連携、**Production ブランチ = `main`**、**出力ディレクトリ = `public`**、ビルドコマンドなし（静的）。
- Actions が `public/scholarships.json` を push するたび自動再デプロイ。
- 無料枠（リクエスト無制限、帯域実質無制限）で十分。カスタムドメインは任意。

### 6-3. リポジトリ初期セットアップ手順（README に記載）
1. GitHub で public リポジトリ作成、本ディレクトリを push。
2. Cloudflare Pages で「Connect to Git」→ 当該リポジトリ選択 → 上記設定でデプロイ。
3. Actions を有効化（public リポジトリは既定で有効）。`workflow_dispatch` で初回手動実行し JSON を生成。
4. 生成された Pages URL を README とツールのフッタに記載。

---

## 7. 開発手順（フェーズ分割）

### フェーズ 0: リポジトリ雛形
- ディレクトリ作成、`requirements.txt` / `.gitignore` / `README.md` 骨子、`public/scholarships.sample.json`（手書き 3〜4 件）。

### フェーズ 1: フロントエンド MVP（サンプル JSON 駆動）
- `public/index.html` を単体で完成させる。`scholarships.sample.json` を読み、全フィルタ + スコアリング + レスポンシブを実装。
- ローカルで `python -m http.server` で確認。**この時点でスクレイパー無しでも「使える画面」ができる**。

### フェーズ 2: スクレイパー基盤 + JASSO/トビタテ
- `models.py` / `normalize.py` / `merge.py` / `schema.json` / `sources/base.py`。
- `sources/jasso.py`, `sources/tobitate.py` を実装。`tests/fixtures/` に保存 HTML を置きオフラインテスト。
- `python -m scraper.run` で `public/scholarships.json` を生成 → フロントを実データに切替。

### フェーズ 3: 自動化（Actions + Cloudflare）
- `scrape.yml` 追加、GitHub リポジトリ作成、Cloudflare Pages 連携、初回手動実行で公開。

### フェーズ 4: ソース拡充
- `osaka_u.py` → `yoshida.py` → `funai.py` → `masason.py` を 1 つずつ追加（各: fixture + parse テスト + `config.py` 追記）。
- JS 描画で HTML 取得不可のソースが出たらここで Playwright 併用を再検討。

### フェーズ 5: 運用改善（任意）
- 締切リマインド用の ICS 生成、URL パラメータでフィルタ共有、簡易アクセス解析（Cloudflare Web Analytics 無料）。

---

## 8. 検証方法（受け入れ基準）

**スクレイパー**
- `pytest` 全緑。特に `test_schema.py`（生成 JSON が `schema.json` に適合）、`test_sources_parse.py`（各 fixture から 1 件以上抽出・必須項目非 null）。
- `python -m scraper.run --dry-run` で JSON を stdout 出力し目視で締切/金額/URL が正しいか確認。
- 片方のソースを故意に 404 化 → 既存データ保持 + `source_status.ok=false` になることを確認（フェイルセーフ）。
- robots.txt Disallow のダミーを食わせ、当該ソースがスキップされることを確認。

**フロントエンド**
- ローカル `http.server` で `sample.json` / 実 `scholarships.json` 両方が読める。
- 各フィルタ操作で件数と並び順が期待通り（例: 修士 + 情報系 + 締切30日以内 → 上位に該当制度）。
- スマホ幅（375px）と PC 幅（1280px）でレイアウト崩れなし。
- `scholarships.json` を空配列にしても 0 件ガイドが出てクラッシュしない。
- 失敗ソースありの JSON で黄色帯の告知が出る。

**自動化**
- `workflow_dispatch` で Actions 実行 → `public/scholarships.json` が更新コミットされる。
- Cloudflare Pages が再デプロイされ、公開 URL で最新 `generated_at` が表示される。

---

## 9. 主要リスクと対策

| リスク | 対策 |
|---|---|
| 対象サイトの HTML 変更でパース破綻 | セレクタを `config.py` 集約 / parse テストで検知 / 破綻時は前回分維持 |
| JS 描画で本文が取れない | まず PDF・一覧・FAQ ページを狙う。ダメならフェーズ4で Playwright 限定投入 |
| 「学内推薦の有無」が機械判定困難 | 無理に埋めず `null` + 原文テキスト表示。フィルタは「不問」を既定に |
| スクレイピングの規約抵触懸念 | 事実情報のみ・低頻度・要約+一次リンク・robots 尊重（§4-4） |
| 情報の鮮度誤認 | `generated_at` と `source_status` を UI 前面に表示、公式確認を促す文言常設 |

---

## 10. この計画で作らないもの（YAGNI）

- ユーザー登録 / ログイン / お気に入り保存（DB 不要のため）。
- サーバーサイド API・データベース。
- AI による自動マッチングや自然文要約（コストゼロ方針）。
- 学内限定ポータルのスクレイピング。
- 多言語 UI（まず日本語のみ）。
