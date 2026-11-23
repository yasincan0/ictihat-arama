"use client";

import Link from "next/link";
import { useState } from "react";
import { ApiError, USE_MOCK_SEARCH, searchDecisions } from "@/lib/api";
import type { SearchResponse } from "@/lib/types";
import { useAuth } from "./AuthProvider";
import { Alert } from "./forms";
import { ResultCard } from "./ResultCard";
import { SearchForm } from "./SearchForm";

export function SearchView({ mock = USE_MOCK_SEARCH }: { mock?: boolean }) {
  const { me, loading, refresh } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<SearchResponse | null>(null);

  const needLogin = !mock && !loading && !me;
  const quota = me?.kota;
  const outOfQuota = !mock && quota && !quota.sinirsiz && (quota.kalan ?? 0) <= 0;

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Karar ara</h1>
      {quota && !quota.sinirsiz && (
        <p className="mt-1 text-sm text-slate-500">Bu ay kalan ücretsiz arama hakkınız: {quota.kalan}</p>
      )}
      {mock && (
        <div className="mt-4">
          <Alert kind="info">
            Arama servisi henüz bağlı değil; aşağıda yalnızca arayüzü göstermek için hazırlanmış örnek sonuçlar
            görünür. Bunlar gerçek karar değildir.
          </Alert>
        </div>
      )}
      <div className="mt-6">
        {needLogin ? (
          <Alert kind="info">
            Arama yapmak için <Link href="/giris" className="font-medium underline">giriş yapın</Link> veya{" "}
            <Link href="/kayit" className="font-medium underline">ücretsiz hesap açın</Link>.
          </Alert>
        ) : outOfQuota ? (
          <Alert kind="info">Bu ayki ücretsiz arama hakkınızı kullandınız. Sınırsız arama için abone olabilirsiniz.</Alert>
        ) : (
          <SearchForm
            busy={busy}
            onSearch={async (q) => {
              setBusy(true);
              setError(null);
              try {
                setData(await searchDecisions(q));
                if (!mock) void refresh(); // kota güncellensin
              } catch (err) {
                setError(err instanceof ApiError ? err.message : "Arama yapılamadı.");
              } finally {
                setBusy(false);
              }
            }}
          />
        )}
      </div>

      {error && (
        <div className="mt-6">
          <Alert kind="error">{error}</Alert>
        </div>
      )}

      {data && (
        <section className="mt-10 space-y-4" aria-label="Sonuçlar">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Sonuçlar</h2>
          {data.sonuclar.length === 0 ? (
            <Alert kind="info">Olayınıza uygun bir içtihadı birleştirme kararı bulunamadı.</Alert>
          ) : (
            data.sonuclar.map((r, i) => <ResultCard key={r.karar.id} result={r} rank={i + 1} />)
          )}
        </section>
      )}
    </div>
  );
}
