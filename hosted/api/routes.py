"""API routes for CostGPT."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..db import get_db
from .auth import AuthContext, get_auth_context

router = APIRouter(prefix="/v1")


class EventRequest(BaseModel):
    id: UUID | None = None
    timestamp: datetime | None = None
    model: str
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    duration_ms: int | None = None
    user_id: str | None = None
    feature: str | None = None
    metadata: dict | None = None


class BatchEventsRequest(BaseModel):
    events: list[EventRequest]


@router.post("/events")
async def create_event(
    request: EventRequest,
    auth: AuthContext = Depends(get_auth_context),
):
    db = get_db()
    async with db.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (customer_id, model, input_tokens, output_tokens, input_cost, output_cost, total_cost, duration_ms, user_id, feature, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
            auth.customer_id,
            request.model,
            request.input_tokens,
            request.output_tokens,
            Decimal(str(request.input_cost)),
            Decimal(str(request.output_cost)),
            Decimal(str(request.total_cost)),
            request.duration_ms,
            request.user_id,
            request.feature,
            request.metadata or {},
        )

    return {"status": "ok"}


@router.post("/events/batch")
async def create_events_batch(
    request: BatchEventsRequest,
    auth: AuthContext = Depends(get_auth_context),
):
    db = get_db()
    async with db.acquire() as conn:
        for event in request.events:
            await conn.execute(
                """
                INSERT INTO events (customer_id, model, input_tokens, output_tokens, input_cost, output_cost, total_cost, duration_ms, user_id, feature, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                auth.customer_id,
                event.model,
                event.input_tokens,
                event.output_tokens,
                Decimal(str(event.input_cost)),
                Decimal(str(event.output_cost)),
                Decimal(str(event.total_cost)),
                event.duration_ms,
                event.user_id,
                event.feature,
                event.metadata or {},
            )

    return {"status": "ok", "count": len(request.events)}


@router.get("/costs/summary")
async def get_cost_summary(
    days: int = Query(30, ge=1, le=90),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get cost summary for the last N days."""
    db = get_db()
    async with db.acquire() as conn:
        start_date = date.today() - timedelta(days=days)

        # Total costs
        totals = await conn.fetchrow(
            """
            SELECT
                COALESCE(SUM(total_cost), 0) as total_cost,
                COALESCE(SUM(total_calls), 0) as total_calls,
                COALESCE(SUM(total_input_tokens), 0) as input_tokens,
                COALESCE(SUM(total_output_tokens), 0) as output_tokens
            FROM daily_costs
            WHERE customer_id = $1 AND date >= $2
            """,
            auth.customer_id,
            start_date,
        )

        # Daily breakdown
        daily = await conn.fetch(
            """
            SELECT date, SUM(total_cost) as cost, SUM(total_calls) as calls
            FROM daily_costs
            WHERE customer_id = $1 AND date >= $2
            GROUP BY date
            ORDER BY date
            """,
            auth.customer_id,
            start_date,
        )

        return {
            "period_days": days,
            "total_cost": float(totals["total_cost"]),
            "total_calls": totals["total_calls"],
            "total_input_tokens": totals["input_tokens"],
            "total_output_tokens": totals["output_tokens"],
            "daily": [
                {"date": str(row["date"]), "cost": float(row["cost"]), "calls": row["calls"]}
                for row in daily
            ],
        }


@router.get("/costs/by-model")
async def get_costs_by_model(
    days: int = Query(30, ge=1, le=90),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get costs grouped by model."""
    db = get_db()
    async with db.acquire() as conn:
        start_date = date.today() - timedelta(days=days)

        rows = await conn.fetch(
            """
            SELECT
                model,
                SUM(total_cost) as cost,
                SUM(total_calls) as calls,
                SUM(total_input_tokens) as input_tokens,
                SUM(total_output_tokens) as output_tokens
            FROM daily_costs
            WHERE customer_id = $1 AND date >= $2
            GROUP BY model
            ORDER BY cost DESC
            """,
            auth.customer_id,
            start_date,
        )

        return {
            "period_days": days,
            "models": [
                {
                    "model": row["model"],
                    "cost": float(row["cost"]),
                    "calls": row["calls"],
                    "input_tokens": row["input_tokens"],
                    "output_tokens": row["output_tokens"],
                }
                for row in rows
            ],
        }


@router.get("/costs/by-user")
async def get_costs_by_user(
    days: int = Query(30, ge=1, le=90),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get costs grouped by user_id."""
    db = get_db()
    async with db.acquire() as conn:
        start_date = date.today() - timedelta(days=days)

        rows = await conn.fetch(
            """
            SELECT
                COALESCE(user_id, '(no user)') as user_id,
                SUM(total_cost) as cost,
                SUM(total_calls) as calls
            FROM daily_costs
            WHERE customer_id = $1 AND date >= $2
            GROUP BY user_id
            ORDER BY cost DESC
            LIMIT 50
            """,
            auth.customer_id,
            start_date,
        )

        return {
            "period_days": days,
            "users": [
                {"user_id": row["user_id"], "cost": float(row["cost"]), "calls": row["calls"]}
                for row in rows
            ],
        }


@router.get("/costs/by-feature")
async def get_costs_by_feature(
    days: int = Query(30, ge=1, le=90),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get costs grouped by feature."""
    db = get_db()
    async with db.acquire() as conn:
        start_date = date.today() - timedelta(days=days)

        rows = await conn.fetch(
            """
            SELECT
                COALESCE(feature, '(no feature)') as feature,
                SUM(total_cost) as cost,
                SUM(total_calls) as calls
            FROM daily_costs
            WHERE customer_id = $1 AND date >= $2
            GROUP BY feature
            ORDER BY cost DESC
            LIMIT 50
            """,
            auth.customer_id,
            start_date,
        )

        return {
            "period_days": days,
            "features": [
                {"feature": row["feature"], "cost": float(row["cost"]), "calls": row["calls"]}
                for row in rows
            ],
        }
