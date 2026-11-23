import Link from "next/link";
import { formatKunye, formatResmiGazete, formatScore } from "@/lib/format";
import type { SearchResult } from "@/lib/types";
import { VerificationBadge } from "./VerificationBadge";

export function ResultCard({ result, rank }: { result: SearchResult; rank: number }) {
  const { karar, skor, aciklama, alinti } = result;
  const rg = formatResmiGazete(karar);
  return (
    <article className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
          <span className="mr-2 text-slate-400">{rank}.</span>
          {formatKunye(karar)}
        </h3>
        <span className="shrink-0 rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300" title="Benzerlik skoru">
          Uygunluk {formatScore(skor)}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <VerificationBadge verified={karar.dogrulandi} source={karar.dogrulama_kaynagi} />
        {rg && <span>{rg}</span>}
      </div>
      {karar.ozet && <p className="mt-3 text-sm text-slate-700 dark:text-slate-300">{karar.ozet}</p>}
      {aciklama && (
        <div className="mt-3 rounded-md bg-slate-50 p-3 text-sm text-slate-700 dark:bg-slate-800/60 dark:text-slate-300">
          <p className="font-medium text-slate-900 dark:text-slate-100">Neden uygun?</p>
          <p className="mt-1">{aciklama}</p>
          {alinti && (
            <blockquote className="mt-2 border-l-2 border-slate-300 pl-3 italic text-slate-600 dark:border-slate-600 dark:text-slate-400">
              {alinti}
            </blockquote>
          )}
        </div>
      )}
      <Link href={`/karar/${karar.id}`} className="mt-4 inline-block text-sm font-medium text-slate-900 underline underline-offset-4 hover:text-slate-600 dark:text-slate-100">
        Tam metni görüntüle
      </Link>
    </article>
  );
}
