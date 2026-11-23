"""Anlamsal arama: olay metnine en yakın karar parçalarını bulur, karar bazında gruplar."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Decision, DecisionChunk
from app.services.embedding import Embedder


@dataclass
class Hit:
    decision: Decision
    score: float  # 0..1 (kosinüs benzerliği)
    best_chunk: str


def search(db: Session, embedder: Embedder, query: str, top_k: int = 10) -> list[Hit]:
    vec = embedder.encode_query(query)
    distance = DecisionChunk.embedding.cosine_distance(vec)
    rows = db.execute(
        select(DecisionChunk.decision_id, DecisionChunk.metin, distance.label("d"))
        .where(DecisionChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(top_k * 5)
    ).all()
    best: dict[int, tuple[float, str]] = {}
    for decision_id, metin, d in rows:
        score = max(0.0, min(1.0, 1.0 - float(d)))
        if decision_id not in best or score > best[decision_id][0]:
            best[decision_id] = (score, metin)
    ranked = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)[:top_k]
    if not ranked:
        return []
    decisions = {d.id: d for d in db.scalars(
        select(Decision).where(Decision.id.in_([i for i, _ in ranked])))}
    return [Hit(decisions[i], s, m) for i, (s, m) in ranked if i in decisions]
