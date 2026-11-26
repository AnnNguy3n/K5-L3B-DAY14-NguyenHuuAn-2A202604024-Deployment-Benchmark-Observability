"""
Cost guard (tiêu chí 8).

Yêu cầu:
  • Cộng dồn chi phí LLM (tính theo token) vào Redis
  • Tổng chi phí trong ngày UTC đạt DAILY_BUDGET_USD → HTTP 402
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException

from .config import settings
from .redis_client import r


# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = Decimal("0.00015")
PRICE_OUTPUT_PER_1K = Decimal("0.0006")


def _daily_key(now: datetime) -> str:
    return f"agent:cost:{now.date().isoformat()}"


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    key = _daily_key(datetime.now(UTC))
    spent = Decimal(r.get(key) or "0")
    if spent >= Decimal(str(settings.daily_budget_usd)):
        raise HTTPException(status_code=402, detail="Daily budget exhausted")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = (input_tokens * PRICE_INPUT_PER_1K + output_tokens * PRICE_OUTPUT_PER_1K) / 1000
    now = datetime.now(UTC)
    key = _daily_key(now)
    next_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    with r.pipeline() as pipe:
        pipe.incrbyfloat(key, str(cost))
        pipe.expireat(key, int(next_midnight.timestamp()))
        pipe.execute()

    return float(cost)
