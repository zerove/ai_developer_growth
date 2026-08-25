#!/usr/bin/env python3
"""
Web Search API Server for AI Developer Growth
基于 Enhanced TF-IDF 的 Web 搜索 API
"""

import os
import sys
import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 确保项目根目录在导入路径上（支持从任意工作目录启动）
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from tools.scripts.search.tfidf_engine import (  # noqa: E402 -- 需先注入项目根路径
    Document,
    EnhancedTFIDF,
    create_enhanced_index,
)


class SearchResponse(BaseModel):
    """搜索响应模型"""

    query: str
    total: int
    results: list[dict]
    time_ms: float


class SearchSuggestion(BaseModel):
    """搜索建议"""

    term: str
    count: int


app = FastAPI(
    title="AI Developer Growth Search API",
    description="AI 时代开发者成长知识库搜索 API",
    version="1.0.0",
)


@app.middleware("http")
async def observe_requests(request, call_next):
    """轻量可观测性：慢请求（>500ms）打警告日志，含耗时与路径。"""
    start = time.time()
    response = await call_next(request)
    elapsed_ms = (time.time() - start) * 1000
    if elapsed_ms > 500:
        print(f"SLOW {request.method} {request.url.path} {elapsed_ms:.0f}ms", flush=True)
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
    return response


# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局索引
search_index: EnhancedTFIDF | None = None
# 索引元数据（构建时间/耗时），供 /api/health 观测
index_meta: dict = {"built_at": None, "build_ms": None}


def build_index() -> tuple[EnhancedTFIDF, dict]:
    """构建索引并返回（索引，元数据）。供启动与热重载复用。"""
    start = time.time()
    documents = load_documents()
    index = create_enhanced_index(documents)
    meta = {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "build_ms": round((time.time() - start) * 1000, 2),
        "document_count": len(documents),
    }
    return index, meta


def load_documents():
    """从 docs 目录加载文档"""
    documents = []
    docs_dir = _ROOT and os.path.join(_ROOT, "docs")

    for root, dirs, files in os.walk(docs_dir):
        for file in files:
            if file.endswith(".md"):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, encoding="utf-8") as f:
                        content = f.read()

                    # 解析 frontmatter
                    title = file.replace(".md", "").replace("-", " ").title()
                    category = ""
                    tags = []
                    difficulty = "初级"

                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            frontmatter = parts[1]
                            for line in frontmatter.strip().split("\n"):
                                if line.startswith("title:"):
                                    title = line.split(":", 1)[1].strip().strip("\"'")
                                elif line.startswith("category:"):
                                    category = line.split(":", 1)[1].strip().strip("\"'")
                                elif line.startswith("tags:"):
                                    tags_str = line.split(":", 1)[1].strip()
                                    if tags_str.startswith("[") and tags_str.endswith("]"):
                                        # YAML 内联数组: [A, B, C] -> 逐项去引号
                                        inner = tags_str[1:-1]
                                        tags = [t.strip().strip("\"'") for t in inner.split(",") if t.strip()]
                                    else:
                                        tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                                elif line.startswith("difficulty:"):
                                    difficulty = line.split(":", 1)[1].strip().strip("\"'")

                    # 移除 frontmatter 获取正文
                    if content.startswith("---"):
                        content = content.split("---", 2)[2] if len(content.split("---", 2)) >= 3 else content

                    rel_path = os.path.relpath(filepath, docs_dir)
                    doc_id = rel_path.replace(".md", "").replace("/", "_")

                    doc = Document(
                        id=doc_id,
                        title=title,
                        content=content[:5000],  # 限制内容长度
                        doc_type="doc",
                        tags=tags,
                        category=category,
                        difficulty=difficulty,
                    )
                    documents.append(doc)
                except Exception as e:
                    print(f"Error loading {filepath}: {e}")

    return documents


@app.on_event("startup")
async def startup_event():
    """启动时初始化搜索索引"""
    global search_index, index_meta
    print("Loading documents...")
    search_index, index_meta = build_index()
    print(f"Index stats: {search_index.get_stats()}")


@app.get("/api/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., description="搜索查询", min_length=1, max_length=200),
    limit: int = Query(10, description="返回结果数", ge=1, le=50),
    category: str | None = Query(None, description="分类过滤"),
):
    """执行搜索"""
    import time

    start = time.time()

    if not search_index:
        raise HTTPException(status_code=503, detail="Search index not ready")

    results = search_index.search(q, top_k=limit)

    # 分类过滤
    if category:
        results = [r for r in results if r.doc.category == category]

    formatted_results = []
    for r in results:
        formatted_results.append(
            {
                "id": r.doc.id,
                "title": r.doc.title,
                "snippet": r.snippet,
                "score": round(r.score, 4),
                "category": r.doc.category,
                "tags": r.doc.tags,
                "difficulty": r.doc.difficulty,
                "url": f"/{r.doc.id.replace('_', '/')}.html",
            }
        )

    return SearchResponse(
        query=q,
        total=len(formatted_results),
        results=formatted_results,
        time_ms=round((time.time() - start) * 1000, 2),
    )


@app.get("/api/suggestions", response_model=list[SearchSuggestion])
async def suggestions(
    q: str = Query(..., description="部分查询", min_length=1, max_length=50),
    limit: int = Query(5, description="建议数量", ge=1, le=20),
):
    """获取搜索建议"""
    if not search_index:
        raise HTTPException(status_code=503, detail="Search index not ready")

    suggestions = search_index.suggest(q, top_k=limit)
    return [{"term": s, "count": 1} for s in suggestions]


@app.get("/api/stats")
async def stats():
    """获取索引统计"""
    if not search_index:
        raise HTTPException(status_code=503, detail="Search index not ready")
    return search_index.get_stats()


@app.get("/api/categories")
async def categories():
    """获取所有分类"""
    if not search_index:
        raise HTTPException(status_code=503, detail="Search index not ready")

    cats = set()
    for doc in search_index.documents.values():
        if doc.category:
            cats.add(doc.category)
    return sorted(list(cats))


@app.get("/api/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "index_ready": search_index is not None,
        "document_count": len(search_index.documents) if search_index else 0,
        "index_built_at": index_meta.get("built_at"),
        "index_build_ms": index_meta.get("build_ms"),
    }


@app.post("/api/reload")
async def reload_index():
    """热重载：docs 内容变更后重建索引，无需重启服务。

    构建失败时保留旧索引继续服务（fail-safe）。
    """
    global search_index, index_meta
    try:
        new_index, new_meta = build_index()
    except Exception as e:  # pragma: no cover - 防御性分支
        raise HTTPException(status_code=500, detail=f"reload failed, old index kept: {e}") from e
    old_count = len(search_index.documents) if search_index else 0
    search_index, index_meta = new_index, new_meta
    return {
        "status": "reloaded",
        "old_document_count": old_count,
        "document_count": new_meta["document_count"],
        "build_ms": new_meta["build_ms"],
        "built_at": new_meta["built_at"],
    }


if __name__ == "__main__":
    import uvicorn

    # 安全默认仅绑本机回环；需局域网访问时显式设置 SEARCH_HOST 环境变量并自行加鉴权
    host = os.environ.get("SEARCH_HOST", "127.0.0.1")
    port = int(os.environ.get("SEARCH_PORT", "8001"))
    uvicorn.run(app, host=host, port=port)
