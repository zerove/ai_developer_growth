#!/usr/bin/env python3
"""
Web Search API Server for AI Developer Growth
基于 Enhanced TF-IDF 的 Web 搜索 API
"""

import os
import sys

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 添加搜索模块路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "examples/ai-navigation/src"))

from enhanced_tfidf import Document, EnhancedTFIDF, create_enhanced_index


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


app = FastAPI(title="AI Developer Growth Search API", description="AI 时代开发者成长知识库搜索 API", version="1.0.0")

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


def load_documents():
    """从 docs 目录加载文档"""
    documents = []
    docs_dir = os.path.join(os.path.dirname(__file__), "docs")

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
                                    if tags_str.startswith("["):
                                        import ast

                                        tags = ast.literal_eval(tags_str)
                                    else:
                                        tags = [t.strip() for t in tags_str.split(",")]
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
    global search_index
    print("Loading documents...")
    documents = load_documents()
    print(f"Loaded {len(documents)} documents")
    search_index = create_enhanced_index(documents)
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
        query=q, total=len(formatted_results), results=formatted_results, time_ms=round((time.time() - start) * 1000, 2)
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
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
