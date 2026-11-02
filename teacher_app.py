
import hmac
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from wordcloud import WordCloud

# ==========================================
# 1. 기본 설정
# ==========================================

st.set_page_config(
    page_title="AI 신호등 평가 - 교사용",
    page_icon="📊",
    layout="wide"
)

CLASSES = {
    "A": {"label": "A분반", "groups": 4},
    "B": {"label": "B분반", "groups": 5}
}

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

COLUMNS = [
    "제출시간",
    "참여ID",
    "평가조",
    "평가",
    "이유"
]

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

/* 수동 새로고침 버튼 */
.st-key-refresh_button button {
    background: #d5edff !important;
    color: #4c6b92 !important;
    border: 2px solid #b9dafa !important;
    min-height: 60px !important;
    font-size: 18px !important;
}

/* 평가 통계 */
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
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 세션 상태
# ==========================================

defaults = {
    "authenticated": False,
    "selected_class_teacher": "A",
    "selected_group": 1,
    "results_cache": {},
    "updated_cache": {},
    "load_error": ""
}

for key, default in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ==========================================
# 4. Google Sheets 결과 조회
# ==========================================

def load_results(class_id):
    """
    선택한 분반의 평가 결과만 조회
    """

    payload = {
        "action": "read",
        "class_id": class_id,
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

    df = pd.DataFrame(
        data.get("results", []),
        columns=COLUMNS
    )

    if df.empty:
        return df

    # 조 번호 숫자로 변환
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

    # 분반에 해당하는 조만 추출
    total_groups = CLASSES[class_id]["groups"]

    df = df[
        df["평가조"].isin(
            range(1, total_groups + 1)
        )
        & df["평가"].isin(ANSWERS)
    ].copy()

    # 중복 응답 제거
    df = df.drop_duplicates(
        subset=["참여ID", "평가조"],
        keep="last"
    )

    return df


def refresh_results(class_id):
    """
    선택한 분반 데이터 수동 새로고침
    """

    try:
        df = load_results(class_id)

        st.session_state.results_cache[class_id] = df

        st.session_state.updated_cache[class_id] = (
            datetime.now(
                ZoneInfo("Asia/Seoul")
            ).strftime("%H:%M:%S")
        )

        st.session_state.load_error = ""

    except Exception as error:
        st.session_state.load_error = (
            f"결과 조회 실패: {error}"
        )


def logout():
    st.session_state.authenticated = False
    st.session_state.results_cache = {}
    st.session_state.updated_cache = {}
    st.session_state.load_error = ""

# ==========================================
# 5. 워드클라우드 설정
# ==========================================

STOPWORDS = {
    "그리고", "그러나", "하지만",
    "그래서", "때문에", "따라서",
    "있어요", "있습니다",
    "없어요", "없습니다",
    "있다", "없다",
    "같아요", "같습니다",
    "생각합니다", "생각해요",
    "것이다", "것을", "것은", "것이",
    "저는", "제가",
    "너무", "정말", "매우",
    "조금", "많이",
    "위해", "대한",
    "이러한", "그러한",
    "서비스", "인공지능",
    "사용할", "사용하는", "사용하고",
    "있을", "없는", "하는",
    "있기", "때문", "한다",
    "된다", "해야", "같은",
    "이것", "저것"
}

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
    """
    평가 이유에서 단어 추출
    """

    words = []

    for text in texts:

        tokens = re.findall(
            r"[가-힣A-Za-z0-9]{2,}",
            str(text)
        )

        for token in tokens:

            token = token.lower()

            token = WORD_REPLACE.get(
                token, token
            )

            if token not in STOPWORDS:
                words.append(token)

    return Counter(words)


@st.cache_data(show_spinner=False)
def korean_font_path():
    """
    한글 폰트 경로 탐색
    """

    candidates = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/malgun.ttf"
    ]

    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate

    font_root = Path("/usr/share/fonts")

    if font_root.exists():

        patterns = [
            "**/NanumGothic.ttf",
            "**/NanumBarunGothic.ttf",
            "**/NotoSansCJK-Regular.ttc"
        ]

        for pattern in patterns:

            found = next(
                font_root.glob(pattern),
                None
            )

            if found is not None:
                return str(found)

    return None


def show_wordcloud(frequencies):
    """
    평가 이유 워드클라우드 출력
    """

    font_path = korean_font_path()

    if not font_path:

        st.warning(
            "한글 폰트가 없습니다. "
            "교사용 저장소의 packages.txt에 "
            "fonts-nanum을 추가해 주세요."
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

        fig.patch.set_facecolor(
            "#fffaff"
        )

        st.pyplot(
            fig,
            use_container_width=True
        )

        plt.close(fig)

    except Exception as error:

        st.error(
            f"워드클라우드 생성 실패: {error}"
        )

# ==========================================
# 6. 교사용 로그인
# ==========================================

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

            correct_password = (
                st.secrets["teacher_password"]
            )

            if hmac.compare_digest(
                password,
                correct_password
            ):

                st.session_state.authenticated = True

                with st.spinner(
                    "🌷 평가 결과를 불러오고 있어요..."
                ):
                    refresh_results(
                        st.session_state.selected_class_teacher
                    )

                st.rerun()

            else:

                st.error(
                    "비밀번호가 올바르지 않습니다."
                )

    st.stop()

# ==========================================
# 7. 교사용 메인 화면
# ==========================================

st.markdown(
    '<div class="main-title">'
    '📊 AI 신호등 평가 결과'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    '분반별로 평가 결과를 확인해 보세요. 🌷'
    '</div>',
    unsafe_allow_html=True
)

header_left, header_right = st.columns(
    [5, 1]
)

with header_left:

    class_id = st.radio(
        "분반 선택",
        options=list(CLASSES),
        format_func=lambda c: CLASSES[c]["label"],
        horizontal=True,
        key="selected_class_teacher"
    )

with header_right:

    st.write("")

    if st.button(
        "로그아웃",
        use_container_width=True
    ):
        logout()
        st.rerun()

# ==========================================
# 8. 평가 조 선택
# ==========================================

total_groups = CLASSES[class_id]["groups"]

# 분반 변경 시 5조 -> 4조처럼
# 선택 범위가 달라질 수 있으므로 보정
if st.session_state.selected_group > total_groups:
    st.session_state.selected_group = 1

selected_group = st.radio(
    "평가 조 선택",
    options=list(
        range(1, total_groups + 1)
    ),
    format_func=lambda n: f"{n}조",
    horizontal=True,
    key="selected_group"
)

# ==========================================
# 9. 수동 새로고침
# ==========================================

if st.button(
    "🔄 평가 결과 새로고침",
    key="refresh_button",
    use_container_width=True
):

    with st.spinner(
        "🌷 최신 평가 결과를 불러오고 있어요..."
    ):

        refresh_results(class_id)

if st.session_state.load_error:
    st.error(st.session_state.load_error)

last_updated = (
    st.session_state.updated_cache.get(class_id)
)

if last_updated:

    st.caption(
        f"{CLASSES[class_id]['label']} "
        f"마지막 데이터 조회 : {last_updated}"
    )

# 처음 선택한 분반은 새로고침 필요
if class_id not in st.session_state.results_cache:

    st.info(
        f"{CLASSES[class_id]['label']}의 결과를 보려면 "
        "'평가 결과 새로고침'을 눌러 주세요."
    )

    st.stop()

# ==========================================
# 10. 평가 결과 집계
# ==========================================

df = st.session_state.results_cache[class_id]

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

st.divider()

st.markdown(
    f'<div class="section-title">'
    f'🌼 {CLASSES[class_id]["label"]} · '
    f'{selected_group}조 평가 현황'
    f'</div>',
    unsafe_allow_html=True
)

st.metric(
    "현재 평가 참여 인원",
    f"{total}명"
)

# ==========================================
# 11. 가능 / 제한 / 금지 통계 카드
# ==========================================

cols = st.columns(3)

css_names = [
    "green",
    "yellow",
    "red"
]

for col, answer, css_name in zip(
    cols,
    ANSWERS,
    css_names
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
# 12. 원그래프
# ==========================================

if total == 0:

    st.info(
        "아직 이 조에 대한 평가 결과가 없습니다."
    )

else:

    labels = [
        answer
        for answer in ANSWERS
        if counts[answer] > 0
    ]

    values = [
        counts[answer]
        for answer in labels
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
# 13. 평가 이유 필터
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

# 실제 이유가 작성된 응답만 추출
valid_reasons = reason_df[
    reason_df["이유"]
    .fillna("")
    .astype(str)
    .str.strip() != ""
].copy()

st.caption(
    f"평가 응답 {len(reason_df)}개 · "
    f"이유가 있는 응답 {len(valid_reasons)}개"
)

# ==========================================
# 14. 워드클라우드
# ==========================================

st.markdown(
    "### ☁️ 평가 이유 워드클라우드"
)

if valid_reasons.empty:

    st.info(
        "선택한 분반·조·평가 유형에는 "
        "작성된 평가 이유가 없습니다."
    )

else:

    frequencies = extract_words(
        valid_reasons["이유"].tolist()
    )

    st.caption(
        f"분석된 단어 종류 : {len(frequencies)}개"
    )

    if not frequencies:

        st.warning(
            "평가 이유는 있지만, "
            "두 글자 이상인 분석 대상 단어가 없습니다."
        )

    else:

        show_wordcloud(frequencies)

        st.markdown(
            "**🔎 자주 등장한 단어 TOP 10**"
        )

        st.write(
            " · ".join(
                f"{word} ({count}회)"
                for word, count
                in frequencies.most_common(10)
            )
        )

st.divider()

# ==========================================
# 15. 학생 평가 이유 목록
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
                f'🕒 제출 시간 : {row["제출시간"]}'
            )

st.markdown(
    '<div class="note">'
    '🌷 새로고침 버튼을 누르면 '
    '선택한 분반의 최신 결과가 반영됩니다.'
    '</div>',
    unsafe_allow_html=True
)
