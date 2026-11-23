import Link from "next/link";
import { formatKunye, formatResmiGazete, formatScore } from "@/lib/format";
import type { SearchResult } from "@/lib/types";
import { VerificationBadge } from "./VerificationBadge";

export function resultTitle(k: SearchResult["karar"]): string {
  if (!k.esas_no && !k.karar_no) {
    return `${k.mahkeme} kararı — künyesi bilinmiyor${k.kategori ? ` (${k.kategori})` : ""}`;
  }
  return formatKunye(k);
}

export function ResultCard({ result, rank }: { result: SearchResult; rank: number }) {
  const { karar, skor, aciklama, alinti, uygun } = result;
  const rg = formatResmiGazete(karar);
  const noKunye = !karar.esas_no && !karar.karar_no;
  return (
    <article
      className={`rounded-lg border bg-white p-5 shadow-sm dark:bg-slate-900 ${
        uygun === false ? "border-slate-200 opacity-80 dark:border-slate-800" : "border-slate-200 dark:border-slate-800"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
          <span className="mr-2 text-slate-400">{rank}.</span>
          {resultTitle(karar)}
        </h3>
        <span className="shrink-0 rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300" title="Anlamsal benzerlik">
          Benzerlik {formatScore(skor)}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <VerificationBadge verified={karar.dogrulandi} source={karar.dogrulama_kaynagi} />
        {noKunye && (
          <span className="rounded-full bg-amber-50 px-2.5 py-0.5 font-medium text-amber-900 ring-1 ring-amber-300 dark:bg-amber-950 dark:text-amber-200 dark:ring-amber-700">
            Künye eksik: esas/karar no bilinmiyor
          </span>
        )}
        {karar.kategori && !noKunye && <span>{karar.kategori}</span>}
        {rg && <span>{rg}</span>}
      </div>
      {karar.ozet && <p className="mt-3 text-sm text-slate-700 dark:text-slate-300">{karar.ozet}</p>}
      {aciklama && (
        <div className="mt-3 rounded-md bg-slate-50 p-3 text-sm text-slate-700 dark:bg-slate-800/60 dark:text-slate-300">
          <p className="font-medium text-slate-900 dark:text-slate-100">
            {uygun === false ? "Olaya uygun görünmüyor" : "Neden uygun?"}
          </p>
          <p className="mt-1">{aciklama}</p>
          {alinti && (
            <blockquote className="mt-2 border-l-2 border-slate-300 pl-3 italic text-slate-600 dark:border-slate-600 dark:text-slate-400">
              {alinti}
            </blockquote>
          )}
        </div>
      )}
      <Link href={`/karar/${karar.id}`} className="mt-4 inline-block text-sm font-medium text-slate-900 underline underline-offset-4 hover:text-slate-600 dark:text-slate-100">
        Karar ayrıntısı
      </Link>
    </article>
  );
}
