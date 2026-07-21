from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from ..database import get_db
from ..auth import get_current_user_id

router = APIRouter(prefix="/contribute", tags=["contribution"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("")
async def contribute_list(request: Request):
    user_id = get_current_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    db = await get_db()
    try:
        rows = await db.execute(
            "SELECT * FROM contributions WHERE user_id = ? ORDER BY submitted_at DESC",
            (user_id,),
        )
        items = await rows.fetchall()
        return templates.TemplateResponse(request, "contribute/list.html", context={"request": request, "contributions": [dict(r) for r in items]},
        )
    finally:
        await db.close()


@router.get("/new")
async def new_contribution(request: Request):
    user_id = get_current_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse(request, "contribute/form.html")


@router.post("")
async def submit_contribution(
    request: Request,
    doc_path: str = Form(...),
    doc_title: str = Form(...),
    content: str = Form(...),
):
    user_id = get_current_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO contributions (user_id, doc_path, doc_title, content, status) VALUES (?, ?, ?, ?, 'submitted')",
            (user_id, doc_path, doc_title, content),
        )
        await db.commit()
        return RedirectResponse(url="/contribute", status_code=303)
    finally:
        await db.close()


@router.get("/{contrib_id}")
async def view_contribution(request: Request, contrib_id: int):
    user_id = get_current_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    db = await get_db()
    try:
        row = await db.execute(
            "SELECT * FROM contributions WHERE id = ? AND user_id = ?",
            (contrib_id, user_id),
        )
        item = await row.fetchone()
        if not item:
            return RedirectResponse(url="/contribute", status_code=303)
        return templates.TemplateResponse(request, "contribute/detail.html", context={"request": request, "contribution": dict(item)},
        )
    finally:
        await db.close()
