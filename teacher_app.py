import re
from collections import Counter
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import hmac
from datetime import datetime
from zoneinfo import ZoneInfo

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
# 2. 파스텔톤 디자인
# ==========================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Gowun+Dodum&display=swap');

html, body, button, input, p,
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

/* 버튼 */
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

/* 새로고침 버튼 */
.st-key-refresh_button button {
    background: #d5edff !important;
    color: #4c6b92 !important;
    border: 2px solid #b9dafa !important;
    min-height: 60px !important;
    font-size: 18px !important;
}

/* 평가 통계 카드 */
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

/* 평가 이유 카드 */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px;
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
# 4. Google Sheets 결과 조회
# ==========================================

def load_results():
    """Apps Script로 평가 결과 조회"""

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

    # 데이터 형식 확인
    df["평가조"] = pd.to_numeric(
        df["평가조"],
        errors="coerce"
    )

    # 정상 평가만 추출
    df = df[
        df["평가조"].isin(GROUPS)
        & df["평가"].isin(ANSWERS)
    ].copy()

    # 중복 응답 방지
    df = df.drop_duplicates(
        subset=["참여ID", "평가조"],
        keep="last"
    )

    return df


def refresh_results():
    """Google Sheets 데이터를 수동으로 다시 조회"""

    try:
        df = load_results()

        st.session_state.results_data = df

        st.session_state.last_updated = (
            datetime.now(
                ZoneInfo("Asia/Seoul")
            ).strftime("%H:%M:%S")
        )

        st.session_state.load_error = ""

    except Exception:
        # 오류가 나면 기존 결과 유지
        st.session_state.load_error = (
            "평가 결과를 불러오지 못했습니다. "
            "잠시 후 다시 시도해 주세요."
        )

# ==========================================
# 5. 교사용 로그인
# ==========================================

def login(password):
    correct = st.secrets["teacher_password"]

    return hmac.compare_digest(
        password,
        correct
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

    left, center, right = st.columns(
        [1, 2, 1]
    )

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

                # 최초 로그인할 때 한 번 조회
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
# 6. 교사용 메인 화면
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
# 7. 수동 새로고침
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
# 8. 평가 결과 대시보드
# ==========================================

if st.session_state.results_data is None:

    st.info(
        "평가 결과를 불러오지 못했어요. "
        "위의 새로고침 버튼을 눌러 주세요."
    )

    st.stop()

# 저장된 데이터를 사용
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

# ------------------------------------------
# 1. 조별 평가 현황
# ------------------------------------------

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

# ------------------------------------------
# 2. 가능 / 제한 / 금지 집계
# ------------------------------------------

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
        if total > 0 else 0
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

# ------------------------------------------
# 3. 신호등 평가 원그래프
# ------------------------------------------

if total == 0:

    st.info(
        "아직 이 조에 대한 평가 결과가 없습니다."
    )

else:

    labels = [
        answer for answer in ANSWERS
        if counts[answer] > 0
    ]

    values = [
        counts[answer] for answer in labels
    ]

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            sort=False,

            marker=dict(
                colors=[
                    COLORS[answer]
                    for answer in labels
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
        config={
            "displayModeBar": False
        }
    )

st.divider()

# ==========================================
# 9. 학생 평가 이유
# ==========================================

st.markdown(
    "### 💬 학생들이 작성한 평가 이유"
)

# 평가 유형 필터
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

st.caption(
    f"총 {len(reason_df)}개의 평가 이유"
)

# ==========================================
# 평가 이유 워드클라우드
# ==========================================

st.subheader("☁️ 평가 이유 워드클라우드")

# 분석에서 제외할 단어
STOPWORDS = {
    "그리고", "그러나", "하지만", "때문에",
    "있어요", "있다", "없다", "같아요",
    "생각합니다", "생각해요", "것", "수",
    "이", "그", "저", "것은", "것이",
    "서비스", "인공지능", "사용",
    "있을", "없는", "대한", "위해"
}

# 선택한 조와 평가 유형의 이유 수집
texts = reason_df["이유"].fillna("").astype(str)

words = []

for text in texts:
    # 한글과 영문 단어 추출
    tokens = re.findall(r"[가-힣A-Za-z]{2,}", text)

    for token in tokens:
        if token not in STOPWORDS:
            words.append(token)

# 단어 빈도 계산
frequencies = Counter(words)

if not frequencies:
    st.info("워드클라우드를 만들 평가 이유가 없습니다.")

else:
    try:
        wc = WordCloud(
            font_path="/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            width=1000,
            height=500,
            background_color="white",
            colormap="Pastel1",
            max_words=40,
            prefer_horizontal=0.9,
            random_state=42
        )

        wc.generate_from_frequencies(frequencies)

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")

        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    except OSError:
        st.error("한글 폰트를 찾지 못했습니다.")

# 많이 등장한 단어 표시
if frequencies:
    st.caption("자주 등장한 단어 TOP 5")

    top_words = frequencies.most_common(5)

    st.write(
        " · ".join(
            f"{word} ({count}회)"
            for word, count in top_words
        )
    )

# ------------------------------------------
# 평가 이유 출력
# ------------------------------------------

if reason_df.empty:

    st.info(
        "아직 작성된 평가 이유가 없습니다."
    )

else:

    for _, row in reason_df.iterrows():

        answer = str(row["평가"])
        reason = str(row["이유"]).strip()
        submitted = str(row["제출시간"])

        # HTML 태그가 그대로 보이지 않도록
        # Streamlit 기본 컨테이너 사용
        with st.container(border=True):

            st.markdown(
                f"**{EMOJI[answer]} {answer}**"
            )

            if reason and reason.lower() != "nan":
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
    '🌷 새로고침 버튼을 누르면 '
    '최신 평가 결과가 반영됩니다.'
    '</div>',
    unsafe_allow_html=True
)
