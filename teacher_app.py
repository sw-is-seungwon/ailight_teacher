
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import hmac
from html import escape

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

/* 제목 */
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

div.stButton > button:hover,
div.stFormSubmitButton > button:hover {
    background: #decbfa;
    border-color: #b9a4db;
}

/* 새로고침 버튼 */
.st-key-refresh_button button {
    background: #d5edff !important;
    color: #4c6b92 !important;
    border: 2px solid #b9dafa !important;
    min-height: 60px !important;
    font-size: 18px !important;
}

/* 평가 현황 카드 */
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

/* 학생 평가 이유 */
.reason-card {
    background: white;
    border: 2px solid #eedced;
    border-radius: 17px;
    padding: 18px;
    margin: 12px 0;
    color: #65596d;
    line-height: 1.8;
    overflow-wrap: anywhere;
}

.reason-content {
    margin-top: 8px;
    white-space: pre-wrap;
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
    """Apps Script에서 평가 결과 가져오기"""

    response = requests.post(
        st.secrets["apps_script_url"],
        json={
            "action": "read",
            "password": st.secrets["teacher_password"]
        },
        timeout=(4, 12),
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

    # 평가조 숫자 변환
    df["평가조"] = pd.to_numeric(
        df["평가조"],
        errors="coerce"
    )

    # 유효한 평가만 추출
    df = df[
        df["평가조"].isin(GROUPS)
        & df["평가"].isin(ANSWERS)
    ].copy()

    # 같은 참여 ID가 같은 조를 여러 번
    # 평가했다면 마지막 응답만 사용
    df = df.drop_duplicates(
        subset=["참여ID", "평가조"],
        keep="last"
    )

    return df


def refresh_results():
    """버튼을 눌렀을 때만 최신 데이터 조회"""

    from datetime import datetime
    from zoneinfo import ZoneInfo

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
        # 기존 데이터는 유지
        st.session_state.load_error = (
            "최신 평가 결과를 불러오지 못했습니다. "
            "잠시 후 다시 시도해 주세요."
        )


# ==========================================
# 5. 로그인
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

                # 로그인 직후 최초 1회 데이터 조회
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

# ------------------------------------------
# 조 선택 및 로그아웃
# ------------------------------------------

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
# 7. 수동 새로고침 버튼
# ==========================================

# 자동 갱신 기능은 사용하지 않음

if st.button(
    "🔄 평가 결과 새로고침",
    key="refresh_button",
    use_container_width=True
):

    with st.spinner(
        "🌷 최신 평가 결과를 불러오고 있어요..."
    ):
        refresh_results()

# 데이터 조회 오류 안내
if st.session_state.load_error:
    st.error(
        st.session_state.load_error
    )

# 마지막 업데이트 시간 표시
if st.session_state.last_updated:

    st.caption(
        "마지막 데이터 조회 : "
        f"{st.session_state.last_updated}"
    )

st.divider()

# ==========================================
# 8. 평가 결과 대시보드
# ==========================================

# 최초 조회에 실패했다면 안내
if st.session_state.results_data is None:

    st.info(
        "평가 결과를 불러오지 못했어요. "
        "위의 새로고침 버튼을 눌러 주세요."
    )

    st.stop()

# 저장해 둔 데이터 사용
# 조 선택, 필터 변경 시에는 다시 통신하지 않음
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
# 1. 현재 평가 참여 인원
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
        config={
            "displayModeBar": False
        }
    )

st.divider()

# ==========================================
# 4. 학생들이 작성한 평가 이유
# ==========================================

st.markdown(
    "### 💬 학생들이 작성한 평가 이유"
)

# 평가 유형 선택
answer_filter = st.selectbox(
    "평가 유형",
    ["전체", "가능", "제한", "금지"],
    key="answer_filter"
)

# 선택한 유형에 따라 필터링
if answer_filter == "전체":
    reason_df = group_df.copy()
else:
    reason_df = group_df[
        group_df["평가"] == answer_filter
    ].copy()

st.caption(
    f"총 {len(reason_df)}개의 평가 이유"
)

# 평가 이유 표시
if reason_df.empty:
    st.info("아직 작성된 평가 이유가 없습니다.")

else:
    for _, row in reason_df.iterrows():

        answer = str(row["평가"])
        reason = str(row["이유"]).strip()
        submitted = str(row["제출시간"])

        with st.container(border=True):

            st.markdown(
                f"**{EMOJI[answer]} {answer}**"
            )

            if reason and reason.lower() != "nan":
                st.write(reason)
            else:
                st.warning("평가 이유가 비어 있습니다.")

            st.caption(f"🕒 제출 시간 : {submitted}")

st.markdown(
    '<div class="note">'
    '🌷 새로고침 버튼을 누르면 최신 평가 결과가 반영됩니다.'
    '</div>',
    unsafe_allow_html=True
)
