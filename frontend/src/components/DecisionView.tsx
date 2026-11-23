"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, getDecision } from "@/lib/api";
import { formatKunye, formatResmiGazete } from "@/lib/format";
import type { DecisionDetail } from "@/lib/types";
import { Alert } from "./forms";
import { VerificationBadge } from "./VerificationBadge";

export function DecisionView({ id }: { id: number }) {
  const [d, setD] = useState<DecisionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isInteger(id) || id <= 0) {
      setError("Karar bulunamadı.");
      return;
    }
    getDecision(id)
      .then(setD)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Karar yüklenemedi."));
  }, [id]);

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <Link href="/ara" className="text-sm text-slate-600 underline underline-offset-4 dark:text-slate-400">
        ← Aramaya dön
      </Link>
      {error && (
        <div className="mt-6">
          <Alert kind="error">{error}</Alert>
        </div>
      )}
      {!d && !error && <p className="mt-6 text-sm text-slate-500">Yükleniyor…</p>}
      {d && (
        <article className="mt-6">
          <h1 className="text-xl font-semibold text-slate-900 sm:text-2xl dark:text-slate-100">{formatKunye(d)}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-slate-500">
            <VerificationBadge verified={d.dogrulandi} source={d.dogrulama_kaynagi} />
            {formatResmiGazete(d) && <span>{formatResmiGazete(d)}</span>}
          </div>
          {d.dogrulandi && d.dogrulama_kaynagi && (
            <p className="mt-2 text-xs text-slate-500">Doğrulama kaynağı: {d.dogrulama_kaynagi}</p>
          )}
          {!d.dogrulandi && (
            <div className="mt-4">
              <Alert kind="info">
                Bu kaydın künyesi ve özeti ikincil kaynaklardan derlenmiştir ve henüz resmî kaynakla doğrulanmamıştır.
                Kullanmadan önce Resmî Gazete veya Danıştay kaynaklarından kontrol edin.
              </Alert>
            </div>
          )}
          {d.ozet && (
            <section className="mt-6">
              <h2 className="font-semibold text-slate-900 dark:text-slate-100">Özet</h2>
              <p className="mt-2 text-slate-700 dark:text-slate-300">{d.ozet}</p>
            </section>
          )}
          <section className="mt-6">
            <h2 className="font-semibold text-slate-900 dark:text-slate-100">Tam metin</h2>
            {d.tam_metin ? (
              <div className="mt-2 whitespace-pre-wrap rounded-lg border border-slate-200 p-4 font-serif text-[15px] leading-7 text-slate-800 dark:border-slate-800 dark:text-slate-200">
                {d.tam_metin}
              </div>
            ) : (
              <p className="mt-2 text-sm text-slate-500">Bu kararın tam metni henüz eklenmedi.</p>
            )}
          </section>
        </article>
      )}
    </div>
  );
}
