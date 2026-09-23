"""Retrieval over the metric definitions and analysis summaries.

The corpus is small (a few dozen sections), so TF-IDF is enough and keeps the
whole thing runnable offline. Swapping in an embedding model would only
change `DefinitionIndex.__init__` and `search`.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

DOCS = [
    Path(__file__).resolve().parent.parent / "docs" / "definitions.md",
    Path(__file__).resolve().parent.parent / "docs" / "findings.md",
]


@dataclass
class Chunk:
    title: str
    text: str
    score: float = 0.0


def split_markdown(text: str) -> list[Chunk]:
    """One chunk per '## ' section."""
    chunks = []
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        title, _, body = block.partition("\n")
        body = body.strip()
        if body:
            chunks.append(Chunk(title.strip(), body))
    return chunks


class DefinitionIndex:
    def __init__(self, chunks: list[Chunk]):
        if not chunks:
            raise ValueError("nothing to index")
        self.chunks = chunks
        self.vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        self.matrix = self.vec.fit_transform([f"{c.title} {c.title} {c.text}" for c in chunks])

    @classmethod
    def from_files(cls, paths=DOCS) -> "DefinitionIndex":
        chunks = []
        for p in paths:
            if Path(p).exists():
                chunks.extend(split_markdown(Path(p).read_text(encoding="utf-8")))
        return cls(chunks)

    def search(self, query: str, k: int = 2, min_score: float = 0.05) -> list[Chunk]:
        sims = linear_kernel(self.vec.transform([query]), self.matrix).ravel()
        best = sims.argsort()[::-1][:k]
        return [Chunk(self.chunks[i].title, self.chunks[i].text, float(sims[i]))
                for i in best if sims[i] >= min_score]
