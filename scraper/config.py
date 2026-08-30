"""スクレイピング対象の定義と、各制度の手入力メタデータ。

このファイルの「CURATED_*」は公式の募集要項・募集ちらしから **人手で転記した安定的な事実** であり、
スクレイパーが本文から推測した値ではない。金額改定や制度変更のたびに（年1回、募集要項公開時期に）
公式資料と突き合わせて更新すること。出典 URL を必ずコメントで残す。

HTML 構造に依存するセレクタ・URL はここに集約し、サイト改修時の修正箇所を局所化する。
"""

from __future__ import annotations

# ---- ネットワーク動作 ---------------------------------------------------------

# HTTP ヘッダは latin-1 のみ。日本語を入れないこと。
USER_AGENT = (
    "KisokoScholarshipBot/0.1 "
    "(+https://github.com/example/kisoko-scholarships; scholarship search tool for Osaka Univ. students)"
)
REQUEST_TIMEOUT = 20          # 秒
MAX_RETRIES = 3
BACKOFF_BASE = 2.0           # 秒（指数バックオフ: base * 2**attempt）
POLITE_DELAY = 3.0          # 同一ソース内の連続リクエスト間隔（秒）

# ---- JASSO 海外留学支援制度 -------------------------------------------------

JASSO_BASE = "https://www.jasso.go.jp"

# 対象プログラム。index ページから年度別ページ（YYYY.html）を辿る。
# enabled=False のものは当面スキップ（協定派遣は個人応募の公募がなく、年度ページが
# 「採用学生専用ページ」のため MVP では扱わない）。
JASSO_PROGRAMS = [
    {
        "key": "daigakuin",
        "label": "大学院学位取得型",
        "index_url": f"{JASSO_BASE}/ryugaku/scholarship_a/daigakuin/index.html",
        "enabled": True,
    },
    {
        "key": "gakubu",
        "label": "学部学位取得型",
        "index_url": f"{JASSO_BASE}/ryugaku/scholarship_a/gakubu/index.html",
        "enabled": True,
    },
    {
        "key": "haken",
        "label": "協定派遣",
        "index_url": f"{JASSO_BASE}/ryugaku/scholarship_a/haken/index.html",
        "enabled": False,
    },
]

# 直近何年度分の年度ページを取得するか（募集中＋直前年度）
JASSO_YEARS_TO_FETCH = 2

# 各プログラムの手入力メタデータ。
# 出典: 2026年度 募集ちらし / 募集要項（https://www.jasso.go.jp/ryugaku/scholarship_a/<key>/index.html）
CURATED_JASSO = {
    "daigakuin": {
        "provider": "日本学生支援機構（JASSO）",
        "amount_text": "月額 177,000〜388,000円（国・地域により異なる）＋ 授業料（上限あり）。"
                       "特別枠は月額 227,000〜833,000円。詳細は募集要項を参照。",
        "amount_monthly_jpy": 177000,   # 一般枠の下限（2026年度募集ちらし）
        "target_degree": ["master", "doctor"],
        "target_fields": ["全分野"],
        "study_type": ["学位取得"],
        "requires_university_nomination": True,   # 原則「大学取りまとめ応募」
        "eligible_universities": ["全国"],
        "tags": ["返済不要", "学内取りまとめ応募", "個人応募枠あり"],
    },
    "gakubu": {
        "provider": "日本学生支援機構（JASSO）",
        "amount_text": "月額 139,000〜352,000円（国・地域により異なる）＋ 授業料（上限あり）。"
                       "詳細は募集要項を参照。",
        "amount_monthly_jpy": 139000,   # 下限（2026年度募集ちらし）
        "target_degree": ["bachelor"],
        "target_fields": ["全分野"],
        "study_type": ["学位取得"],
        "requires_university_nomination": True,
        "eligible_universities": ["全国"],
        "tags": ["返済不要", "学内取りまとめ応募", "個人応募枠あり"],
    },
}

# 年度ページ内の抽出ヒント
JASSO_SCHEDULE_HEADING_RE = r"応募受付.*日程|応募・?選考.*日程|実施日程"
JASSO_DEADLINE_ROW_RE = r"応募書類.*提出|出願書類.*提出|書類提出"
JASSO_CLOSED_RE = r"募集終了|募集は終了|受付終了"

# ---- トビタテ！留学JAPAN 新・日本代表プログラム（大学生等対象） --------------

TOBITATE_BASE = "https://tobitate-mext.jasso.go.jp"
TOBITATE_TOP_URL = f"{TOBITATE_BASE}/"
TOBITATE_UV_URL = f"{TOBITATE_BASE}/newprogram/uv/"

# 出典: https://tobitate-mext.jasso.go.jp/newprogram/uv/ および大学生等対象 募集要項PDF
CURATED_TOBITATE_UV = {
    "provider": "文部科学省／官民協働海外留学支援制度（トビタテ！留学JAPAN）",
    "amount_text": "返済不要。月額 60,000〜160,000円（地域による）＋ 授業料負担金（最大60万円）"
                   "＋ 事前・事後研修参加費。留学期間・活動内容により異なる。詳細は募集要項を参照。",
    "amount_monthly_jpy": 60000,   # 下限
    "target_degree": ["bachelor", "master", "doctor"],
    "target_fields": ["全分野"],
    "study_type": ["学位取得", "研究", "インターン", "語学", "交換留学"],
    "requires_university_nomination": True,   # 在籍大学の学内選考を経て応募
    "eligible_universities": ["全国"],
    "tags": ["返済不要", "学内選考あり", "事前・事後研修必須", "留学大使活動"],
    "duration_text": "28日以上2年以内",
    "description": "官民協働の留学支援制度。留学計画を自分で設計でき、研究・インターン・"
                   "ボランティア・語学・学位取得など幅広い活動が対象。成績・語学力の"
                   "足切りは原則なし。民間寄附を原資とする返済不要の奨学金。事前・事後研修と"
                   "留学後の情報発信（留学大使活動）が必須。理工系向けの STEAM コースあり。",
}

# トビタテ top ページのニュース見出しから募集状況を判定するための正規表現
TOBITATE_PROGRAM_RE = r"新・?日本代表プログラム"
TOBITATE_UNIV_RE = r"大学生等|大学生・大学院生|大学生"
TOBITATE_OPEN_RE = r"募集開始|募集を開始|募集中です"
TOBITATE_CLOSED_RE = r"募集終了|募集を終了"
TOBITATE_TERM_RE = r"第\s*([0-9]{1,3})\s*期"
# ニュース見出し中の「大学生等（第N期）」から大学生等プログラムの期を取る
TOBITATE_UNIV_TERM_RE = r"大学生等\s*[（(]\s*第\s*([0-9]{1,3})"

# ---- 船井情報科学振興財団 --------------------------------------------------

FUNAI_BASE = "https://funaifoundation.jp"
# 応募要項ページは <dl><div><dt>ラベル</dt><dd>内容</dd></div></dl> 構造。
# 「応募期間」dd から締切、「支援内容」dd から金額テキストを動的に取得する。
FUNAI_PROGRAMS = [
    {
        "key": "phd",
        "url": f"{FUNAI_BASE}/scholarship/scholarship_guidelines_phd.html",
        "title": "船井情報科学振興財団 海外留学奨学金（大学院・博士号取得）",
        "target_degree": ["doctor"],
        "target_fields": ["情報科学", "情報工学", "理工系", "生命科学", "医学", "経済経営", "全分野"],
    },
    {
        "key": "bachelor",
        "url": f"{FUNAI_BASE}/scholarship/scholarship_guidelines_bachelor.html",
        "title": "船井情報科学振興財団 海外留学奨学金（学部）",
        "target_degree": ["bachelor"],
        "target_fields": ["科学技術系", "理工系", "全分野"],
    },
]
CURATED_FUNAI_COMMON = {
    "provider": "公益財団法人 船井情報科学振興財団",
    "requires_university_nomination": False,   # 財団へ直接応募
    "eligible_universities": ["全国"],
    "study_type": ["学位取得"],
    "destination_countries": ["米国", "欧州", "全世界"],
    "tags": ["返済不要", "財団へ直接応募", "併給は1つまで可"],
}
FUNAI_PERIOD_LABEL = "応募期間"
FUNAI_AMOUNT_LABEL = "支援内容"
FUNAI_DURATION_LABEL = "支援期間"
FUNAI_ELIGIBILITY_LABEL = "応募資格"

# ---- 吉田育英会 日本人派遣留学プログラム ----------------------------------

YOSHIDA_GUIDELINE_URL = "https://www.ysf.or.jp/scholarship/visitor/universal/os_guideline.html"
# 「20XX度採用分の募集を行います」= 募集中 / 「募集は終了」= 終了
YOSHIDA_OPEN_RE = r"(\d{4})\s*年?度?\s*採用分の募集"
YOSHIDA_CLOSED_RE = r"募集は終了|募集を終了|次年度の募集"
CURATED_YOSHIDA = {
    "provider": "公益財団法人 吉田育英会",
    "amount_text": "生活滞在費 月額 2,500 米ドル、学校納付金・研究費として奨学期間内に合計 250 万円以内（実費）、"
                   "往復渡航交通費。奨学期間は支給開始から2年以内（博士は1年延長可）。詳細は募集要項PDFを参照。",
    "amount_monthly_jpy": None,   # 米ドル建てのため換算しない
    "target_degree": ["master", "doctor"],
    "target_fields": ["全分野"],
    "study_type": ["学位取得", "研究"],
    "requires_university_nomination": None,   # 推薦依頼校在籍者は大学経由、それ以外は公募
    "eligible_universities": ["全国"],
    "tags": ["返済不要", "公募＋推薦依頼校併用", "35歳未満", "米ドル建て支給"],
    "duration_text": "2年以内（博士は最長3年）",
    "description": "海外の大学院等で学位取得または研究を行う日本人を対象とする給付型奨学金。"
                   "推薦依頼校に在籍する場合は大学を通じて応募、それ以外は公募。"
                   "生活費は米ドル建てで支給。詳細な応募資格・締切は募集要項PDFに記載。",
}

# ---- 孫正義育英財団 ------------------------------------------------------

MASASON_TOP_URL = "https://masason-foundation.org/"
MASASON_REQUIREMENTS_URL = "https://masason-foundation.org/requirements/"
MASASON_CLOSED_RE = r"今期の募集は終了|募集は終了しました|募集を終了しました"
MASASON_TERM_NEWS_RE = r"第\s*(\d+)\s*期(?:生|支援人材)?の募集開始"
CURATED_MASASON = {
    "provider": "公益財団法人 孫正義育英財団",
    "amount_text": "専用施設の無償利用、講演会・イベント参加、活動資金支援など（返済不要）。"
                   "海外大学進学・留学時の経済的支援も対象。詳細は募集要項を参照。",
    "amount_monthly_jpy": None,
    "target_degree": ["bachelor", "master", "doctor", "research"],
    "target_fields": ["全分野"],
    "study_type": ["学位取得", "研究"],
    "requires_university_nomination": False,
    "eligible_universities": ["全国"],
    "tags": ["返済不要", "26歳未満対象", "留学専用ではない", "国際大会入賞等が条件", "例年1〜2月募集"],
    "duration_text": "支援期間の定めなし（財団生資格）",
    "description": "分野を問わず突出した才能を持つ26歳未満の若者を支援する英才育成プログラム。"
                   "専用施設の提供、イベント参加、活動資金支援に加え、海外大学進学・留学時の"
                   "経済的支援も受けられる。国際大会・全国大会での実績等が応募資格。",
}

# ---- 大阪大学 留学助成制度（学内アグリゲートページ） ----------------------

OSAKA_SCHOLARSHIP_URL = "https://www.osaka-u.ac.jp/ja/international/outbound/scholarship"
# このページで直接スクレイプ済みの制度と重複するものは除外する
OSAKA_EXCLUDE_TITLE_RE = r"JASSO|日本学生支援機構|トビタテ"
# KOAN 掲示日がこの日数より古い行は「過年度の募集」として除外
OSAKA_MAX_AGE_DAYS = 450
# 学内ログインが必要なリンクは公開の一覧ページ URL にフォールバック
OSAKA_INTERNAL_HOST_RE = r"my\.osaka-u\.ac\.jp|koan|mahoroba"
