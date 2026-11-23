"""Kararları aranabilir parçalara böler.

- Tam metin varsa: paragraf tabanlı, örtüşmeli parçalar (yaklaşık CHUNK_CHARS karakter).
- Yalnızca özet varsa (şimdiki durum): kategori + özet tek parça.
Embedding'e giden metnin başına künye ve kategori eklenir (bağlam için); saklanan
`metin` ise kararın kendi metnidir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import Decision

CHUNK_CHARS = 1200
OVERLAP_CHARS = 200


@dataclass(frozen=True)
class Chunk:
    sira: int
    metin: str  # saklanan ve gösterilen metin
    embed_text: str  # vektörleştirilen metin (başlıklı)


def _header(d: Decision) -> str:
    parts = []
    if d.esas_no or d.karar_no:
        parts.append(d.kunye)
    if d.kategori:
        parts.append(f"Konu: {d.kategori}")
    return ". ".join(parts)


def split_paragraphs(text: str, size: int = CHUNK_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n(?=\s{2,})", text) if p.strip()]
    chunks: list[str] = []
    cur = ""
    for p in paras:
        while len(p) > size:  # çok uzun paragrafı böl
            head, p = p[:size], p[size - overlap:]
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(head)
        if cur and len(cur) + len(p) + 2 > size:
            chunks.append(cur)
            cur = cur[-overlap:] + "\n\n" + p if overlap else p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    if cur:
        chunks.append(cur)
    return chunks


def build_chunks(d: Decision) -> list[Chunk]:
    header = _header(d)
    if d.tam_metin and d.tam_metin.strip():
        texts = split_paragraphs(d.tam_metin)
        # Özet varsa ayrıca bir parça olarak eklenir (kısa sorgularda isabeti artırır)
        if d.ozet:
            texts = [d.ozet] + texts
    elif d.ozet:
        texts = [d.ozet]
    else:
        return []
    return [
        Chunk(sira=i, metin=t, embed_text=f"{header}\n{t}" if header else t)
        for i, t in enumerate(texts)
    ]
