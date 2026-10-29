
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

div.stButton > button,
div.stFormSubmitButton > button {
    width: 100%;
    min-height: 50px;
    border-radius: 15px;
    background: #e9dcff;
    color: #5c4e7e;
    border: 2px solid #dac6f3;
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
# 3. Google Sheets 결과 조회
# ==========================================

def load_results():

    response = requests.post(
        st.secrets["apps_script_url"],
        json={
            "action": "read",
            "password": st.secrets["teacher_password"]
        },
        timeout=25
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

    df = df[
        df["평가조"].isin([1, 2, 3, 4])
        & df["평가"].isin(ANSWERS)
    ].copy()

    # 같은 참여 ID의 중복 응답은 마지막 것만
    df = df.drop_duplicates(
        subset=["참여ID", "평가조"],
        keep="last"
    )

    return df


# ==========================================
# 4. 로그인
# ==========================================

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False


def login(password):

    correct = st.secrets["teacher_password"]

    return hmac.compare_digest(
        password,
        correct
    )


if not st.session_state.authenticated:

    st.markdown(
        '<div class="main-title">🔒 교사용 신호등 평가</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">비밀번호를 입력해 주세요.</div>',
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
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")

    st.stop()

# ==========================================
# 5. 교사용 메인 화면
# ==========================================

st.markdown(
    '<div class="main-title">📊 AI 신호등 평가 결과</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    '학생들의 평가 결과를 실시간으로 확인할 수 있어요. 🌷'
    '</div>',
    unsafe_allow_html=True
)

left, right = st.columns([5, 1])

with left:
    group = st.radio(
        "결과를 확인할 조",
        [1, 2, 3, 4],
        format_func=lambda x: f"{x}조",
        horizontal=True
    )

with right:
    if st.button("로그아웃"):
        st.session_state.authenticated = False
        st.rerun()

st.divider()

# ==========================================
# 6. 실시간 대시보드
# ==========================================

@st.fragment(run_every="5s")
def dashboard():

    try:
        df = load_results()

    except Exception:
        st.error(
            "Google Sheets의 평가 결과를 "
            "불러오지 못했습니다."
        )
        return

    group_df = df[
        df["평가조"] == group
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
        f'🌼 {group}조 평가 현황</div>',
        unsafe_allow_html=True
    )

    st.metric(
        "현재 평가 참여 인원",
        f"{total}명"
    )

    # 평가별 인원과 비율
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

    # 원그래프
    if total == 0:
        st.info(
            "아직 이 조에 대한 평가가 없습니다."
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
                text=f"{group}조 신호등 평가 비율",
                x=0.5
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=420,
            margin=dict(
                l=20, r=20,
                t=60, b=20
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

    # 학생 평가 이유
    st.markdown(
        '<div class="section-title">'
        '💬 학생들이 작성한 평가 이유</div>',
        unsafe_allow_html=True
    )

    answer_filter = st.selectbox(
        "평가 유형",
        ["전체", "가능", "제한", "금지"],
        key="answer_filter"
    )

    if answer_filter == "전체":
        reason_df = group_df
    else:
        reason_df = group_df[
            group_df["평가"] == answer_filter
        ]

    st.caption(
        f"총 {len(reason_df)}개의 평가 이유"
    )

    if reason_df.empty:
        st.info("표시할 평가 이유가 없습니다.")

    for _, row in reason_df.iterrows():

        answer = row["평가"]

        reason = escape(
            str(row["이유"])
        )

        submitted = escape(
            str(row["제출시간"])
        )

        st.markdown(
            f"""
            <div class="reason-card">
                <b>{EMOJI[answer]} {answer}</b>
                <div class="reason-content">
                    {reason}
                </div>
                <div style="
                    color:#999;
                    font-size:12px;
                    margin-top:10px;
                ">
                    {submitted}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown(
        '<div class="note">'
        '🔄 5초마다 평가 결과를 자동으로 확인합니다.'
        '</div>',
        unsafe_allow_html=True
    )


dashboard()
