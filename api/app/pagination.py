"""Shared pagination params for list endpoints (perf/scalability: P-H2).

Used as a FastAPI dependency (`page: PageParams = Depends()`), it exposes `?limit=&offset=`
with a SAFE DEFAULT and HARD CAP so no collection endpoint can ever load unbounded data,
even when a caller omits the params.
"""

from __future__ import annotations

from fastapi import Query

DEFAULT_LIMIT = 200
MAX_LIMIT = 500


class PageParams:
    def __init__(
        self,
        limit: int = Query(
            DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max rows to return (bounded)."
        ),
        offset: int = Query(0, ge=0, description="Rows to skip (pagination)."),
    ) -> None:
        self.limit = limit
        self.offset = offset
