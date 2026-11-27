"""게임에 등장하는 후보 종목 목록.

ticker, 회사명, 시장 정보를 한 곳에서 함께 관리한다.
종목을 추가하거나 빼려면 이 파일의 STOCKS 목록만 고치면 된다.
"""

# 시장 이름 (화면에 그대로 표시한다)
MARKET_US = "미국"
MARKET_KR = "한국"

# 시장별 가격 표시 형식: 미국은 달러(소수 둘째 자리), 한국은 원(정수)
PRICE_FORMATS = {
    MARKET_US: "${:,.2f}",
    MARKET_KR: "{:,.0f}원",
}

# 후보 종목 목록: 미국 20개 + 한국 10개
# 한국 종목은 Yahoo Finance 형식에 맞춰 코스피 접미사 ".KS"를 붙인다.
STOCKS: list[dict[str, str]] = [
    # 미국 (20)
    {"ticker": "AAPL", "name": "Apple", "market": MARKET_US},
    {"ticker": "NVDA", "name": "NVIDIA", "market": MARKET_US},
    {"ticker": "MSFT", "name": "Microsoft", "market": MARKET_US},
    {"ticker": "GOOGL", "name": "Alphabet (Google)", "market": MARKET_US},
    {"ticker": "AMZN", "name": "Amazon", "market": MARKET_US},
    {"ticker": "SPCX", "name": "SpaceX", "market": MARKET_US},
    {"ticker": "META", "name": "Meta Platforms", "market": MARKET_US},
    {"ticker": "TSLA", "name": "Tesla", "market": MARKET_US},
    {"ticker": "AVGO", "name": "Broadcom", "market": MARKET_US},
    {"ticker": "BRK-B", "name": "Berkshire Hathaway Class B", "market": MARKET_US},
    {"ticker": "LLY", "name": "Eli Lilly", "market": MARKET_US},
    {"ticker": "WMT", "name": "Walmart", "market": MARKET_US},
    {"ticker": "JPM", "name": "JPMorgan Chase", "market": MARKET_US},
    {"ticker": "MU", "name": "Micron Technology", "market": MARKET_US},
    {"ticker": "V", "name": "Visa", "market": MARKET_US},
    {"ticker": "AMD", "name": "Advanced Micro Devices", "market": MARKET_US},
    {"ticker": "JNJ", "name": "Johnson & Johnson", "market": MARKET_US},
    {"ticker": "XOM", "name": "Exxon Mobil", "market": MARKET_US},
    {"ticker": "MA", "name": "Mastercard", "market": MARKET_US},
    {"ticker": "ABBV", "name": "AbbVie", "market": MARKET_US},
    # 한국 (10, 모두 코스피)
    {"ticker": "005930.KS", "name": "삼성전자", "market": MARKET_KR},
    {"ticker": "000660.KS", "name": "SK하이닉스", "market": MARKET_KR},
    {"ticker": "402340.KS", "name": "SK스퀘어", "market": MARKET_KR},
    {"ticker": "373220.KS", "name": "LG에너지솔루션", "market": MARKET_KR},
    {"ticker": "207940.KS", "name": "삼성바이오로직스", "market": MARKET_KR},
    {"ticker": "009150.KS", "name": "삼성전기", "market": MARKET_KR},
    {"ticker": "005380.KS", "name": "현대차", "market": MARKET_KR},
    {"ticker": "105560.KS", "name": "KB금융", "market": MARKET_KR},
    {"ticker": "032830.KS", "name": "삼성생명", "market": MARKET_KR},
    {"ticker": "068270.KS", "name": "셀트리온", "market": MARKET_KR},
]


def get_all_tickers() -> list[str]:
    """후보 종목의 ticker만 목록으로 돌려준다."""
    tickers = []
    for stock in STOCKS:
        tickers.append(stock["ticker"])
    return tickers


def get_stock_by_ticker(ticker: str) -> dict[str, str]:
    """ticker로 종목 정보(ticker, name, market)를 찾아 돌려준다.

    목록에 없는 ticker면 ValueError를 일으킨다.
    """
    for stock in STOCKS:
        if stock["ticker"] == ticker:
            return stock
    raise ValueError(f"후보 목록에 없는 ticker입니다: {ticker}")
