"""Streamlit 화면 표시 함수.

받은 데이터를 화면에 그리고, 버튼이 눌렸는지만 돌려준다.
게임 상태(session_state)를 바꾸는 일은 app.py가 맡는다.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

from game_logic import HIGHER, LOWER, calculate_return_path
from stock_universe import PRICE_FORMATS

# 결과·선택 값을 화면에 보일 문구로 바꾸는 표
OUTCOME_LABELS = {"correct": "정답", "wrong": "오답", "draw": "무승부"}
CHOICE_LABELS = {HIGHER: "▲ Higher", LOWER: "▼ Lower"}

# 결과 아이콘: app.py가 있는 폴더 기준 images 폴더 (어느 위치에서 실행해도 찾을 수 있게)
IMAGES_DIR = Path(__file__).parent / "images"
OUTCOME_ICONS = {
    "correct": IMAGES_DIR / "check-icon.png",
    "wrong": IMAGES_DIR / "cross.png",
    "draw": IMAGES_DIR / "tie.png",
}

CARD_HEIGHT = 510       # 카드 세로 길이(px). 숨김·공개 상태 모두 같은 높이로 그려 크기 변화를 없앤다.
CHART_HEIGHT = 170         # 카드 안 차트 높이(px)
ICON_WIDTH = 64            # 가운데 결과 아이콘 크기(px)
COLUMN_RATIO = [5, 1, 5]   # 왼쪽 카드 : 가운데 칸 : 오른쪽 카드


def format_return(period_return: float) -> str:
    """수익률을 부호가 있는 퍼센트 문자열로 바꾼다. 예: 0.2234 → '+22.34%'"""
    return f"{period_return * 100:+.2f}%"


def format_price(price: float, market: str) -> str:
    """가격을 시장 통화에 맞는 문자열로 바꾼다. 예: (216.0, 미국) → '$216.00', (176300, 한국) → '176,300원'"""
    return PRICE_FORMATS[market].format(price)


def format_price_time(last_trade_time: pd.Timestamp | None, is_intraday: bool) -> str:
    """마지막 가격이 언제 기준인지 알려주는 문구를 만든다.

    '종가'라는 말은 쓰지 않는다. Yahoo가 알려주는 정규장 마감 시각이 실제와 다른 시장이 있어
    장중 가격을 종가로 잘못 부를 수 있기 때문이다(시행착오.md 9번).
    """
    if last_trade_time is None:
        return ""
    time_text = last_trade_time.strftime("%m-%d %H:%M")
    if is_intraday:
        return f"🔴 장중 · {time_text} (현지 시각) · 지연 시세"
    return f"{time_text} (현지 시각) 기준 가격"


def show_start_screen() -> bool:
    """시작 화면을 그린다. 시작 버튼을 눌렀으면 True를 돌려준다."""
    st.title("더 크게 움직인 주식은?")
    st.write("오른쪽 종목이 왼쪽 종목보다 **최근 1개월 동안 더 크게 움직였는지** 맞혀보세요.")
    st.markdown(
        "- 오르든 내리든 **움직인 크기(절대 수익률)**만 비교합니다. +22%보다 -37%가 더 크게 움직인 것입니다.\n"
        "- 오른쪽이 더 크게 움직였으면 **▲ Higher**, 덜 움직였으면 **▼ Lower**를 고르세요.\n"
        "- 맞히면 오른쪽 종목이 왼쪽으로 옮겨지고 새 종목이 등장합니다. 2라운드부터는 왼쪽 종목의 수익률이 공개됩니다.\n"
        "- 틀리면 게임이 끝납니다. 크기가 같으면 무승부로 연승이 유지됩니다.\n"
        "- 수익률은 최근 1개월 조정 종가의 `마지막 종가 / 첫 종가 - 1`로 계산합니다."
    )
    return st.button("게임 시작", type="primary")


def show_header(streak: int) -> None:
    """현재 연승과 질문을 한 줄로 보여준다."""
    st.markdown(
        f"**현재 연승: {streak}** &nbsp;·&nbsp; 오른쪽 종목은 왼쪽보다 최근 1개월 동안 **더 크게 움직였을까?** "
        "(상승·하락과 상관없이 크기만 비교)"
    )


def show_card(stock: dict, revealed: dict | None, with_buttons: bool = False) -> str | None:
    """종목 카드 하나를 고정 높이로 그린다.

    revealed: 공개할 때 {"prices", "period_return", "last_trade_time", "is_intraday"}, 숨길 때 None
    with_buttons: 숨긴 카드 안에 Higher/Lower 버튼을 넣을지 여부
    반환값: 버튼으로 고른 값(HIGHER 또는 LOWER), 고르지 않았으면 None
    """
    choice = None
    with st.container(height=CARD_HEIGHT, border=True):
        st.markdown(f"#### {stock['name']}")
        st.caption(f"{stock['ticker']} · {stock['market']} 시장")

        if revealed is None:
            # 숨김 상태: 수익률 대신 물음표와 (필요하면) 선택 버튼
            st.markdown(
                "<div style='text-align:center; font-size:72px; padding:24px 0;'>❓</div>",
                unsafe_allow_html=True,
            )
            if with_buttons:
                higher_column, lower_column = st.columns(2)
                with higher_column:
                    if st.button(CHOICE_LABELS[HIGHER], key="choose_higher", type="primary", width="stretch"):
                        choice = HIGHER
                with lower_column:
                    if st.button(CHOICE_LABELS[LOWER], key="choose_lower", type="primary", width="stretch"):
                        choice = LOWER
            else:
                st.caption("결과 공개 때 함께 보여드립니다.")
        else:
            # 공개 상태: 수익률, 움직인 크기, 기준 기간, 차트
            prices = revealed["prices"]
            period_return = revealed["period_return"]
            st.metric("1개월 수익률", format_return(period_return))
            st.write(f"움직인 크기(절대 수익률): **{abs(period_return) * 100:.2f}%**")

            # 수익률 계산에 쓴 시작·마지막 가격과, 기간 중 최고·최저 가격(차트와 같은 일별 가격 기준)
            market = stock["market"]
            price_text = (
                f"{format_price(prices.iloc[0], market)} → {format_price(prices.iloc[-1], market)}"
                f" · 최고 {format_price(prices.max(), market)} · 최저 {format_price(prices.min(), market)}"
            )
            # Streamlit은 $...$ 사이를 수식으로 바꿔 그리므로, 달러 기호 앞에 \를 붙여 글자 그대로 보이게 한다.
            st.caption(price_text.replace("$", "\\$"))

            # 시장마다 거래일이 다르므로 기준 기간을 종목별로 따로 표시한다.
            first_date = prices.index[0].date()
            last_date = prices.index[-1].date()
            st.caption(f"기준 기간: {first_date} ~ {last_date} ({stock['market']} 시장 거래일 {len(prices)}일)")
            price_time_text = format_price_time(revealed["last_trade_time"], revealed["is_intraday"])
            if price_time_text:
                st.caption(price_time_text)
            # 가격 대신 '첫날 대비 몇 %'를 그린다. 0% 선이 시작점이라 움직인 크기가 잘 보이고 통화 차이도 없다.
            percent_path = calculate_return_path(prices) * 100
            percent_path.name = "시작 대비 변화(%)"   # 마우스를 올렸을 때 보이는 이름
            st.line_chart(percent_path, height=CHART_HEIGHT, x_label="", y_label="시작 대비 변화(%)")
    return choice


def show_middle_vs() -> None:
    """선택 전 가운데 칸에 'VS'를 보여준다."""
    with st.container(horizontal_alignment="center"):
        st.subheader("VS", anchor=False, width="content")   # anchor=False: 제목 옆 링크 아이콘 자리를 없애 정확히 가운데 정렬


def show_middle_outcome(outcome: str, correct_choice: str | None) -> bool:
    """선택 후 가운데 칸에 결과 아이콘과 문구를 보여준다.

    오답이면 아이콘 아래에 '다시 하기' 버튼도 둔다. 버튼을 눌렀으면 True를 돌려준다.
    """
    if outcome == "wrong":
        caption = f"정답: {CHOICE_LABELS[correct_choice]}"
    else:
        caption = OUTCOME_LABELS[outcome]

    # 이 상자 안의 아이콘·문구·버튼을 가로 가운데에 놓는다.
    with st.container(horizontal_alignment="center"):
        st.image(OUTCOME_ICONS[outcome], width=ICON_WIDTH)
        st.caption(caption, width="content")
        if outcome == "wrong":
            return st.button("다시 하기", key="restart", type="primary", width="stretch")
        # 정답·무승부: 다음 종목 조회가 늦어져도 멈춘 화면으로 보이지 않게 안내한다.
        st.caption("곧 다음 라운드", width="content")   # 가운데 칸이 좁아 짧은 문구를 쓴다
    return False


def show_question(left_stock: dict, left_result: dict | None, right_stock: dict, streak: int) -> str | None:
    """문제 화면을 그린다. Higher/Lower 버튼은 오른쪽 카드 안에 있다.

    left_result: 왼쪽 카드를 공개할 때 show_card의 revealed와 같은 dict, 1라운드처럼 숨길 때 None
    반환값: 고른 값(HIGHER 또는 LOWER), 아직 고르지 않았으면 None
    """
    show_header(streak)
    left_column, middle_column, right_column = st.columns(COLUMN_RATIO, vertical_alignment="center")
    with left_column:
        show_card(left_stock, left_result)
    with middle_column:
        show_middle_vs()
    with right_column:
        choice = show_card(right_stock, None, with_buttons=True)
    return choice


def show_result(
    left_stock: dict, left_result: dict, right_stock: dict, right_result: dict,
    outcome: str, correct_choice: str | None, streak: int,
) -> bool:
    """결과 화면을 그린다. 문제 화면과 같은 배치에서 카드만 공개 상태로 바뀌고, 가운데에 결과 아이콘이 뜬다.

    반환값: 오답일 때 가운데의 '다시 하기' 버튼을 눌렀으면 True
    """
    show_header(streak)
    left_column, middle_column, right_column = st.columns(COLUMN_RATIO, vertical_alignment="center")
    with left_column:
        show_card(left_stock, left_result)
    with middle_column:
        restart_clicked = show_middle_outcome(outcome, correct_choice)
    with right_column:
        show_card(right_stock, right_result)
    return restart_clicked


def show_round_summary(round_history: list[dict]) -> None:
    """게임 오버 때 이번 판의 대진 요약 표를 보여준다."""
    st.markdown("**이번 판 대진 요약**")

    rows = []
    for record in round_history:
        rows.append({
            "라운드": record["round"],
            "왼쪽": record["left_name"],
            "왼쪽 수익률": format_return(record["left_return"]),
            "오른쪽": record["right_name"],
            "오른쪽 수익률": format_return(record["right_return"]),
            "내 선택": CHOICE_LABELS[record["choice"]],
            "결과": OUTCOME_LABELS[record["outcome"]],
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True)


def show_data_error(message: str) -> bool:
    """데이터 문제 안내와 '다시 시도' 버튼을 그린다. 눌렀으면 True를 돌려준다."""
    st.warning(message)
    return st.button("다시 시도")


def show_footer() -> None:
    """데이터 출처와 투자 조언이 아니라는 안내를 보여준다."""
    st.divider()
    st.caption(
        "이 게임은 교육용이며 투자 조언이 아닙니다. 가격은 yfinance(Yahoo Finance 데이터를 가져오는 "
        "비공식 오픈소스 라이브러리)로 받은 조정 가격입니다. 장중에는 실시간이 아닌 지연 시세"
        "(미국 약 15분, 한국 약 20분)이며, 부정확할 수 있습니다."
    )
    st.caption(
        "아이콘: Ampeross(Qetto 2 Icons), Hopstarter(Button Icons, CC BY-NC-ND 4.0), "
        "Bootstrap Team(Bootstrap Icons, MIT) · Icon Archive 제공. 자세한 출처는 CREDITS.md 참고."
    )
