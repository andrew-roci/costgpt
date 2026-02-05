"""Web dashboard routes."""

from datetime import date, timedelta
from uuid import UUID

import bcrypt
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from api.auth import generate_api_key
from db import get_db

router = APIRouter()
templates = Jinja2Templates(directory="templates")


async def get_current_user(request: Request) -> dict | None:
    user_id = request.cookies.get("session_user_id")
    if not user_id:
        return None
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        return None

    db = get_db()
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, email, name FROM customers WHERE id = $1",
            user_uuid,
        )
        return dict(row) if row else None


# --- Landing ---

@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    user = await get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("landing.html", {"request": request})


# --- Auth ---

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = await get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "user": None})


@router.post("/login")
async def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    db = get_db()
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, password_hash FROM customers WHERE email = $1",
            email.lower().strip(),
        )
        if not row or not row["password_hash"]:
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials", "user": None})

        if not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials", "user": None})

        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie("session_user_id", str(row["id"]), httponly=True, max_age=60*60*24*7)
        return response


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    user = await get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("signup.html", {"request": request, "user": None})


@router.post("/signup")
async def signup_submit(request: Request, name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    if len(password) < 8:
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Password must be at least 8 characters", "user": None})

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    db = get_db()
    async with db.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM customers WHERE email = $1", email.lower().strip())
        if existing:
            return templates.TemplateResponse("signup.html", {"request": request, "error": "Email already registered", "user": None})

        row = await conn.fetchrow(
            "INSERT INTO customers (email, name, password_hash) VALUES ($1, $2, $3) RETURNING id",
            email.lower().strip(),
            name.strip(),
            password_hash,
        )

        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie("session_user_id", str(row["id"]), httponly=True, max_age=60*60*24*7)
        return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session_user_id")
    return response


# --- Dashboard ---

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, days: int = 30):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    async with db.acquire() as conn:
        start_date = date.today() - timedelta(days=days)

        # Totals
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
            user["id"],
            start_date,
        )

        # Daily
        daily = await conn.fetch(
            """
            SELECT date, SUM(total_cost) as cost
            FROM daily_costs
            WHERE customer_id = $1 AND date >= $2
            GROUP BY date ORDER BY date
            """,
            user["id"],
            start_date,
        )

        # By model
        by_model = await conn.fetch(
            """
            SELECT model, SUM(total_cost) as cost, SUM(total_calls) as calls
            FROM daily_costs
            WHERE customer_id = $1 AND date >= $2
            GROUP BY model ORDER BY cost DESC LIMIT 10
            """,
            user["id"],
            start_date,
        )

        # By user
        by_user = await conn.fetch(
            """
            SELECT COALESCE(user_id, '(no user)') as user_id, SUM(total_cost) as cost
            FROM daily_costs
            WHERE customer_id = $1 AND date >= $2
            GROUP BY user_id ORDER BY cost DESC LIMIT 10
            """,
            user["id"],
            start_date,
        )

        # By feature
        by_feature = await conn.fetch(
            """
            SELECT COALESCE(feature, '(no feature)') as feature, SUM(total_cost) as cost
            FROM daily_costs
            WHERE customer_id = $1 AND date >= $2
            GROUP BY feature ORDER BY cost DESC LIMIT 10
            """,
            user["id"],
            start_date,
        )

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "days": days,
        "totals": {
            "cost": float(totals["total_cost"]),
            "calls": totals["total_calls"],
            "input_tokens": totals["input_tokens"],
            "output_tokens": totals["output_tokens"],
        },
        "daily": [{"date": str(r["date"]), "cost": float(r["cost"])} for r in daily],
        "by_model": [{"model": r["model"], "cost": float(r["cost"]), "calls": r["calls"]} for r in by_model],
        "by_user": [{"user_id": r["user_id"], "cost": float(r["cost"])} for r in by_user],
        "by_feature": [{"feature": r["feature"], "cost": float(r["cost"])} for r in by_feature],
    })


# --- API Keys ---

@router.get("/keys", response_class=HTMLResponse)
async def keys_page(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    async with db.acquire() as conn:
        keys = await conn.fetch(
            """
            SELECT id, name, key_prefix, created_at, last_used_at
            FROM api_keys WHERE customer_id = $1 AND revoked_at IS NULL
            ORDER BY created_at DESC
            """,
            user["id"],
        )

    return templates.TemplateResponse("keys.html", {
        "request": request,
        "user": user,
        "keys": [dict(k) for k in keys],
        "new_key": None,
    })


@router.post("/keys/create")
async def create_key(request: Request, name: str = Form(...)):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    full_key, key_prefix, key_hash = generate_api_key()

    db = get_db()
    async with db.acquire() as conn:
        await conn.execute(
            "INSERT INTO api_keys (customer_id, key_hash, key_prefix, name) VALUES ($1, $2, $3, $4)",
            user["id"],
            key_hash,
            key_prefix,
            name.strip(),
        )

        keys = await conn.fetch(
            """
            SELECT id, name, key_prefix, created_at, last_used_at
            FROM api_keys WHERE customer_id = $1 AND revoked_at IS NULL
            ORDER BY created_at DESC
            """,
            user["id"],
        )

    return templates.TemplateResponse("keys.html", {
        "request": request,
        "user": user,
        "keys": [dict(k) for k in keys],
        "new_key": full_key,
    })


@router.post("/keys/{key_id}/revoke")
async def revoke_key(request: Request, key_id: UUID):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    async with db.acquire() as conn:
        await conn.execute(
            "UPDATE api_keys SET revoked_at = now() WHERE id = $1 AND customer_id = $2",
            key_id,
            user["id"],
        )

    return RedirectResponse(url="/keys", status_code=302)
