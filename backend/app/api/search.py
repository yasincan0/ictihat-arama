"""Arama, karar detayı ve ön yüz yapılandırması uç noktaları.

KVKK: olay metni yalnızca bu istek süresince bellekte işlenir; veritabanına ve günlüklere
yazılmaz. search_logs yalnızca uzunluk, sonuç sayısı ve karar kimliklerini tutar.
"""

import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, optional_user
from app.core.config import get_settings
from app.core.db import get_db
from app.core.ratelimit import client_ip, limit
from app.models import Decision, DecisionChunk, SearchLog, User
from app.schemas.search import (
    DecisionDetail,
    DecisionSummary,
    PublicConfig,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from app.services.embedding import Embedder, get_embedder
from app.services.llm.explain import Candidate, LLMClient, explain, get_llm_client
from app.services.quota import get_quota
from app.services.search import search

router = APIRouter(tags=["arama"])


def _candidate(d: Decision, metin: str) -> Candidate:
    has_kunye = bool(d.esas_no or d.karar_no)
    markers = tuple(x for x in (d.karar_no, d.esas_no) if x)
    return Candidate(
        id=d.id,
        kunye=d.kunye if has_kunye else "bilinmiyor",
        konu=d.kategori or "",
        dogrulandi=d.dogrulandi,
        metin=metin,
        kunye_markers=markers,
    )


@router.get("/config", response_model=PublicConfig)
def public_config(db: Session = Depends(get_db)) -> PublicConfig:
    s = get_settings()
    total = db.scalar(select(func.count(func.distinct(DecisionChunk.decision_id)))) or 0
    verified = db.scalar(select(func.count(Decision.id)).where(Decision.dogrulandi.is_(True))) or 0
    return PublicConfig(arama_giris_gerekli=s.search_requires_login,
                        abonelik_acik=s.payments_enabled,
                        aciklama_acik=bool(s.anthropic_api_key),
                        karar_sayisi=total, dogrulanmis_karar_sayisi=verified)


@router.post("/search", response_model=SearchResponse)
def search_endpoint(body: SearchRequest, request: Request, db: Session = Depends(get_db),
                    user: User | None = Depends(optional_user),
                    embedder: Embedder = Depends(get_embedder),
                    llm: LLMClient | None = Depends(get_llm_client)) -> SearchResponse:
    s = get_settings()
    limit("search_ip", client_ip(request))
    if s.search_requires_login and user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Arama yapmak için giriş yapın")
    if s.payments_enabled and user is not None and not get_quota(db, user).allowed:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
                            "Bu ayki ücretsiz arama hakkınızı kullandınız")

    started = time.monotonic()
    hits = search(db, embedder, body.olay, top_k=s.search_top_k)
    top = hits[: s.explain_top_n]
    expl = explain(body.olay, [_candidate(h.decision, h.best_chunk) for h in top],
                   llm if s.explain_top_n else None)

    results = []
    for h in hits:
        e = expl.aciklamalar.get(h.decision.id)
        results.append(SearchResult(
            karar=DecisionSummary.model_validate(h.decision), skor=round(h.score, 4),
            aciklama=e.aciklama if e else None, alinti=e.alinti if e else None,
            uygun=e.uygun if e else None,
        ))
    # Claude'un uygun bulmadığı kararlar (değerlendirilenler içinde) sona alınır; sıra korunur
    results.sort(key=lambda r: 1 if r.uygun is False else 0)

    db.add(SearchLog(user_id=user.id if user else None, query_length=len(body.olay),
                     result_count=len(results),
                     result_decision_ids=[r.karar.id for r in results],
                     duration_ms=int((time.monotonic() - started) * 1000)))
    db.commit()
    return SearchResponse(sonuclar=results, aciklama_durumu=expl.durum,
                          genel_degerlendirme=expl.genel_degerlendirme)


@router.get("/decisions/{decision_id}", response_model=DecisionDetail)
def get_decision(decision_id: int, db: Session = Depends(get_db),
                 user: User | None = Depends(optional_user)) -> Decision:
    if get_settings().search_requires_login and user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Giriş yapmanız gerekiyor")
    d = db.get(Decision, decision_id)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Karar bulunamadı")
    return d


__all__ = ["router", "get_current_user"]
