from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from ..database import get_db
from ..auth import get_current_user_id

router = APIRouter(prefix="/assess", tags=["assessment"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

# Skill dimensions mapping to docs
SKILL_DOCS = {
    "ai_comprehension": [
        "mindset/ai-native-thinking.md",
        "mindset/capability-model.md",
        "mindset/problem-decomposition.md",
        "mindset/systems-thinking.md",
    ],
    "engineering_integration": [
        "tools/ai-coding-assistants.md",
        "tools/local-llm-setup.md",
        "tools/ai-search-engines.md",
        "tools/prompt-engineering.md",
    ],
    "learning_method": [
        "efficiency/knowledge-qa-system.md",
        "efficiency/full-cycle-workflow.md",
        "efficiency/personalized-search.md",
    ],
    "innovation_thinking": [
        "mindset/resource-integration.md",
        "mindset/leverage-thinking.md",
        "mindset/three-layer-model.md",
    ],
    "output_quality": [
        "efficiency/quality-comparison.md",
        "efficiency/metrics-framework.md",
        "efficiency/cost-optimization.md",
    ],
}

LEVEL_THRESHOLDS = {
    0.2: "L0 - 初学者",
    0.4: "L1 - 进阶",
    0.6: "L2 - 胜任",
    0.8: "L3 - 精通",
    1.0: "L4 - 专家",
}


def get_level(score: float) -> str:
    for threshold, level in sorted(LEVEL_THRESHOLDS.items()):
        if score <= threshold:
            return level
    return "L4 - 专家"


@router.get("")
async def assessment_form(request: Request):
    user_id = get_current_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    db = await get_db()
    try:
        prev = await db.execute(
            "SELECT * FROM assessments WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        )
        prev_row = await prev.fetchone()
        return templates.TemplateResponse(
            request,
            "assess/assessment.html",
            context={
                "request": request,
                "prev": dict(prev_row) if prev_row else None,
                "skill_docs": SKILL_DOCS,
            },
        )
    finally:
        await db.close()


@router.post("")
async def submit_assessment(
    request: Request,
    ai_comprehension: float = Form(0),
    engineering_integration: float = Form(0),
    learning_method: float = Form(0),
    innovation_thinking: float = Form(0),
    output_quality: float = Form(0),
):
    user_id = get_current_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    scores = {
        "ai_comprehension": ai_comprehension,
        "engineering_integration": engineering_integration,
        "learning_method": learning_method,
        "innovation_thinking": innovation_thinking,
        "output_quality": output_quality,
    }
    overall = sum(scores.values()) / len(scores)

    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO assessments (user_id, ai_comprehension, engineering_integration, learning_method, innovation_thinking, output_quality, overall) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, *scores.values(), overall),
        )
        await db.commit()

        # Build recommendations
        weak_dims = sorted(scores.items(), key=lambda x: x[1])[:2]
        recommendations = []
        for dim, score in weak_dims:
            docs = SKILL_DOCS.get(dim, [])
            dim_name = {
                "ai_comprehension": "AI 理解力",
                "engineering_integration": "工程整合",
                "learning_method": "学习方法",
                "innovation_thinking": "创新思维",
                "output_quality": "输出质量",
            }.get(dim, dim)
            recommendations.append(
                {"dimension": dim_name, "score": score, "docs": docs}
            )

        return templates.TemplateResponse(
            request,
            "assess/result.html",
            context={
                "request": request,
                "scores": scores,
                "overall": overall,
                "level": get_level(overall),
                "recommendations": recommendations,
            },
        )
    finally:
        await db.close()


@router.get("/history")
async def assessment_history(request: Request):
    user_id = get_current_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    db = await get_db()
    try:
        rows = await db.execute(
            "SELECT * FROM assessments WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
            (user_id,),
        )
        items = await rows.fetchall()
        return templates.TemplateResponse(
            request,
            "assess/history.html",
            context={"request": request, "assessments": [dict(r) for r in items]},
        )
    finally:
        await db.close()
