"""게임 규칙: 수익률 계산, 중복 없는 새 상대 뽑기, Higher/Lower 판정.

Streamlit 세션 상태나 화면에 의존하지 않는 순수 함수만 둔다.
입력을 받아 결과를 돌려줄 뿐, 게임 상태를 직접 바꾸지 않는다(상태 변경은 app.py가 맡는다).
"""

import random

import pandas as pd

# 대진 하나 = 정렬된 두 ticker의 tuple. 예: ("AAPL", "MSFT")
# 항상 정렬된 순서로 만들기 때문에 A-B와 B-A가 같은 대진으로 취급된다.
Pair = tuple[str, str]

HIGHER = "higher"   # 오른쪽 종목이 왼쪽보다 더 크게 움직였다
LOWER = "lower"     # 오른쪽 종목이 왼쪽보다 덜 움직였다


def calculate_period_return(close_prices: pd.Series) -> float:
    """기간 수익률(마지막 종가 / 첫 종가 - 1)을 계산한다.

    부호가 있는 값을 돌려준다. 예: 22% 상승 → 0.22, 37% 하락 → -0.37
    가격이 2개 미만이거나 첫 가격이 0 이하이면 ValueError를 일으킨다.
    """
    if len(close_prices) < 2:
        raise ValueError("수익률을 계산하려면 가격이 2개 이상 필요합니다.")

    first_price = close_prices.iloc[0]
    last_price = close_prices.iloc[-1]
    if first_price <= 0:
        raise ValueError("첫 가격이 0 이하라 수익률을 계산할 수 없습니다.")

    return float(last_price / first_price - 1)


def calculate_return_path(close_prices: pd.Series) -> pd.Series:
    """첫날을 0으로 두고, 날마다 첫날 대비 수익률이 얼마였는지 돌려준다.

    예: 종가 [100, 90, 122] → [0.0, -0.10, 0.22]
    마지막 값이 calculate_period_return의 기간 수익률과 같다. 차트와 (후속) 파형 효과음에 쓴다.
    """
    if len(close_prices) == 0 or close_prices.iloc[0] <= 0:
        raise ValueError("첫 가격이 있어야 하고 0보다 커야 합니다.")
    return close_prices / close_prices.iloc[0] - 1


def make_pair(ticker_a: str, ticker_b: str) -> Pair:
    """두 ticker를 정렬해 대진 하나로 만든다. make_pair("B", "A")와 make_pair("A", "B")는 같다."""
    return tuple(sorted([ticker_a, ticker_b]))


def pick_next_challenger(
    left_ticker: str, candidate_tickers: list[str], used_pairs: set[Pair], seen_tickers: set[str]
) -> tuple[str, bool] | None:
    """새 오른쪽 종목을 무작위로 고른다. 이번 판에 아직 나오지 않은 종목을 먼저 고른다.

    left_ticker: 현재 왼쪽 카드 종목
    candidate_tickers: 이번 판에서 쓸 수 있는 ticker 목록(제외된 종목은 빠져 있어야 한다)
    used_pairs: 이번 순환에서 이미 나온 대진들
    seen_tickers: 이번 판에서 이미 화면에 나온 종목들

    고르는 순서:
      1. 아직 나오지 않은 종목이 있으면 그중에서 고른다(이미 본 수익률을 외워서 맞히지 못하게).
      2. 모두 나왔으면, 왼쪽 종목과 아직 붙어 보지 않은 종목 중에서 고른다.
      3. 그것도 없으면 새 순환을 시작한다.

    반환값:
      - (오른쪽 ticker, 새 순환 여부): 3번의 경우 새 순환 여부가 True다.
        이때 호출한 쪽은 used_pairs를 비워야 한다.
      - None: 왼쪽 종목 말고는 후보가 없어 대진을 만들 수 없음
    """
    other_tickers = []
    for ticker in sorted(set(candidate_tickers)):
        if ticker != left_ticker:
            other_tickers.append(ticker)
    if len(other_tickers) == 0:
        return None

    # 1. 이번 판에 아직 나오지 않은 종목 우선 (처음 나오는 종목이라 왼쪽과 붙은 적도 없다)
    unseen_tickers = []
    for ticker in other_tickers:
        if ticker not in seen_tickers:
            unseen_tickers.append(ticker)
    if len(unseen_tickers) > 0:
        return random.choice(unseen_tickers), False

    # 2. 모두 나왔으면 왼쪽 종목과 아직 붙어 보지 않은 종목
    available_tickers = []
    for ticker in other_tickers:
        if make_pair(left_ticker, ticker) not in used_pairs:
            available_tickers.append(ticker)

    # 3. 왼쪽 종목과 붙일 수 있는 상대를 모두 썼으면 새 순환을 시작한다.
    is_new_cycle = False
    if len(available_tickers) == 0:
        available_tickers = other_tickers
        is_new_cycle = True

    challenger_ticker = random.choice(available_tickers)
    return challenger_ticker, is_new_cycle


def judge_higher_lower(left_return: float, right_return: float) -> str | None:
    """오른쪽 종목이 왼쪽보다 더 크게 움직였으면 HIGHER, 덜 움직였으면 LOWER를 돌려준다.

    반올림하지 않은 절대 수익률로 비교한다. 같으면 무승부로 보고 None을 돌려준다.
    """
    left_score = abs(left_return)
    right_score = abs(right_return)

    if right_score > left_score:
        return HIGHER
    if right_score < left_score:
        return LOWER
    return None
