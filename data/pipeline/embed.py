"""Kararları parçalara böler, embedding üretir ve decision_chunks tablosuna yazar.

Kullanım (depo kökünden):
    python -m data.pipeline.embed            # parçası olmayan kararları işler
    python -m data.pipeline.embed --force    # tüm kararları yeniden işler

Varsayılan modelde (BAAI/bge-m3) ilk çalıştırmada model indirilir (~2,2 GB).
Kararın metni değiştiyse (ör. doğrulamada tam metin eklendiyse) parçaları yeniden üretilir.
"""

from __future__ import annotations

import argparse
import time

from data.pipeline import _bootstrap  # noqa: F401  (app.* içe aktarımı için)

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.orm import Session, selectinload  # noqa: E402

from app.models import Decision, DecisionChunk  # noqa: E402
from app.services.chunking import build_chunks  # noqa: E402
from app.services.embedding import Embedder  # noqa: E402


def _needs_update(d: Decision, force: bool) -> bool:
    if force or not d.chunks:
        return True
    expected = [c.metin for c in build_chunks(d)]
    return expected != [c.metin for c in d.chunks]


def embed_decisions(session: Session, embedder: Embedder, force: bool = False,
                    batch_size: int = 32) -> dict[str, int]:
    """Commit çağıranın sorumluluğundadır."""
    decisions = session.scalars(
        select(Decision).options(selectinload(Decision.chunks)).order_by(Decision.id)
    ).all()
    todo = [d for d in decisions if _needs_update(d, force)]
    stats = {"karar": len(decisions), "islenen": 0, "parca": 0, "metinsiz": 0}

    pending: list[tuple[Decision, list]] = []
    for d in todo:
        chunks = build_chunks(d)
        session.execute(delete(DecisionChunk).where(DecisionChunk.decision_id == d.id))
        if not chunks:
            stats["metinsiz"] += 1
            continue
        pending.append((d, chunks))
    session.expire_all()

    flat = [(d, c) for d, chunks in pending for c in chunks]
    for i in range(0, len(flat), batch_size):
        part = flat[i : i + batch_size]
        vectors = embedder.encode_documents([c.embed_text for _, c in part])
        for (d, c), v in zip(part, vectors):
            session.add(DecisionChunk(decision_id=d.id, sira=c.sira, metin=c.metin, embedding=v))
        session.flush()
    stats["islenen"] = len(pending)
    stats["parca"] = len(flat)
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Kararları vektörleştirir.")
    parser.add_argument("--force", action="store_true", help="Tüm kararları yeniden işle")
    args = parser.parse_args(argv)

    from app.core.db import SessionLocal
    from app.services.embedding import get_embedder

    started = time.monotonic()
    embedder = get_embedder()
    with SessionLocal() as session:
        stats = embed_decisions(session, embedder, force=args.force)
        session.commit()
    print(f"Toplam karar: {stats['karar']}; işlenen: {stats['islenen']} "
          f"({stats['parca']} parça); metni olmadığı için atlanan: {stats['metinsiz']}; "
          f"süre: {time.monotonic() - started:.1f} sn")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
