"""Arama sonuçları için Claude ile "neden uygun" açıklaması.

Güvenlik ağları (istem kurallarına ek olarak, kodda denetlenir):
- Yalnızca aday listesindeki karar_id'ler kabul edilir.
- Alıntı, karar metninde birebir (boşluklar normalize edilerek) geçmiyorsa atılır.
- Açıklama künyeye atıf yapmıyorsa başına künye eklenir.
Olay metni günlüğe yazılmaz.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.config import get_settings
from app.services.llm import prompts

logger = logging.getLogger(__name__)

# Tek karar için modele gönderilecek en fazla metin (karakter). Şimdilik yalnızca özetler var;
# tam metinler eklendiğinde en ilgili parçalar gönderilir.
MAX_DECISION_CHARS = 6000


@dataclass(frozen=True)
class Candidate:
    id: int
    kunye: str  # "bilinmiyor" olabilir
    konu: str
    dogrulandi: bool
    metin: str
    # Künye denetimi için aranacak işaretler (ör. "1970/1")
    kunye_markers: tuple[str, ...] = ()


@dataclass
class Explanation:
    karar_id: int
    uygun: bool
    aciklama: str
    alinti: str | None


@dataclass
class ExplainResult:
    durum: str  # "tamam" | "kapali" | "hata"
    aciklamalar: dict[int, Explanation] = field(default_factory=dict)
    genel_degerlendirme: str | None = None


class LLMClient(Protocol):
    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]: ...


class ExplanationError(RuntimeError):
    pass


class AnthropicClient:
    """Anthropic Messages API ile JSON şemalı yanıt."""

    def __init__(self, api_key: str, model: str, effort: str, timeout: float) -> None:
        import anthropic

        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=2)
        self.model = model
        self.effort = effort

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        a = self._anthropic
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"effort": self.effort,
                               "format": {"type": "json_schema", "schema": schema}},
                # Güvenlik sınıflandırıcısı reddederse istek sunucu tarafında yedek modelle yinelenir
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except a.AuthenticationError as exc:
            raise ExplanationError("Anthropic API anahtarı geçersiz") from exc
        except a.RateLimitError as exc:
            raise ExplanationError("Açıklama servisi şu an yoğun") from exc
        except a.APIStatusError as exc:
            logger.error("Anthropic API hatası: %s (istek %s)", exc.status_code,
                         getattr(exc, "request_id", None))
            raise ExplanationError("Açıklama servisi hata verdi") from exc
        except a.APIConnectionError as exc:
            raise ExplanationError("Açıklama servisine ulaşılamadı") from exc

        if response.stop_reason == "refusal":
            raise ExplanationError("Açıklama servisi bu isteği yanıtlamadı")
        if response.stop_reason == "max_tokens":
            raise ExplanationError("Açıklama yanıtı yarım kaldı")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise ExplanationError("Açıklama yanıtı boş")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ExplanationError("Açıklama yanıtı çözümlenemedi") from exc


def get_llm_client() -> LLMClient | None:
    s = get_settings()
    if not s.anthropic_api_key:
        return None
    return AnthropicClient(s.anthropic_api_key, s.anthropic_model, s.anthropic_effort,
                           s.anthropic_timeout_seconds)


def _norm(text: str) -> str:
    text = text.replace("İ", "i").replace("I", "ı").lower()  # Türkçe büyük/küçük harf
    return re.sub(r"\s+", " ", text).strip().strip("\"'“”«»")


def quote_in_text(quote: str, text: str) -> bool:
    q = _norm(quote).rstrip(".…")
    return len(q) >= 10 and q in _norm(text)


def build_user_prompt(olay: str, candidates: list[Candidate]) -> str:
    blocks = [
        prompts.DECISION_TEMPLATE.format(
            id=c.id, kunye=c.kunye, konu=c.konu or "—",
            dogrulandi="true" if c.dogrulandi else "false",
            metin=c.metin[:MAX_DECISION_CHARS],
        )
        for c in candidates
    ]
    return prompts.EXPLAIN_USER_TEMPLATE.format(olay=olay, kararlar="\n\n".join(blocks))


def explain(olay: str, candidates: list[Candidate], client: LLMClient | None) -> ExplainResult:
    if client is None:
        return ExplainResult(durum="kapali")
    if not candidates:
        return ExplainResult(durum="tamam")
    try:
        data = client.complete_json(prompts.EXPLAIN_SYSTEM, build_user_prompt(olay, candidates),
                                    prompts.EXPLAIN_SCHEMA)
    except ExplanationError as exc:
        logger.warning("Açıklama üretilemedi: %s", exc)
        return ExplainResult(durum="hata")

    by_id = {c.id: c for c in candidates}
    result = ExplainResult(durum="tamam",
                           genel_degerlendirme=(data.get("genel_degerlendirme") or "").strip() or None)
    for item in data.get("sonuclar") or []:
        try:
            cid = int(item["karar_id"])
        except (KeyError, TypeError, ValueError):
            continue
        cand = by_id.get(cid)
        if cand is None or cid in result.aciklamalar:
            continue  # aday listesinde olmayan veya yinelenen karar
        aciklama = str(item.get("aciklama") or "").strip()
        if not aciklama:
            continue
        markers = cand.kunye_markers or ((cand.kunye,) if cand.kunye != "bilinmiyor" else ())
        if markers and not any(m in aciklama for m in markers):
            aciklama = f"{cand.kunye}: {aciklama}"
        alinti = str(item.get("alinti") or "").strip()
        if alinti and not quote_in_text(alinti, cand.metin):
            alinti = ""  # metinde birebir geçmeyen alıntı gösterilmez
        result.aciklamalar[cid] = Explanation(cid, bool(item.get("uygun")), aciklama,
                                              alinti or None)
    return result
