"""
MkDocs 搜索插件 - 集成 Enhanced TF-IDF 搜索
"""

import json
import os
import sys

from mkdocs.config import config_options
from mkdocs.plugins import BasePlugin


class EnhancedSearchPlugin(BasePlugin):
    """增强搜索插件"""

    config_scheme = (
        ("enabled", config_options.Type(bool, default=True)),
        ("index_path", config_options.Type(str, default="search_index.json")),
    )

    def on_config(self, config):
        """配置阶段"""
        if not self.config["enabled"]:
            return config

        # 添加自定义搜索 JS
        if "extra_javascript" not in config:
            config["extra_javascript"] = []

        config["extra_javascript"].append("js/enhanced-search.js")

        return config

    def on_post_build(self, config):
        """构建完成后生成搜索索引"""
        if not self.config["enabled"]:
            return

        print("Generating enhanced search index...")

        # 这里可以生成供前端使用的索引
        # 由于 MkDocs 自带 lunr.js 搜索，我们可以扩展它
        pass


# 如果直接运行，生成独立搜索索引
if __name__ == "__main__":
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "examples/ai-navigation/src"))

    import json

    from enhanced_tfidf import Document, create_enhanced_index

    docs = []
    docs_dir = "docs"

    for root, dirs, files in os.walk(docs_dir):
        for f in files:
            if f.endswith(".md"):
                path = os.path.join(root, f)
                try:
                    with open(path, encoding="utf-8") as fp:
                        content = fp.read()

                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            frontmatter = parts[1]
                            body = parts[2]

                            import ast

                            title = f.replace(".md", "").replace("-", " ").title()
                            tags = []
                            category = "未分类"
                            difficulty = "初级"

                            for line in frontmatter.split("\n"):
                                if line.startswith("title:"):
                                    title = line.split(":", 1)[1].strip().strip("\"'")
                                elif line.startswith("tags:"):
                                    tags_str = line.split(":", 1)[1].strip()
                                    if tags_str.startswith("["):
                                        tags = ast.literal_eval(tags_str)
                                    else:
                                        tags = [t.strip() for t in tags_str.split(",")]
                                elif line.startswith("category:"):
                                    category = line.split(":", 1)[1].strip().strip("\"'")
                                elif line.startswith("difficulty:"):
                                    difficulty = line.split(":", 1)[1].strip().strip("\"'")

                            doc = Document(
                                id=path.replace(".md", "").replace("/", "_").replace(docs_dir + "_", ""),
                                title=title,
                                content=body[:3000],
                                doc_type="doc",
                                tags=tags,
                                category=category,
                                difficulty=difficulty,
                            )
                            docs.append(doc)
                except Exception:
                    # 跳过无法解析的单篇文档，不影响整体索引构建
                    pass

    print(f"Loaded {len(docs)} documents")

    index = create_enhanced_index(docs)

    # 导出简化索引供前端使用
    export_data = {
        "documents": [],
        "doc_freqs": index.doc_freqs,
        "avg_doc_length": index.avg_doc_length,
    }

    for doc in index.documents.values():
        export_data["documents"].append(
            {
                "id": doc.id,
                "title": doc.title,
                "category": doc.category,
                "tags": doc.tags,
                "difficulty": doc.difficulty,
            }
        )

    output_path = os.path.join("site", "search_index_enhanced.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False)

    print(f"Index saved to {output_path}")
