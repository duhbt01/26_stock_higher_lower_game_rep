"""yfinance로 종목의 최근 1개월 가격을 조회하고, 쓸 수 있는 데이터인지 확인한다.

수익률 계산(game_logic.py)과 화면 표시(ui.py)는 이 파일에서 하지 않는다.
"""

import logging

import pandas as pd
import streamlit as st
import yfinance as yf

# 조회 실패 원인을 터미널에 남기는 로거
logger = logging.getLogger(__name__)

# yfinance는 기본 설정에서 네트워크 오류가 나도 예외 대신 빈 DataFrame을 돌려준다.
# 그러면 "네트워크 오류"와 "데이터 없음"을 구분할 수 없으므로, 오류를 예외로 받도록 바꾼다.
# (yfinance 1.8.0에서 예전 raise_errors 옵션을 대체하는 설정)
yf.config.debug.hide_exceptions = False

PERIOD = "1mo"            # 조회 기간: 최근 1개월
CACHE_SECONDS = 10 * 60   # 같은 종목을 다시 조회하지 않고 캐시를 쓰는 시간: 10분 (새 판마다 최신 가격 반영)

# load_stock_prices가 돌려주는 상태 값
STATUS_OK = "ok"                        # 정상 데이터
STATUS_INVALID = "invalid"              # 응답은 왔지만 가격이 비었거나 부족함 → 그 판에서 종목 제외
STATUS_NETWORK_ERROR = "network_error"  # 조회 중 오류 → 종목은 두고 다시 시도


@st.cache_data(ttl=CACHE_SECONDS)
def fetch_price_history(ticker: str) -> tuple[pd.DataFrame, dict]:
    """ticker의 최근 1개월 조정 가격 데이터와 시세 시각 정보를 조회한다.

    auto_adjust=True로 배당·분할이 반영된 조정 가격을 받아 'Close' 열에 담는다.
    시세 시각 정보는 history()가 가격과 함께 받아 온 메타데이터라 추가 요청이 없다.
    네트워크 오류는 예외로 그대로 올라간다. 예외로 끝난 호출은 캐시에 저장되지 않는다.
    """
    stock = yf.Ticker(ticker)
    history = stock.history(period=PERIOD, auto_adjust=True)

    metadata = stock.history_metadata
    regular_session = metadata.get("currentTradingPeriod", {}).get("regular", {})
    market_times = {
        "last_trade_time": metadata.get("regularMarketTime"),   # 마지막 체결 시각
        "session_start": regular_session.get("start"),          # 정규장 시작 시각
        "session_end": regular_session.get("end"),              # 정규장 마감 시각
        "timezone": metadata.get("exchangeTimezoneName"),       # 거래소 시간대 (예: Asia/Seoul)
    }
    return history, market_times


def is_intraday(
    last_trade_time: pd.Timestamp | None, session_start: pd.Timestamp | None, session_end: pd.Timestamp | None
) -> bool:
    """마지막 체결이 정규장 시간 안이면(시작 ≤ 체결 < 마감) 장중 가격으로 본다.

    시각 정보가 하나라도 없으면 장중이라고 단정하지 않고 False를 돌려준다.
    """
    if last_trade_time is None or session_start is None or session_end is None:
        return False
    return session_start <= last_trade_time < session_end


def load_stock_prices(ticker: str) -> tuple[str, dict | None]:
    """ticker의 날짜별 조정 종가와 시세 시각 정보를 조회하고 상태와 함께 돌려준다.

    반환값: (상태, 종목 가격 정보)
      - (STATUS_OK, {"prices", "last_trade_time", "is_intraday"}): 계산에 쓸 수 있는 정상 데이터
        prices: 날짜별 종가 Series / last_trade_time: 거래소 현지 시각의 마지막 체결 시각(없으면 None)
        is_intraday: 마지막 가격이 장중 가격인지
      - (STATUS_INVALID, None): 가격이 비었거나 2개 미만, 또는 첫·마지막 가격이 0 이하
      - (STATUS_NETWORK_ERROR, None): 조회 중 예외 발생
    """
    try:
        history, market_times = fetch_price_history(ticker)
    except Exception as error:
        # 연결 실패가 대부분이지만, 없는 ticker(404)나 예상하지 못한 오류도 여기로 온다.
        # 게임은 멈추지 않고 재시도하되, 실제 원인은 숨기지 않고 터미널 로그에 남긴다.
        logger.warning("%s 조회 실패 (%s): %s", ticker, type(error).__name__, error)
        return STATUS_NETWORK_ERROR, None

    if "Close" not in history.columns:
        return STATUS_INVALID, None

    close_prices = history["Close"].dropna()
    if len(close_prices) < 2:
        return STATUS_INVALID, None

    # 수익률(마지막 / 첫 - 1)을 계산하려면 첫 가격과 마지막 가격이 모두 양수여야 한다.
    first_price = close_prices.iloc[0]
    last_price = close_prices.iloc[-1]
    if first_price <= 0 or last_price <= 0:
        return STATUS_INVALID, None

    # 화면에 보여줄 마지막 체결 시각은 거래소 현지 시각으로 바꿔 둔다.
    last_trade_time = market_times["last_trade_time"]
    if last_trade_time is not None and market_times["timezone"] is not None:
        last_trade_time = last_trade_time.tz_convert(market_times["timezone"])

    stock_prices = {
        "prices": close_prices,
        "last_trade_time": last_trade_time,
        "is_intraday": is_intraday(
            market_times["last_trade_time"], market_times["session_start"], market_times["session_end"]
        ),
    }
    return STATUS_OK, stock_prices
