from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime

from ..database import get_db
from ..auth import get_current_user_id

router = APIRouter(prefix="/progress", tags=["progress"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("")
async def progress_list(request: Request):
    user_id = get_current_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    db = await get_db()
    try:
        rows = await db.execute(
            "SELECT * FROM learning_progress WHERE user_id = ? ORDER BY CASE status WHEN 'in_progress' THEN 1 WHEN 'pending' THEN 2 WHEN 'completed' THEN 3 END, completed_at DESC",
            (user_id,),
        )
        items = await rows.fetchall()
        return templates.TemplateResponse(
            request,
            "progress/list.html",
            context={"request": request, "items": [dict(r) for r in items]},
        )
    finally:
        await db.close()


@router.post("/start")
async def start_learning(
    request: Request,
    doc_path: str = Form(...),
    doc_title: str = Form(...),
):
    user_id = get_current_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    db = await get_db()
    try:
        existing = await db.execute(
            "SELECT id FROM learning_progress WHERE user_id = ? AND doc_path = ?",
            (user_id, doc_path),
        )
        if not await existing.fetchone():
            await db.execute(
                "INSERT INTO learning_progress (user_id, doc_path, doc_title, status, started_at) VALUES (?, ?, ?, 'in_progress', ?)",
                (user_id, doc_path, doc_title, datetime.now().isoformat()),
            )
            await db.commit()
        return RedirectResponse(url="/progress", status_code=303)
    finally:
        await db.close()


@router.post("/{progress_id}/complete")
async def complete_learning(request: Request, progress_id: int, notes: str = Form("")):
    user_id = get_current_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    db = await get_db()
    try:
        await db.execute(
            "UPDATE learning_progress SET status = 'completed', completed_at = ?, notes = ? WHERE id = ? AND user_id = ?",
            (datetime.now().isoformat(), notes, progress_id, user_id),
        )
        await db.commit()
        return RedirectResponse(url="/progress", status_code=303)
    finally:
        await db.close()


@router.post("/{progress_id}/delete")
async def delete_progress(request: Request, progress_id: int):
    user_id = get_current_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    db = await get_db()
    try:
        await db.execute("DELETE FROM learning_progress WHERE id = ? AND user_id = ?", (progress_id, user_id))
        await db.commit()
        return RedirectResponse(url="/progress", status_code=303)
    finally:
        await db.close()
