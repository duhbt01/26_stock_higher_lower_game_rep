"""앱 진입점: 세션 상태를 관리하고, 데이터·규칙·화면 모듈을 연결한다.

실행: streamlit run app.py
"""

import random
import time

import streamlit as st

import ui
from game_logic import calculate_period_return, judge_higher_lower, make_pair, pick_next_challenger
from stock_data import STATUS_INVALID, STATUS_NETWORK_ERROR, STATUS_OK, load_stock_prices
from stock_universe import get_all_tickers, get_stock_by_ticker

# 비정상 데이터 종목을 제외하며 대진을 다시 뽑는 최대 횟수 (무한 재시도 방지)
# 네트워크 오류는 다시 뽑지 않고 바로 안내한다(다시 뽑으면 이미 받아둔 종목이 유리해지기 때문).
MAX_PAIR_ATTEMPTS = 5
# 정답·무승부일 때 결과를 보여준 뒤 다음 라운드로 넘어가기까지 기다리는 시간(초)
AUTO_ADVANCE_SECONDS = 2.0

DATA_ERROR_MESSAGE = (
    "주가 데이터를 불러오지 못했습니다. 인터넷 연결을 확인한 뒤 다시 시도해 주세요. "
    "지금까지의 연승은 그대로 유지됩니다."
)


def reset_game_state() -> None:
    """새 판을 위해 게임 상태를 처음 값으로 되돌린다."""
    st.session_state.streak = 0
    st.session_state.used_pairs = set()          # 이번 순환에서 이미 나온 대진
    st.session_state.seen_tickers = set()        # 이번 판에서 이미 화면에 나온 종목
    st.session_state.excluded_tickers = set()    # 이번 판에서 비정상 데이터로 제외된 종목
    st.session_state.price_snapshot = {}         # 이번 판에서 받은 가격 정보 (ticker → load_stock_prices가 준 dict)
    st.session_state.left_ticker = None          # 왼쪽 카드 종목 (1라운드 전에는 None)
    st.session_state.right_ticker = None         # 오른쪽 카드 종목
    st.session_state.round_history = []          # 라운드별 결과 기록
    st.session_state.data_error = None           # 데이터 문제 안내 문구


def init_session_state() -> None:
    """앱을 처음 열었을 때만 세션 상태를 만든다."""
    if "phase" not in st.session_state:
        st.session_state.phase = "start"         # "start" → "question" → "result"
        reset_game_state()


def load_into_snapshot(ticker: str) -> str:
    """종목 가격을 이번 판의 스냅샷에 넣고, 조회 상태(STATUS_OK/INVALID/NETWORK_ERROR)를 돌려준다.

    이미 받은 종목이면 다시 조회하지 않는다(한 판 동안 가격 고정).
    비정상 데이터면 그 종목을 이번 판에서 제외한다. 네트워크 오류면 제외하지 않는다.
    """
    snapshot = st.session_state.price_snapshot
    if ticker in snapshot:
        return STATUS_OK

    status, stock_prices = load_stock_prices(ticker)
    if status == STATUS_OK:
        snapshot[ticker] = stock_prices          # 종가와 시세 시각 정보를 함께 고정한다
    elif status == STATUS_INVALID:
        st.session_state.excluded_tickers.add(ticker)
    return status


def get_candidate_tickers() -> list[str]:
    """이번 판에서 아직 제외되지 않은 후보 ticker 목록을 돌려준다."""
    candidates = []
    for ticker in get_all_tickers():
        if ticker not in st.session_state.excluded_tickers:
            candidates.append(ticker)
    return candidates


def prepare_next_round() -> bool:
    """다음 라운드의 왼쪽·오른쪽 종목을 준비한다. 성공하면 True를 돌려준다.

    1라운드(left_ticker가 None)에는 왼쪽 종목도 새로 고르고,
    그 뒤로는 left_ticker를 그대로 두고 새 오른쪽 종목만 고른다.
    비정상 데이터 종목은 제외하고 MAX_PAIR_ATTEMPTS번까지 다시 뽑는다.
    네트워크 오류는 다시 뽑지 않고 바로 멈춘다. 다시 뽑으면 조회가 필요 없는 '이미 받아둔 종목'만
    통과하게 되어, 오프라인에서 수익률을 아는 종목만 나오는 꼼수가 생기기 때문이다(시행착오.md 11번).
    준비하지 못하면 data_error에 안내 문구를 남기고 False를 돌려준다.
    """
    for _attempt in range(MAX_PAIR_ATTEMPTS):
        candidates = get_candidate_tickers()

        left_ticker = st.session_state.left_ticker
        if left_ticker is None:                  # 1라운드: 왼쪽 종목도 무작위로 고른다
            if len(candidates) == 0:
                break
            left_ticker = random.choice(candidates)
            left_status = load_into_snapshot(left_ticker)
            if left_status == STATUS_NETWORK_ERROR:
                break
            if left_status == STATUS_INVALID:
                continue

        picked = pick_next_challenger(
            left_ticker, candidates, st.session_state.used_pairs, st.session_state.seen_tickers
        )
        if picked is None:                       # 왼쪽 말고는 후보가 없어 대진을 만들 수 없음
            break
        right_ticker, is_new_cycle = picked
        if is_new_cycle:                         # 왼쪽 종목과 붙일 상대를 다 썼으니 기록을 비우고 새 순환
            st.session_state.used_pairs = set()

        right_status = load_into_snapshot(right_ticker)
        if right_status == STATUS_NETWORK_ERROR:
            break
        if right_status == STATUS_INVALID:
            continue

        # 두 종목 데이터를 모두 받은 뒤에만 '이미 나온 대진'과 '이미 나온 종목'으로 기록한다.
        st.session_state.used_pairs.add(make_pair(left_ticker, right_ticker))
        st.session_state.seen_tickers.update([left_ticker, right_ticker])
        st.session_state.left_ticker = left_ticker
        st.session_state.right_ticker = right_ticker
        st.session_state.data_error = None
        st.session_state.phase = "question"
        return True

    st.session_state.data_error = DATA_ERROR_MESSAGE
    return False


def start_next_round() -> None:
    """로딩 안내를 보여주며 다음 라운드를 준비한다."""
    with st.spinner("주가 데이터를 불러오는 중..."):
        prepare_next_round()


def get_period_return(ticker: str) -> float:
    """스냅샷에 저장된 종가로 종목의 기간 수익률을 계산한다."""
    return calculate_period_return(st.session_state.price_snapshot[ticker]["prices"])


def build_revealed_card(ticker: str) -> dict:
    """공개 카드에 보여줄 정보(종가, 수익률, 마지막 체결 시각, 장중 여부)를 모은다."""
    stock_prices = st.session_state.price_snapshot[ticker]
    return {
        "prices": stock_prices["prices"],
        "period_return": get_period_return(ticker),
        "last_trade_time": stock_prices["last_trade_time"],
        "is_intraday": stock_prices["is_intraday"],
    }


def handle_choice(choice: str) -> None:
    """플레이어의 Higher/Lower 선택을 판정하고, 연승과 라운드 기록을 갱신한다."""
    left_ticker = st.session_state.left_ticker
    right_ticker = st.session_state.right_ticker
    left_return = get_period_return(left_ticker)
    right_return = get_period_return(right_ticker)

    correct_choice = judge_higher_lower(left_return, right_return)
    if correct_choice is None:
        outcome = "draw"                         # 무승부: 연승 유지
    elif choice == correct_choice:
        outcome = "correct"
        st.session_state.streak += 1
    else:
        outcome = "wrong"                        # 오답: 이번 판 종료

    st.session_state.round_history.append({
        "round": len(st.session_state.round_history) + 1,
        "left_ticker": left_ticker,
        "left_name": get_stock_by_ticker(left_ticker)["name"],
        "left_return": left_return,
        "right_ticker": right_ticker,
        "right_name": get_stock_by_ticker(right_ticker)["name"],
        "right_return": right_return,
        "choice": choice,
        "correct_choice": correct_choice,
        "outcome": outcome,
    })
    st.session_state.phase = "result"


def advance_after_delay(previous_right_ticker: str) -> None:
    """잠깐 기다린 뒤 다음 라운드로 넘어간다. 직전 오른쪽 종목이 새 왼쪽 종목이 된다.

    기다리는 동안 다음 오른쪽 종목 데이터를 미리 받아, 넘어갈 때 지연이 없게 한다.
    """
    started_at = time.time()
    st.session_state.left_ticker = previous_right_ticker
    st.session_state.right_ticker = None
    prepare_next_round()

    elapsed_seconds = time.time() - started_at
    if elapsed_seconds < AUTO_ADVANCE_SECONDS:
        time.sleep(AUTO_ADVANCE_SECONDS - elapsed_seconds)
    st.rerun()


def render_question() -> None:
    """문제 화면을 보여주고, 선택하면 판정한다. 1라운드에는 왼쪽 카드도 숨긴다."""
    left_ticker = st.session_state.left_ticker
    right_ticker = st.session_state.right_ticker

    is_first_round = len(st.session_state.round_history) == 0
    left_result = None
    if not is_first_round:
        left_result = build_revealed_card(left_ticker)

    choice = ui.show_question(
        get_stock_by_ticker(left_ticker), left_result, get_stock_by_ticker(right_ticker), st.session_state.streak
    )
    if choice is not None:
        handle_choice(choice)
        st.rerun()


def render_result() -> None:
    """방금 라운드의 결과와 두 종목의 수익률·차트를 공개한다.

    정답·무승부면 잠시 뒤 자동으로 다음 라운드로, 오답이면 대진 요약과 '다시 시작'을 보여준다.
    """
    record = st.session_state.round_history[-1]
    left_result = build_revealed_card(record["left_ticker"])
    right_result = build_revealed_card(record["right_ticker"])

    restart_clicked = ui.show_result(
        get_stock_by_ticker(record["left_ticker"]), left_result,
        get_stock_by_ticker(record["right_ticker"]), right_result,
        record["outcome"], record["correct_choice"], st.session_state.streak,
    )

    if record["outcome"] == "wrong":
        ui.show_round_summary(st.session_state.round_history)
        if restart_clicked:
            reset_game_state()
            start_next_round()
            st.rerun()
    else:
        advance_after_delay(record["right_ticker"])


def main() -> None:
    st.set_page_config(page_title="더 크게 움직인 주식은?", page_icon="📈", layout="wide")
    init_session_state()

    if st.session_state.data_error is not None:
        if ui.show_data_error(st.session_state.data_error):
            start_next_round()
            st.rerun()
    elif st.session_state.phase == "start":
        if ui.show_start_screen():
            reset_game_state()
            start_next_round()
            st.rerun()
    elif st.session_state.phase == "question":
        render_question()
    elif st.session_state.phase == "result":
        render_result()

    ui.show_footer()


main()
