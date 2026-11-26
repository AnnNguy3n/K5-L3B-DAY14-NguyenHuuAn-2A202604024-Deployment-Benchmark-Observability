"""
Rate limiting (tiêu chí 7).

Yêu cầu:
  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window)
  • Vượt giới hạn → HTTP 429, nên kèm header Retry-After
  • State lưu trong Redis để mọi worker / instance dùng chung và vẫn còn sau khi
    restart agent (script chấm sẽ restart agent để kiểm tra)
"""

from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException

from .config import settings
from .redis_client import r


WINDOW_SECONDS = 60

# Redis runs the check and insert atomically across workers and instances.
_check_window = r.register_script("""
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2]) * 1000
local request_id = ARGV[3]

if limit <= 0 then
    return tonumber(ARGV[2])
end

local now = redis.call('TIME')
local now_ms = tonumber(now[1]) * 1000 + math.floor(tonumber(now[2]) / 1000)
redis.call('ZREMRANGEBYSCORE', key, '-inf', now_ms - window_ms)

local count = redis.call('ZCARD', key)
if count >= limit then
    local rank = count - limit
    local next_slot = redis.call('ZRANGE', key, rank, rank, 'WITHSCORES')
    return math.ceil((tonumber(next_slot[2]) + window_ms - now_ms) / 1000)
end

redis.call('ZADD', key, now_ms, request_id)
redis.call('PEXPIRE', key, window_ms)
return 0
""")


def check_rate_limit(key: str) -> None:
    """Consume one request slot or return HTTP 429 if the window is full."""
    key_digest = sha256(key.encode("utf-8")).hexdigest()
    retry_after = _check_window(
        keys=[f"agent:rate_limit:{key_digest}"],
        args=[settings.rate_limit_per_minute, WINDOW_SECONDS, uuid4().hex],
    )
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
