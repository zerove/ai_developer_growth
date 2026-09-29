"""
AI Navigation - Knowledge Index Builder

Builds a searchable index from knowledge base documents and case studies.
Supports both JSON-based local index and vector embeddings for RAG.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Document:
    """Represents a knowledge document."""

    id: str
    type: str  # methodology, case_study, tool, adr
    category: str
    title: str
    content: str
    metadata: dict = field(default_factory=dict)
    embedding: list[float] | None = None


@dataclass
class KnowledgeIndex:
    """Knowledge index for RAG queries."""

    documents: list[Document] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def add_document(self, doc: Document) -> None:
        """Add a document to the index."""
        self.documents.append(doc)

    def get_document(self, doc_id: str) -> Document | None:
        """Get a document by ID."""
        for doc in self.documents:
            if doc.id == doc_id:
                return doc
        return None

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Simple keyword-based search.
        For production, replace with vector similarity search.
        """
        query_lower = query.lower()
        results = []

        # For Chinese text, also extract individual characters as search terms
        # This helps with partial matching
        query_chars = set(query_lower) - set("？！。，、；：''（）【】")

        for doc in self.documents:
            # Simple scoring based on keyword matches
            score = 0
            title_lower = doc.title.lower()
            content_lower = doc.content.lower()

            # Title match (higher weight)
            if query_lower in title_lower:
                score += 10

            # Content match - full query
            if query_lower in content_lower:
                score += 5

            # Content match - individual words (space-separated)
            query_words = query_lower.split()
            for word in query_words:
                if len(word) >= 2:  # Only match words with 2+ chars
                    if word in content_lower:
                        score += 1
                    if word in title_lower:
                        score += 2

            # Content match - individual characters (for Chinese)
            for char in query_chars:
                if char.isalpha():  # Only match alphabetic characters
                    if char in content_lower:
                        score += 0.5
                    if char in title_lower:
                        score += 1

            if score > 0:
                results.append(
                    {
                        "doc": doc,
                        "score": score,
                        "snippet": self._get_snippet(doc.content, list(query_chars)),
                    }
                )

        # Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _get_snippet(
        self, content: str, query_words: list[str], context_len: int = 100
    ) -> str:
        """Get a relevant snippet from content."""
        content_lower = content.lower()

        # Find first occurrence of any query word
        for word in query_words:
            idx = content_lower.find(word)
            if idx >= 0:
                start = max(0, idx - context_len)
                end = min(len(content), idx + context_len)
                snippet = content[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."
                return snippet

        # Fallback: return first 200 chars
        return content[:200] + "..." if len(content) > 200 else content

    def save(self, path: str) -> None:
        """Save index to JSON file."""
        data = {
            "metadata": self.metadata,
            "documents": [asdict(doc) for doc in self.documents],
        }
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2))

    @classmethod
    def load(cls, path: str) -> "KnowledgeIndex":
        """Load index from JSON file."""
        data = json.loads(Path(path).read_text())
        index = cls(metadata=data.get("metadata", {}))
        for doc_data in data.get("documents", []):
            doc = Document(**doc_data)
            index.add_document(doc)
        return index


class IndexBuilder:
    """Builds knowledge index from files."""

    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root)

    def build(self) -> KnowledgeIndex:
        """Build complete knowledge index."""
        index = KnowledgeIndex(
            metadata={
                "version": "1.0",
                "repo_root": str(self.repo_root),
                "description": "AI Developer Growth Knowledge Index",
            }
        )

        # Index docs
        self._index_methodology(index)

        # Index case studies
        self._index_case_studies(index)

        # Index ADRs
        self._index_adrs(index)

        return index

    def _index_methodology(self, index: KnowledgeIndex) -> None:
        """Index methodology documents."""
        docs_dir = self.repo_root / "docs"
        if not docs_dir.exists():
            return

        for md_file in docs_dir.rglob("*.md"):
            if md_file.name in ("README.md", "INDEX.md", "MOC.md"):
                continue

            try:
                content = md_file.read_text(encoding="utf-8")
                rel_path = md_file.relative_to(docs_dir)
                category = (
                    rel_path.parent.name if rel_path.parent != Path(".") else "root"
                )

                # Extract title from first heading
                title = self._extract_title(content, md_file.stem)

                doc = Document(
                    id=f"methodology-{md_file.stem}",
                    type="methodology",
                    category=category,
                    title=title,
                    content=content,
                    metadata={
                        "path": str(rel_path),
                        "reading_time": self._estimate_reading_time(content),
                        "difficulty": self._estimate_difficulty(content),
                    },
                )
                index.add_document(doc)
            except Exception as e:
                print(f"Warning: Failed to index {md_file}: {e}")

    def _index_case_studies(self, index: KnowledgeIndex) -> None:
        """Index case study documents."""
        cases_dir = self.repo_root / "docs" / "case-studies"
        if not cases_dir.exists():
            return

        for md_file in cases_dir.glob("*.md"):
            if md_file.name in ("README.md", "INDEX.md"):
                continue

            try:
                content = md_file.read_text(encoding="utf-8")

                # Extract metadata from content
                project_type = self._extract_field(content, "项目类型") or "unknown"
                tools_used = self._extract_field(content, "AI 工具栈") or ""
                efficiency = self._extract_field(content, "效率提升") or "unknown"

                doc = Document(
                    id=f"case-{md_file.stem}",
                    type="case_study",
                    category=project_type.lower().replace(" ", "_"),
                    title=self._extract_title(content, md_file.stem),
                    content=content,
                    metadata={
                        "project_type": project_type,
                        "tools_used": [
                            t.strip() for t in tools_used.split(",") if t.strip()
                        ],
                        "efficiency_gain": efficiency,
                        "path": md_file.name,
                    },
                )
                index.add_document(doc)
            except Exception as e:
                print(f"Warning: Failed to index {md_file}: {e}")

    def _index_adrs(self, index: KnowledgeIndex) -> None:
        """Index Architecture Decision Records."""
        adr_dir = self.repo_root / "docs" / "adr"
        if not adr_dir.exists():
            return

        for md_file in adr_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")

                # Extract status
                status = "unknown"
                for line in content.split("\n"):
                    if line.startswith("## 状态"):
                        # Get next non-empty line
                        idx = content.find(line) + len(line)
                        remaining = content[idx:].strip()
                        first_line = remaining.split("\n")[0].strip()
                        status = first_line
                        break

                doc = Document(
                    id=f"adr-{md_file.stem}",
                    type="adr",
                    category="architecture",
                    title=self._extract_title(content, md_file.stem),
                    content=content,
                    metadata={"status": status, "path": md_file.name},
                )
                index.add_document(doc)
            except Exception as e:
                print(f"Warning: Failed to index {md_file}: {e}")

    def _extract_title(self, content: str, fallback: str) -> str:
        """Extract title from markdown content."""
        for line in content.split("\n"):
            if line.startswith("# "):
                return line[2:].strip()
        return fallback

    def _extract_field(self, content: str, field_name: str) -> str | None:
        """Extract a field value from content."""
        for line in content.split("\n"):
            if field_name in line and ":" in line:
                _, value = line.split(":", 1)
                return value.strip()
        return None

    def _estimate_reading_time(self, content: str) -> str:
        """Estimate reading time in minutes."""
        words = len(content.split())
        minutes = max(1, words // 200)
        return f"{minutes}min"

    def _estimate_difficulty(self, content: str) -> str:
        """Estimate content difficulty."""
        word_count = len(content.split())
        if word_count < 500:
            return "beginner"
        elif word_count < 1500:
            return "intermediate"
        else:
            return "advanced"


def build_index(repo_root: str, output_path: str) -> KnowledgeIndex:
    """Build and save knowledge index."""
    builder = IndexBuilder(repo_root)
    index = builder.build()
    index.save(output_path)
    print(f"✅ Index built: {len(index.documents)} documents")
    print(
        f"   - Methodology: {sum(1 for d in index.documents if d.type == 'methodology')}"
    )
    print(
        f"   - Case Studies: {sum(1 for d in index.documents if d.type == 'case_study')}"
    )
    print(f"   - ADRs: {sum(1 for d in index.documents if d.type == 'adr')}")
    return index


if __name__ == "__main__":
    import sys

    repo_root = sys.argv[1] if len(sys.argv) > 1 else "."
    output = sys.argv[2] if len(sys.argv) > 2 else "knowledge_index.json"

    build_index(repo_root, output)
