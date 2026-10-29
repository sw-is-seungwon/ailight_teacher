
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import hmac
import re
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from wordcloud import WordCloud
import matplotlib.pyplot as plt

# ==========================================
# 1. 기본 설정
# ==========================================

st.set_page_config(
    page_title="AI 신호등 평가 - 교사용",
    page_icon="📊",
    layout="wide"
)

GROUPS = [1, 2, 3, 4]
ANSWERS = ["가능", "제한", "금지"]

COLORS = {
    "가능": "#B9EDC9",
    "제한": "#FFE49C",
    "금지": "#FFC2CE"
}

EMOJI = {
    "가능": "🟢",
    "제한": "🟡",
    "금지": "🔴"
}

# ==========================================
# 2. 디자인
# ==========================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Gowun+Dodum&display=swap');

html, body, button, input, p, textarea,
[data-testid="stAppViewContainer"],
[data-testid="stMarkdownContainer"] {
    font-family: 'Gowun Dodum', sans-serif !important;
}

.stApp {
    background: linear-gradient(
        180deg, #fff8fc, #f6faff
    );
}

.block-container {
    max-width: 1100px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

.main-title {
    font-size: 2.3rem;
    font-weight: bold;
    text-align: center;
    color: #65536d;
    margin: 15px 0;
}

.subtitle {
    text-align: center;
    color: #897a92;
    margin-bottom: 25px;
}

.section-title {
    font-size: 1.5rem;
    font-weight: bold;
    color: #685772;
    margin: 20px 0;
}

div.stButton > button,
div.stFormSubmitButton > button {
    font-family: 'Gowun Dodum', sans-serif !important;
    width: 100%;
    min-height: 50px;
    border-radius: 15px;
    background: #e9dcff;
    color: #5c4e7e;
    border: 2px solid #dac6f3;
    font-weight: bold;
}

.st-key-refresh_button button {
    background: #d5edff !important;
    color: #4c6b92 !important;
    border: 2px solid #b9dafa !important;
    min-height: 60px !important;
    font-size: 18px !important;
}

.stat {
    border-radius: 18px;
    padding: 20px;
    text-align: center;
    font-size: 1.1rem;
    line-height: 2;
}

.stat-num {
    font-size: 2rem;
    font-weight: bold;
}

.green {
    background: #e1f8e9;
    color: #31754b;
}

.yellow {
    background: #fff6d5;
    color: #88661d;
}

.red {
    background: #ffe4e9;
    color: #9b485b;
}

.note {
    text-align: center;
    color: #95899a;
    font-size: 14px;
    margin: 15px;
}

.wordcloud-area {
    background: #ffffff;
    border: 2px solid #eedced;
    border-radius: 20px;
    padding: 12px;
    margin: 15px 0;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 세션 상태
# ==========================================

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "results_data" not in st.session_state:
    st.session_state.results_data = None

if "last_updated" not in st.session_state:
    st.session_state.last_updated = None

if "load_error" not in st.session_state:
    st.session_state.load_error = ""

# ==========================================
# 4. Google Sheets 조회
# ==========================================

def load_results():

    payload = {
        "action": "read",
        "password": st.secrets["teacher_password"]
    }

    response = requests.post(
        st.secrets["apps_script_url"],
        json=payload,
        timeout=(4, 15),
        allow_redirects=True
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(
            data.get("message", "조회 실패")
        )

    columns = [
        "제출시간",
        "참여ID",
        "평가조",
        "평가",
        "이유"
    ]

    df = pd.DataFrame(
        data.get("results", []),
        columns=columns
    )

    if df.empty:
        return df

    df["평가조"] = pd.to_numeric(
        df["평가조"],
        errors="coerce"
    )

    df["평가"] = (
        df["평가"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df["이유"] = (
        df["이유"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df = df[
        df["평가조"].isin(GROUPS)
        & df["평가"].isin(ANSWERS)
    ].copy()

    df = df.drop_duplicates(
        subset=["참여ID", "평가조"],
        keep="last"
    )

    return df


def refresh_results():

    try:
        df = load_results()

        st.session_state.results_data = df

        st.session_state.last_updated = (
            datetime.now(
                ZoneInfo("Asia/Seoul")
            ).strftime("%H:%M:%S")
        )

        st.session_state.load_error = ""

    except Exception as e:

        st.session_state.load_error = (
            "평가 결과를 불러오지 못했습니다. "
            f"오류: {e}"
        )

# ==========================================
# 5. 워드클라우드 함수
# ==========================================

# 한글 분석에 적합하지 않은 일반 표현 제거
STOPWORDS = {
    "그리고", "그러나", "하지만",
    "그래서", "때문에", "따라서",
    "있어요", "있습니다", "없어요",
    "없습니다", "있다", "없다",
    "같아요", "같습니다", "생각합니다",
    "생각해요", "것이다", "것을",
    "것은", "것이", "저는", "제가",
    "너무", "정말", "매우",
    "조금", "많이", "위해",
    "대한", "이러한", "그러한",
    "서비스", "인공지능",
    "사용할", "사용하는", "사용하고",
    "있을", "없는", "하는",
    "있기", "때문", "한다",
    "된다", "해야", "같은",
    "그리고", "이것", "저것"
}

# 자주 등장하는 표현 통합
WORD_REPLACE = {
    "개인정보가": "개인정보",
    "개인정보를": "개인정보",
    "개인정보의": "개인정보",
    "안전성이": "안전성",
    "안전성을": "안전성",
    "정확성이": "정확성",
    "정확성을": "정확성",
    "공정성이": "공정성",
    "공정성을": "공정성",
    "신뢰성이": "신뢰성",
    "신뢰성을": "신뢰성",
    "편리해서": "편리함",
    "편리하고": "편리함",
    "편리하다": "편리함",
    "위험해서": "위험",
    "위험하다": "위험",
    "보완해야": "보완",
    "보완하면": "보완",
    "오류가": "오류",
    "오류를": "오류"
}


def extract_words(texts):
    """학생 평가 이유에서 단어 추출"""

    words = []

    for text in texts:

        text = str(text).strip()

        # 한글, 영어, 숫자 중 두 글자 이상의 단어
        tokens = re.findall(
            r"[가-힣A-Za-z0-9]{2,}",
            text
        )

        for token in tokens:

            token = token.lower()

            # 표현 통합
            token = WORD_REPLACE.get(
                token, token
            )

            if token in STOPWORDS:
                continue

            words.append(token)

    return Counter(words)


def find_korean_font():
    """Streamlit 서버에서 한글 폰트 찾기"""

    candidates = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansKR-Regular.ttf",
        "C:/Windows/Fonts/malgun.ttf"
    ]

    for path in candidates:
        if Path(path).is_file():
            return path

    # 설치 위치가 다른 경우 검색
    font_root = Path("/usr/share/fonts")

    if font_root.exists():
        for pattern in [
            "**/NanumGothic.ttf",
            "**/NanumBarunGothic.ttf",
            "**/NotoSansCJK-Regular.ttc"
        ]:
            matches = list(
                font_root.glob(pattern)
            )

            if matches:
                return str(matches[0])

    return None


def make_wordcloud(frequencies):

    font_path = find_korean_font()

    if font_path is None:
        st.warning(
            "한글 폰트가 설치되어 있지 않습니다. "
            "GitHub에 packages.txt 파일을 추가하고 "
            "fonts-nanum을 입력해 주세요."
        )
        return

    try:
        wc = WordCloud(
            font_path=font_path,
            width=1100,
            height=550,
            background_color="#fffaff",
            max_words=50,
            colormap="Set2",
            prefer_horizontal=0.95,
            random_state=42,
            collocations=False,
            margin=8
        )

        wc.generate_from_frequencies(
            frequencies
        )

        fig, ax = plt.subplots(
            figsize=(12, 6)
        )

        ax.imshow(
            wc,
            interpolation="bilinear"
        )

        ax.axis("off")

        fig.patch.set_facecolor("#fffaff")

        st.pyplot(
            fig,
            use_container_width=True
        )

        plt.close(fig)

    except Exception as e:
        st.error(
            "워드클라우드 생성 중 오류가 발생했습니다."
        )
        st.caption(str(e))


# ==========================================
# 6. 로그인
# ==========================================

def login(password):

    return hmac.compare_digest(
        password,
        st.secrets["teacher_password"]
    )


def logout():

    st.session_state.authenticated = False
    st.session_state.results_data = None
    st.session_state.last_updated = None
    st.session_state.load_error = ""


if not st.session_state.authenticated:

    st.markdown(
        '<div class="main-title">'
        '🔒 교사용 신호등 평가'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        '비밀번호를 입력해 주세요.'
        '</div>',
        unsafe_allow_html=True
    )

    left, center, right = st.columns([1, 2, 1])

    with center:

        with st.form("login_form"):

            password = st.text_input(
                "교사용 비밀번호",
                type="password"
            )

            submitted = st.form_submit_button(
                "로그인",
                use_container_width=True
            )

        if submitted:

            if login(password):

                st.session_state.authenticated = True

                with st.spinner(
                    "🌷 평가 결과를 불러오고 있어요..."
                ):
                    refresh_results()

                st.rerun()

            else:
                st.error(
                    "비밀번호가 올바르지 않습니다."
                )

    st.stop()

# ==========================================
# 7. 메인 화면
# ==========================================

st.markdown(
    '<div class="main-title">'
    '📊 AI 신호등 평가 결과'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    '학생들의 신호등 평가 결과를 확인해 보세요. 🌷'
    '</div>',
    unsafe_allow_html=True
)

left, right = st.columns([5, 1])

with left:

    selected_group = st.radio(
        "결과를 확인할 조",
        GROUPS,
        format_func=lambda x: f"{x}조",
        horizontal=True,
        key="selected_group"
    )

with right:

    st.write("")

    if st.button(
        "로그아웃",
        use_container_width=True
    ):
        logout()
        st.rerun()

st.write("")

# ==========================================
# 8. 수동 새로고침
# ==========================================

if st.button(
    "🔄 평가 결과 새로고침",
    key="refresh_button",
    use_container_width=True
):

    with st.spinner(
        "🌷 최신 평가 결과를 불러오고 있어요..."
    ):
        refresh_results()

if st.session_state.load_error:
    st.error(st.session_state.load_error)

if st.session_state.last_updated:
    st.caption(
        "마지막 데이터 조회 : "
        f"{st.session_state.last_updated}"
    )

st.divider()

# ==========================================
# 9. 평가 결과 집계
# ==========================================

if st.session_state.results_data is None:

    st.info(
        "데이터가 없습니다. 새로고침 버튼을 눌러 주세요."
    )

    st.stop()

df = st.session_state.results_data

group_df = df[
    df["평가조"] == selected_group
].copy()

total = len(group_df)

counts = {
    answer: int(
        (group_df["평가"] == answer).sum()
    )
    for answer in ANSWERS
}

st.markdown(
    f'<div class="section-title">'
    f'🌼 {selected_group}조 평가 현황'
    f'</div>',
    unsafe_allow_html=True
)

st.metric(
    "현재 평가 참여 인원",
    f"{total}명"
)

# ==========================================
# 10. 가능 / 제한 / 금지
# ==========================================

cols = st.columns(3)

css_names = [
    "green",
    "yellow",
    "red"
]

for col, answer, css_name in zip(
    cols, ANSWERS, css_names
):

    number = counts[answer]

    percent = (
        number / total * 100
        if total else 0
    )

    with col:

        st.markdown(
            f"""
            <div class="stat {css_name}">
                {EMOJI[answer]} {answer}
                <div class="stat-num">
                    {number}명
                </div>
                {percent:.1f}%
            </div>
            """,
            unsafe_allow_html=True
        )

st.write("")

# ==========================================
# 11. 원그래프
# ==========================================

if total == 0:

    st.info(
        "아직 이 조에 대한 평가 결과가 없습니다."
    )

else:

    labels = [
        a for a in ANSWERS
        if counts[a] > 0
    ]

    values = [
        counts[a] for a in labels
    ]

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            sort=False,
            marker=dict(
                colors=[
                    COLORS[a] for a in labels
                ],
                line=dict(
                    color="white",
                    width=3
                )
            ),
            textinfo="label+percent",
            textfont=dict(size=17),
            hovertemplate=(
                "%{label}: %{value}명"
                "<extra></extra>"
            )
        )
    )

    fig.update_layout(
        title=dict(
            text=f"{selected_group}조 신호등 평가 비율",
            x=0.5
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=420,
        margin=dict(
            l=20,
            r=20,
            t=60,
            b=20
        ),
        annotations=[
            dict(
                text=f"{total}명",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(
                    size=24,
                    color="#65536d"
                )
            )
        ]
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False}
    )

st.divider()

# ==========================================
# 12. 평가 이유 필터
# ==========================================

st.markdown(
    "### 💬 학생들이 작성한 평가 이유"
)

answer_filter = st.selectbox(
    "평가 유형",
    ["전체", "가능", "제한", "금지"],
    key="answer_filter"
)

if answer_filter == "전체":

    reason_df = group_df.copy()

else:

    reason_df = group_df[
        group_df["평가"] == answer_filter
    ].copy()

# 실제 문장이 있는 응답만 추출
valid_reasons = reason_df[
    reason_df["이유"].fillna("").astype(str).str.strip() != ""
].copy()

st.caption(
    f"평가 응답 {len(reason_df)}개 · "
    f"이유가 있는 응답 {len(valid_reasons)}개"
)

# ==========================================
# 13. 워드클라우드
# ==========================================

st.markdown("### ☁️ 평가 이유 워드클라우드")

if valid_reasons.empty:

    st.info(
        "선택한 조와 평가 유형에 작성된 "
        "평가 이유가 없습니다."
    )

else:

    texts = valid_reasons["이유"].tolist()

    # 단어 추출
    frequencies = extract_words(texts)

    # 단어 수 확인
    st.caption(
        f"분석된 단어 종류 : {len(frequencies)}개"
    )

    if not frequencies:

        st.warning(
            "평가 이유는 있지만 추출된 단어가 없습니다. "
            "두 글자 이상의 단어가 있는지 확인해 주세요."
        )

    else:

        make_wordcloud(frequencies)

        # 자주 등장한 단어 표시
        st.markdown("**🔎 자주 등장한 단어 TOP 10**")

        top_words = frequencies.most_common(10)

        st.write(
            " · ".join(
                f"{word} ({count}회)"
                for word, count in top_words
            )
        )

st.divider()

# ==========================================
# 14. 학생 평가 이유 목록
# ==========================================

st.markdown(
    "### 📝 학생들의 평가 이유 자세히 보기"
)

if reason_df.empty:

    st.info(
        "표시할 평가 이유가 없습니다."
    )

else:

    for _, row in reason_df.iterrows():

        answer = str(row["평가"])
        reason = str(row["이유"]).strip()
        submitted = str(row["제출시간"])

        with st.container(border=True):

            st.markdown(
                f"**{EMOJI[answer]} {answer}**"
            )

            if reason:
                st.write(reason)

            else:
                st.warning(
                    "평가 이유가 비어 있습니다."
                )

            st.caption(
                f"🕒 제출 시간 : {submitted}"
            )

st.markdown(
    '<div class="note">'
    '🌷 새로고침 버튼을 누르면 최신 결과가 반영됩니다.'
    '</div>',
    unsafe_allow_html=True
)
