from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from ..database import get_db
from ..auth import hash_password, verify_password, create_access_token, set_auth_cookie

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/register")
async def register_form(request: Request):
    return templates.TemplateResponse(request, "auth/register.html")


@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    db = await get_db()
    try:
        existing = await db.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?", (username, email)
        )
        if await existing.fetchone():
            return templates.TemplateResponse(
                request,
                "auth/register.html",
                context={
                    "request": request,
                    "error": "Username or email already exists",
                },
                status_code=400,
            )
        hashed = hash_password(password)
        cursor = await db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, hashed),
        )
        await db.commit()
        user_id = cursor.lastrowid
        token = create_access_token({"user_id": user_id, "username": username})
        response = RedirectResponse(url="/dashboard", status_code=303)
        set_auth_cookie(response, token)
        return response
    finally:
        await db.close()


@router.get("/login")
async def login_form(request: Request):
    return templates.TemplateResponse(request, "auth/login.html")


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    db = await get_db()
    try:
        row = await db.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        )
        user = await row.fetchone()
        if not user or not verify_password(password, user["password_hash"]):
            return templates.TemplateResponse(
                request,
                "auth/login.html",
                context={"request": request, "error": "Invalid credentials"},
                status_code=400,
            )
        token = create_access_token(
            {"user_id": user["id"], "username": user["username"]}
        )
        response = RedirectResponse(url="/dashboard", status_code=303)
        set_auth_cookie(response, token)
        return response
    finally:
        await db.close()


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("access_token")
    return response
