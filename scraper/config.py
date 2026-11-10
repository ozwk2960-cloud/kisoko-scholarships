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
    "(+https://github.com/ozwk2960-cloud/kisoko-scholarships; scholarship search tool for Osaka Univ. students)"
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
    # 金額は第19期（2027年度）募集要項PDF（2026年10月）の支給金額表による
    "amount_text": "返済不要。奨学金は月額 60,000〜160,000円（留学先の地域と家計基準による）"
                   "＋ 留学準備金（アジア15万円／その他25万円。物価高騰対応でアジア+6万円・その他+10万円）"
                   "＋ 授業料の支援（全地域 30万円）。詳細は募集要項を参照。",
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

# 期ごとの日程（募集要項PDFから）。キーは「第N期」の N。期が違えば当たらないので、
# 次の期の募集に古い日程が残ることはない。学生本人の締切は「在籍大学等が指定する期間」で
# 機構の期限より早い。ここでは機構側の期限を「大学が機構に出す期限」として説明に使うだけで、deadline には入れない。
# 出典: https://tobitate-mext.jasso.go.jp/newprogram/assets/pdf/2027_19th_univ_applicant_guidelines.pdf
TOBITATE_SCHEDULES = {
    "19": {
        "text": "第19期（2027年度）の募集要項が公開済み。学生本人の応募期間は在籍大学等が指定するため、"
                "学内締切は所属大学の担当窓口で確認すること。参考: 大学から機構への応募申請は"
                "2026年12月上旬開始・2027年2月25日17時が期限（学内締切はこれより前）。"
                "書面審査結果は4月下旬、面接は5月15・16日（東京）、採否は6月中旬の予定。",
        "note": "留学開始は2027年8月1日〜2028年3月31日。大学院生も新大学1年生以外のスケジュールで応募。",
    },
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

# 阪大の一覧ページに【対象】が載っていない「個人で直接応募」の制度は、各財団・機関の公式ページで
# 確認できた事実だけをここに手で記録する（財団名キーなので年度が変わっても効く）。
# 方針: 公式に明記されていることだけを書く。不明な項目はキーごと省略 → ツール上は「要確認」になる。
#   target_fields の「全分野」は、公式の応募資格に専攻の条件が一切書かれていない（または不問と明記）場合のみ。
#   match      : 一覧上のタイトルに当てる正規表現
#   target_degree / study_type / target_fields / destination_countries : 上書きする値
#   note       : カードの説明文に添える「公式情報」の要約
OSAKA_CURATED = [
    # 出典: https://www.inpex.co.jp/ (INPEX教育交流財団 募集要項。修士・博士課程の大学院生が対象)
    {"match": r"INPEX", "target_degree": ["master", "doctor"], "target_fields": ["全分野"],
     "destination_countries": ["インドネシア", "オーストラリア", "UAE"],
     "note": "公式情報: 大学院（修士・博士）が対象。学部生は対象外。留学先はインドネシア・オーストラリア・UAE。"},
    # 出典: 皇太子明仁親王奨学金（日米学生交流）公式案内。留学先は米国（ハワイ含む）
    {"match": r"皇太子明仁親王", "target_degree": ["master", "doctor"],
     "destination_countries": ["アメリカ", "ハワイ"],
     "note": "公式情報: 大学院生が対象。留学先は米国（ハワイ）。"},
    # 出典: 日中友好協会「中国政府奨学金留学生」募集案内
    {"match": r"中国政府奨学金", "target_degree": ["bachelor", "master", "doctor"],
     "destination_countries": ["中国"]},
    # 出典: 在日フランス大使館 フランス政府奨学金 募集案内（修士・博士レベル）
    {"match": r"フランス政府", "target_degree": ["master", "doctor"],
     "destination_countries": ["フランス"], "study_type": ["学位取得", "研究"]},
    # 出典: 豊田理化学研究所 海外大学院進学支援制度の案内（理工系）
    {"match": r"豊田理化学", "target_degree": ["bachelor", "master"], "study_type": ["学位取得"],
     "target_fields": ["理工系"], "destination_countries": ["全世界"]},
    # 出典: 本庄国際奨学財団 募集要項（海外大学院の学位取得）
    {"match": r"本庄", "target_degree": ["master", "doctor"], "study_type": ["学位取得"],
     "target_fields": ["全分野"], "destination_countries": ["全世界"]},
    # 出典: 重田教育財団 海外留学奨学金 募集要項
    {"match": r"重田教育財団", "study_type": ["学位取得"], "target_fields": ["全分野"],
     "destination_countries": ["全世界"]},
    # 出典: 食生活研究会 海外留学奨学生 募集要項
    {"match": r"食生活研究会", "study_type": ["学位取得"], "target_fields": ["全分野"]},
    # 出典: 日米教育委員会（フルブライト・ジャパン）日本人対象プログラム案内
    {"match": r"フルブライト", "study_type": ["学位取得", "研究"], "target_fields": ["全分野"],
     "destination_countries": ["アメリカ"]},
    # 出典: スイス政府奨学金（ESKAS）案内。博士・研究者向け
    {"match": r"スイス政府", "target_degree": ["doctor", "research"], "study_type": ["研究"],
     "destination_countries": ["スイス"]},
    # 出典: 伊藤国際教育交流財団 募集要項（学位取得が対象。交換留学・短期・博士後期は対象外）
    {"match": r"伊藤国際", "target_degree": ["master"], "study_type": ["学位取得"], "target_fields": ["全分野"],
     "destination_countries": ["全世界"],
     "note": "公式情報: 修士課程での学位取得を目的とする留学が対象（専攻不問）。交換留学・短期留学は対象外。"},
    # 出典: 霞山会 中国・台湾留学奨学金 案内
    {"match": r"霞山会", "target_degree": ["bachelor", "master", "doctor"], "study_type": ["研究"],
     "destination_countries": ["中国", "台湾"]},
    # 出典: 松下幸之助国際スカラシップ 募集要項（人文社会科学系の研究、アジア・アフリカ・中南米）
    {"match": r"松下幸之助", "target_degree": ["bachelor", "master", "doctor"], "study_type": ["研究"],
     "target_fields": ["人文社会科学"],
     "destination_countries": ["アジア", "アフリカ", "ラテンアメリカ"]},
    # 出典: 中島記念国際交流財団 募集要項
    {"match": r"中島記念", "study_type": ["学位取得"],
     "target_fields": ["情報科学", "生命科学", "経営科学"]},
    # 出典: 日中友好協会 2026年度アポロトレイディング奨学金 募集要項（第2版）PDF
    #   https://www.j-cfa.com/project/apolloshogaku/ から取得（専攻の列挙は基礎工の専攻名と
    #   対応しないため target_fields は入れず、note で伝える）
    {"match": r"アポロ", "target_degree": ["bachelor", "master", "doctor"],
     "study_type": ["学位取得", "交換留学"], "destination_countries": ["中国"],
     "note": "公式情報: 中国の4年制大学・研究機関に9か月以上留学する学部生・大学院生（交換留学可）。"
             "HSK4級／中検3級以上・30歳以下。専攻は政治・経済・歴史・文化・科学。"},
    # 出典: 福井県国際交流協会 フィンドレー大学・福井県奨学生 募集要項（令和8年度版）
    #   https://www.f-i-a.or.jp/ja/fia/findlay/ の一式zip内 PDF
    {"match": r"フィンドレー", "target_degree": ["bachelor", "master", "doctor"],
     "study_type": ["学位取得", "語学"], "destination_countries": ["アメリカ"],
     "note": "公式情報: 応募資格は原則として福井県内在住または県内の高校卒業者。"
             "フィンドレー大学（米国）の学部・大学院・集中英語コースの1年分の授業料を免除。"},
    # 出典: 経団連国際教育交流財団 2027年度奨学生募集要項 PDF
    #   https://idc.disc.co.jp/keidanren/scholarship/scholarshipyoukou.pdf
    {"match": r"経団連グローバル人材育成", "target_degree": ["bachelor", "master"], "target_fields": ["全分野"],
     "study_type": ["交換留学"], "destination_countries": ["全世界"],
     "note": "公式情報: 学部2〜4年生または博士前期課程1〜2年生。8か月以上1年未満の留学（理工系は研究室での"
             "研究・講義受講で6か月以上も可）。支給200万円。TOEFL iBT61／IELTS5.0相当と学部長等の推薦状が必要。"},
    # 出典: 大蔵共助会 海外留学生支援 http://www.jhayashida.co.jp/okurakyojokai/sa.html
    #   学年の明記は無いが、過去の支援実績に阪大の学部生・大学院生の両方が載っている
    {"match": r"大蔵共助会", "target_degree": ["bachelor", "master", "doctor"], "target_fields": ["全分野"],
     "destination_countries": ["全世界"],
     "note": "公式情報: 海外の大学・大学院（語学研修校を除く）へ半年以上留学する日本国籍の方。"
             "大阪府内在住の学生、または府内の学校法人・留学支援団体所属の学生が対象。"},
    # 出典: SEKAIA IBPグローバル留学奨学金 https://www.sekaia.co.jp/ibp/student/scholarship/
    {"match": r"SEKAIA", "study_type": ["インターン"],
     "destination_countries": ["アメリカ", "イギリス", "オーストラリア", "マレーシア"],
     "note": "公式情報: IBPビジネス留学プログラム（約12か月・現地大学＋インターン）の参加費を免除する奨学金。"
             "応募資格は18歳以上の学生。公式ページに『募集は終了』の表示あり。"},
    # 出典: 寺浦さよ子記念奨学会 募集要項 http://www.sayoko-shougakukai.or.jp/guidelines-for-applicants/
    {"match": r"寺浦", "target_degree": ["bachelor", "master", "doctor"], "target_fields": ["全分野"],
     "destination_countries": ["全世界"],
     "note": "公式情報: 海外の大学・大学院等へ留学する学生のうち、経済的に学資の支弁が困難な優秀な者。"
             "大学・大学院生は月額10万円＋支度一時金。"},
    # 出典: フクシマグローバル人材支援奨学財団 2026年度募集要項 https://www.fukushima-global.or.jp/overseas.html
    #   短期は「本学主催の海外研修プログラム」への参加が条件（阪大ページの【対象】）。交換留学は含まない。
    #   種別「語学」は利用者（阪大関係者）の指摘による分類。
    {"match": r"フクシマ.*短期", "target_degree": ["bachelor"], "target_fields": ["全分野"], "study_type": ["語学"], "destination_countries": ["全世界"],
     "note": "公式情報: 25歳以下の学部生が2週間以上6か月未満の留学をする場合。30万円以上の留学プログラムが対象。"},
    # 出典: 業務スーパージャパンドリーム財団 2026年度留学支援事業 募集要項（大学事務担当者用）PDF
    #   https://www.kobebussan.or.jp/pdf/guideline_202601_02.pdf （第1回・第2回共通）
    {"match": r"業務スーパージャパンドリーム", "target_degree": ["bachelor"], "study_type": ["交換留学"],
     "target_fields": ["全分野"], "destination_countries": ["全世界"],
     "note": "公式情報: 学部2年生以上（大学院は不可）・35歳以下。語学研修を含まない6か月以上の大学間協定留学が対象。"
             "学内選考あり。専攻の制限は無い（文系・文理融合型学部のみ単位認定等の追加条件）。"},
    # 出典: 阪和育英会 海外留学奨学生の資格 https://hanwa-ikueikai.or.jp/recruiting2/index.html
    {"match": r"阪和育英会", "target_degree": ["bachelor"], "target_fields": ["全分野"],
     "destination_countries": ["全世界"],
     "note": "公式情報: 指定大学の学部生。家計の年収合計1,000万円以内、学校長（学部長）の推薦が必要。語学研修目的は不可。"},
    # 出典: みずほ国際交流奨学財団 日本人奨学生募集要項（2027年度） https://mizuhokokusai.la.coocan.jp/information.html
    {"match": r"みずほ国際交流", "target_degree": ["bachelor"], "study_type": ["交換留学"],
     "target_fields": ["全分野"], "destination_countries": ["全世界"],
     "note": "公式情報: 学部生で、大学の選考により協定大学への交換留学が決定している人。最長1年（半年は不可）。"
             "大学が財団から推薦依頼を受けている場合のみ応募可。"},
    # 出典: 大遊協国際交流・援助・研究協会 日本人留学生向け応募要領 https://www.daiyukyo-kokusaikoryu.or.jp/scholarship.html
    {"match": r"大遊協", "target_degree": ["bachelor"], "study_type": ["交換留学"],
     "target_fields": ["全分野"], "destination_countries": ["全世界"],
     "note": "公式情報: 大阪に居住し大阪の大学に通う学部生が、8か月〜1年の交換留学をする場合。"
             "経済的理由で自費のみの留学が困難な人が対象。"},
    {"match": r"フクシマ.*長期", "target_degree": ["bachelor"], "target_fields": ["全分野"], "destination_countries": ["全世界"],
     "note": "公式情報: 25歳以下の学部生が6か月以上12か月未満の留学をする場合。"},
    # 出典: 吉田育英会 日本人派遣留学プログラム（既存の CURATED_YOSHIDA と同じ内容）
    {"match": r"吉田育英会", "target_degree": ["master", "doctor"], "study_type": ["学位取得", "研究"],
     "target_fields": ["全分野"]},
]

# 募集回（年度）ごとの締切・募集状況。OSAKA_CURATED（制度の性質）と違い、毎回の募集に固有の事実なので
# 年度入りのタイトル、または阪大掲示日（posted）で特定の回にだけ当てる。次の年度の行には当たらない
# ＝古い締切が新しい募集に残ることはない。公式ページで確認できたものだけ記録する。
#   match / posted : タイトルの正規表現 / 阪大ページの掲示日（ISO）。両方指定なら両方満たすこと
#   deadline       : 公式に明記された応募締切（ISO）。過ぎたら「募集終了」として扱う
#   application_status : 日付が無く「募集終了」とだけ書かれている場合
#   note           : カードの説明に添える公式情報
OSAKA_ROUNDS = [
    # 出典: 経団連 皇太子明仁親王奨学金 http://www.keidanren.or.jp/japanese/profile/prince.html
    {"match": r"皇太子明仁親王.*令和9年度", "deadline": "2026-11-30",
     "note": "公式情報: 応募受付 2026/10/1〜11/30 必着。"},
    # 出典: 食生活研究会 https://www.z-ssk.org/ab_study/guideline.html （2027年度渡航留学生）
    {"match": r"食生活研究会.*2027年度", "deadline": "2026-11-13",
     "note": "公式情報: 応募書類は2026/11/13必着。"},
    # 出典: 大蔵共助会 http://www.jhayashida.co.jp/okurakyojokai/sa.html （募集期間 2026/5/1〜6/15）
    {"match": r"大蔵共助会.*2026年度", "deadline": "2026-06-15"},
    # 出典: 中島記念国際交流財団 http://nakajimafound.or.jp/koubo.html （受付 令和8年8/1〜8/20）
    {"match": r"中島記念.*令和9年度", "deadline": "2026-08-20"},
    # 出典: 経団連 募集要項PDF（応募受付 2026/8/4〜10/7）
    {"match": r"経団連グローバル人材育成.*2027年度", "deadline": "2026-10-07"},
    # 出典: 日中友好協会 https://www.j-cfa.com/studyabroad/ （出願 2025/12/8〜12/25）
    {"match": r"2026年度.*中国政府奨学金", "deadline": "2025-12-25"},
    # 出典: 本庄国際奨学財団 https://www.hisf.or.jp/scholarship/abroad （募集 2026/2/2〜4/30）
    {"match": r"本庄.*2026年度", "deadline": "2026-04-30"},
    # 出典: 重田教育財団 https://s-ef.or.jp/scholarship/ （募集 2026/5/1〜6/30 必着）
    {"match": r"重田教育財団.*2026年度", "deadline": "2026-06-30"},
    # 出典: 松下幸之助国際スカラシップ （応募受付 2026/6/1〜7/23）
    {"match": r"松下幸之助.*2026年度", "deadline": "2026-07-23"},
    # 出典: INPEX教育交流財団 https://www.inpex-s.com/ （2026/10/31『2027年度奨学金の募集を締め切りました』）
    {"match": r"INPEX.*2027年度", "deadline": "2026-10-31"},
    # 出典: 日中友好協会 https://www.j-cfa.com/project/apolloshogaku/ （出願 〜2026/5/18）
    {"match": r"2026年度.*アポロトレイディング", "deadline": "2026-05-18"},
    # 出典: 福井県国際交流協会 令和8年度募集要項（応募締切 2026/10/31）。タイトルに年度が無いので掲示日で特定
    {"match": r"フィンドレー", "posted": "2026-05-28", "deadline": "2026-10-31"},
    # 出典: SEKAIA IBP 公式ページに「募集は終了いたしました」。日付の記載は無い
    {"match": r"SEKAIA", "posted": "2025-12-18", "application_status": "closed"},
    # 出典: JASSO 外国政府等奨学金（スイス） https://ryugaku.jasso.go.jp/.../scholarship_ch.html
    #   阪大ページの行は「2026-2027年度」のままだが、公式ページが募集中なのは「2027-2028年度」の回
    {"match": r"スイス政府.*2026-2027年度", "posted": "2025-09-02", "deadline": "2026-11-30",
     "note": "公式情報: 現在募集中なのは2027-2028年度の回（申請期限 2026/11/30）。阪大ページの行は旧年度表記のまま。"},
    # --- 締切調査（2026-11-10）：各財団・大使館の公式ページで確認できたものだけ ---
    # 出典: 伊藤国際教育交流財団 募集要項（2027年度 日本人奨学金。申請書類の提出締切 2026/8/26）
    {"match": r"伊藤国際.*2027年度", "deadline": "2026-08-26"},
    # 出典: 日米教育委員会 フルブライト日本人対象（オンライン登録 2026/3/1〜5/1、書類は7/1消印有効）
    {"match": r"フルブライト.*2027年度", "deadline": "2026-05-01",
     "note": "公式情報: オンライン登録 2026/3/1〜5/1。書類提出は7/1消印有効。"},
    # 出典: 豊田理化学研究所 海外大学院進学支援制度（2025年度分の募集は2026/5/6締切）
    {"match": r"豊田理化学.*2025年度", "posted": "2026-02-12", "deadline": "2026-05-06",
     "note": "公式情報: 次回の募集は2027年2月頃の見込み。"},
    # 出典: 霞山会 公式ページ「現在は募集を行っていない」
    {"match": r"霞山会.*2026年度", "posted": "2025-10-22", "application_status": "closed",
     "note": "公式情報: 現在は募集を行っていません。"},
    # 出典: 在日フランス大使館 2027年度の募集（オンライン出願締切 2026/11/20）
    {"match": r"フランス政府.*2027年度", "posted": "2026-08-21", "deadline": "2026-11-20",
     "note": "公式情報: オンライン出願の締切は2026/11/20。"},
    # 2027年度の募集が始まったため、前回（2026-2027年度）の回は終了
    {"match": r"フランス政府.*2026-2027年度", "posted": "2025-08-22", "application_status": "closed",
     "note": "公式情報: 2027年度の募集が始まっており、この回の募集は終了しています。"},
]
