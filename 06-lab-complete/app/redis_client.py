"""Kết nối Redis dùng chung cho readiness, rate limiter và cost guard."""

import redis
from redis.exceptions import RedisError

from .config import settings


# Client chỉ mở kết nối khi thực hiện lệnh đầu tiên.
r = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=1.0,
    socket_timeout=1.0,
)


def redis_healthy() -> bool:
    """Trả về trạng thái kết nối Redis cho endpoint readiness."""
    try:
        return bool(r.ping())
    except RedisError:
        return False
