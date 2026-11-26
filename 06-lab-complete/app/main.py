"""API của production agent cho Part 6."""

import json
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from time import perf_counter
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from redis.exceptions import RedisError
from starlette.concurrency import run_in_threadpool

from utils.mock_llm import ask as llm_ask

from .auth import verify_api_key
from .cost_guard import check_budget, record_cost
from .rate_limiter import check_rate_limit
from .redis_client import r, redis_healthy


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "lvl": record.levelname,
            "event": record.getMessage(),
            **getattr(record, "fields", {}),
        })


logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        yield
    finally:
        await run_in_threadpool(r.close)


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def log_request(request: Request, call_next):
    started = perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    logger.info("request", extra={"fields": {
        "path": getattr(route, "path", "unmatched"),
        "status": response.status_code,
        "ms": round((perf_counter() - started) * 1000, 2),
    }})
    return response


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"status": "ready"}


@app.post("/ask")
def ask(body: AskRequest, api_key: Annotated[str, Depends(verify_api_key)]):
    try:
        check_rate_limit(api_key)
        check_budget()
        answer = llm_ask(body.question)

        # Mock LLM chỉ trả văn bản. Ước lượng hai token mỗi từ như Part 4.
        record_cost(len(body.question.split()) * 2, len(answer.split()) * 2)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Redis unavailable") from exc
    return {"question": body.question, "answer": answer}
