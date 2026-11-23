// Hukuki metin sayfaları için ortak düzen. TASLAK uyarısı, metinler hukukçu tarafından
// düzenlenip onaylanana kadar kaldırılmamalıdır.

export function LegalPage({ title, updated, children }: { title: string; updated: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <div role="note" className="rounded-md bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-300 dark:bg-amber-950 dark:text-amber-200 dark:ring-amber-700">
        TASLAK — Bu metin hukuki inceleme ve onaydan geçmemiştir. Köşeli parantez içindeki alanlar doldurulmalıdır.
      </div>
      <h1 className="mt-6 text-2xl font-semibold text-slate-900 dark:text-slate-100">{title}</h1>
      <p className="mt-1 text-sm text-slate-500">Son güncelleme: {updated}</p>
      <div className="legal mt-6 space-y-4 text-[15px] leading-7 text-slate-800 dark:text-slate-200 [&_h2]:mt-8 [&_h2]:text-lg [&_h2]:font-semibold [&_li]:ml-5 [&_li]:list-disc [&_.not]:text-sm [&_.not]:italic [&_.not]:text-amber-800 dark:[&_.not]:text-amber-300">
        {children}
      </div>
    </div>
  );
}
