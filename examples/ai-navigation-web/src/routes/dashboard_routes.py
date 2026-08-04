from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from ..database import get_db
from ..auth import get_current_user_id

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/dashboard")
async def dashboard(request: Request):
    user_id = get_current_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    db = await get_db()
    try:
        user = await db.execute("SELECT username FROM users WHERE id = ?", (user_id,))
        user_row = await user.fetchone()
        if not user_row:
            return RedirectResponse(url="/auth/login", status_code=303)

        # Get latest assessment
        assessment = await db.execute(
            "SELECT * FROM assessments WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,)
        )
        assessment_row = await assessment.fetchone()

        # Get progress stats
        progress = await db.execute(
            "SELECT status, COUNT(*) as cnt FROM learning_progress WHERE user_id = ? GROUP BY status",
            (user_id,),
        )
        progress_rows = await progress.fetchall()
        progress_stats = {row["status"]: row["cnt"] for row in progress_rows}

        # Get recent progress
        recent = await db.execute(
            "SELECT * FROM learning_progress WHERE user_id = ? ORDER BY completed_at DESC LIMIT 5",
            (user_id,),
        )
        recent_items = await recent.fetchall()

        # Get contributions count
        contrib = await db.execute("SELECT COUNT(*) as cnt FROM contributions WHERE user_id = ?", (user_id,))
        contrib_row = await contrib.fetchone()

        return templates.TemplateResponse(
            request,
            "dashboard.html",
            context={
                "request": request,
                "username": user_row["username"],
                "assessment": dict(assessment_row) if assessment_row else None,
                "progress_stats": progress_stats,
                "recent_items": [dict(r) for r in recent_items],
                "contrib_count": contrib_row["cnt"] if contrib_row else 0,
            },
        )
    finally:
        await db.close()


@router.get("/")
async def home(request: Request):
    user_id = get_current_user_id(request)
    if user_id:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request, "home.html")
