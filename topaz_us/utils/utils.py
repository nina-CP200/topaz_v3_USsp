from __future__ import annotations

import json
import os
from typing import List, Tuple


def load_stock_list_from_json(file_path: str) -> List[Tuple[str, str, str]]:
    if not os.path.exists(file_path):
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        stocks_data = json.load(f)

    stocks = []
    for item in stocks_data:
        code = item.get("code", "").strip().upper()
        if not code:
            continue
        stocks.append((code, item.get("name", code), item.get("sector", item.get("industry", ""))))
    return stocks


def format_price(price: float, currency: str = "USD") -> str:
    symbol = "$" if currency == "USD" else "¥"
    return f"{symbol}{price:.2f}"


def format_pct(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"
