"""
Semantic search for ADR documents using TF-IDF-like scoring.

Provides vector similarity search without external dependencies.
"""
import math
import os
import re
from collections import Counter
from typing import Dict, List, Tuple


def tokenize(text: str) -> List[str]:
    text_lower = text.lower()
    tokens = re.findall(r'\b\w+\b', text_lower)
    stopwords = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'shall', 'can', 'need', 'dare', 'ought',
        'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
        'as', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
        'between', 'out', 'off', 'over', 'under', 'again', 'further', 'then',
        'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each',
        'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
        'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
        'just', 'because', 'but', 'and', 'or', 'if', 'while', 'that', 'this',
        'these', 'those', 'it', 'its', 'we', 'they', 'them', 'he', 'she',
    }
    return [t for t in tokens if t not in stopwords and len(t) > 2]


def compute_tf(tokens: List[str]) -> Dict[str, float]:
    counts = Counter(tokens)
    total = len(tokens)
    if total == 0:
        return {}
    return {word: count / total for word, count in counts.items()}


def compute_idf(documents: List[List[str]]) -> Dict[str, float]:
    n_docs = len(documents)
    if n_docs == 0:
        return {}
    doc_freq: Counter[str] = Counter()
    for doc in documents:
        unique_tokens = set(doc)
        for token in unique_tokens:
            doc_freq[token] += 1
    return {word: math.log(n_docs / freq) for word, freq in doc_freq.items()}


def cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    common_keys = set(vec_a.keys()) & set(vec_b.keys())
    if not common_keys:
        return 0.0
    dot_product = sum(vec_a[k] * vec_b[k] for k in common_keys)
    norm_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
    norm_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


class SemanticSearcher:
    """TF-IDF based semantic search over markdown documents."""

    def __init__(self) -> None:
        self.documents: List[str] = []
        self.doc_tokens: List[List[str]] = []
        self.idf: Dict[str, float] = {}

    def index_directory(self, directory: str) -> int:
        count = 0
        if not os.path.exists(directory):
            return 0
        for filename in sorted(os.listdir(directory)):
            if not filename.endswith(".md"):
                continue
            path = os.path.join(directory, filename)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.add_document(content)
            count += 1
        self._rebuild_idf()
        return count

    def add_document(self, content: str) -> None:
        self.documents.append(content)
        self.doc_tokens.append(tokenize(content))
        self._rebuild_idf()

    def _rebuild_idf(self) -> None:
        self.idf = compute_idf(self.doc_tokens)

    def search(self, query: str, top_k: int = 3) -> List[Tuple[str, float]]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        query_tf = compute_tf(query_tokens)
        query_vec = {word: tf * self.idf.get(word, 0.0) for word, tf in query_tf.items()}

        scores: List[Tuple[str, float]] = []
        for doc_content, doc_tok in zip(self.documents, self.doc_tokens):
            doc_tf = compute_tf(doc_tok)
            doc_vec = {word: tf * self.idf.get(word, 0.0) for word, tf in doc_tf.items()}
            score = cosine_similarity(query_vec, doc_vec)
            if score > 0:
                scores.append((doc_content, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
