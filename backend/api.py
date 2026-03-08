from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from aiohttp import web

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data" / "OpenPeru.db"


def dict_factory(cursor: sqlite3.Cursor, row: sqlite3.Row) -> Dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    return conn


@web.middleware
async def cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        response = web.Response(status=204)
    else:
        response = await handler(request)

    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


async def health(_: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def list_congresistas(request: web.Request) -> web.Response:
    query = request.query.get("q", "").strip()
    sql = "SELECT id, nombre FROM congresistas"
    params: List[Any] = []
    if query:
        sql += " WHERE nombre LIKE ?"
        params.append(f"%{query}%")
    sql += " ORDER BY nombre"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    return web.json_response(rows)


async def congresista_detail(request: web.Request) -> web.Response:
    person_id = request.match_info["person_id"]
    sql = """
        SELECT id, nombre, party_name, current_bancada, dist_electoral,
               votes_in_election, photo_url
        FROM congresistas
        WHERE id = ?
    """

    with get_connection() as conn:
        row = conn.execute(sql, (person_id,)).fetchone()

    if row is None:
        raise web.HTTPNotFound(text="Congressman not found")

    return web.json_response(row)


async def congresista_bills(request: web.Request) -> web.Response:
    person_id = request.match_info["person_id"]
    role = request.query.get("role")

    sql = """
        SELECT bc.bill_id, bc.role_type, b.title, b.presentation_date, b.status
        FROM bills_congresistas bc
        JOIN bills b ON b.id = bc.bill_id
        WHERE bc.person_id = ?
    """
    params: List[Any] = [person_id]

    if role:
        sql += " AND bc.role_type = ?"
        params.append(role)

    sql += " ORDER BY b.presentation_date IS NULL, b.presentation_date DESC"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    return web.json_response(rows)


async def list_leyes(_: web.Request) -> web.Response:
    sql = "SELECT id, title, bill_id FROM leyes ORDER BY id DESC"
    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()
    return web.json_response(rows)


async def bill_steps(request: web.Request) -> web.Response:
    bill_id = request.match_info["bill_id"]
    sql = """
        SELECT step_type, step_date, step_detail
        FROM bill_steps
        WHERE bill_id = ?
        ORDER BY step_date IS NULL, step_date ASC, id ASC
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (bill_id,)).fetchall()
    return web.json_response(rows)


def create_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/api/health", health)
    app.router.add_get("/api/congresistas", list_congresistas)
    app.router.add_get("/api/congresistas/{person_id}", congresista_detail)
    app.router.add_get("/api/congresistas/{person_id}/bills", congresista_bills)
    app.router.add_get("/api/leyes", list_leyes)
    app.router.add_get("/api/bills/{bill_id}/steps", bill_steps)
    app.router.add_options("/api/{tail:.*}", health)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=8000)
