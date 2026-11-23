// Doğrulanmamış kararlar her yerde açık bir uyarıyla gösterilir (bkz. CLAUDE.md).

export function VerificationBadge({ verified, source }: { verified: boolean; source?: string | null }) {
  if (verified) {
    return (
      <span
        className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-800 ring-1 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-200 dark:ring-emerald-800"
        title={source ?? undefined}
      >
        <span aria-hidden>✓</span> Resmî kaynaktan doğrulandı
      </span>
    );
  }
  return (
    <span
      role="status"
      className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-900 ring-1 ring-amber-300 dark:bg-amber-950 dark:text-amber-200 dark:ring-amber-700"
      title="Bu kaydın künyesi ve özeti henüz resmî kaynakla karşılaştırılmadı."
    >
      <span aria-hidden>!</span> Doğrulanmamış: resmî kaynaktan kontrol edin
    </span>
  );
}
