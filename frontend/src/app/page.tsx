import Link from "next/link";

const STEPS = [
  { title: "Olayı anlatın", text: "Davanızdaki olayı müvekkilinizden dinlediğiniz gibi, kendi cümlelerinizle yazın." },
  { title: "Uygun kararları görün", text: "Anlamsal arama, olayınıza en yakın içtihadı birleştirme kararlarını sıralar." },
  { title: "Gerekçeyi okuyun", text: "Her kararın neden uygun olduğu, yalnızca karar metnine dayanarak ve künyesiyle açıklanır." },
];

export default function Home() {
  return (
    <div className="mx-auto max-w-5xl px-4">
      <section className="py-16 sm:py-24">
        <h1 className="max-w-3xl text-3xl font-semibold tracking-tight text-slate-900 sm:text-5xl dark:text-slate-100">
          Davanıza uygun içtihadı birleştirme kararını dakikalar içinde bulun
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-slate-600 dark:text-slate-400">
          Olayı serbest metinle anlatın; Danıştay İçtihatları Birleştirme Kurulu kararları arasından en uygun olanları
          ve neden uygun olduklarını görün.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/ara" className="rounded-md bg-slate-900 px-5 py-3 text-sm font-medium text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900">
            Aramaya başla
          </Link>
          <Link href="/kayit" className="rounded-md px-5 py-3 text-sm font-medium text-slate-900 ring-1 ring-slate-300 hover:bg-slate-50 dark:text-slate-100 dark:ring-slate-700 dark:hover:bg-slate-900">
            Ücretsiz hesap aç
          </Link>
        </div>
        <p className="mt-3 text-sm text-slate-500">Deneme sürümü: arama için hesap gerekmez.</p>
      </section>

      <section className="grid gap-6 pb-16 sm:grid-cols-3">
        {STEPS.map((s, i) => (
          <div key={s.title} className="rounded-lg border border-slate-200 p-5 dark:border-slate-800">
            <p className="text-sm font-medium text-slate-400">{i + 1}</p>
            <h2 className="mt-1 font-semibold text-slate-900 dark:text-slate-100">{s.title}</h2>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">{s.text}</p>
          </div>
        ))}
      </section>

      <section className="mb-20 grid gap-6 rounded-xl bg-slate-50 p-6 sm:grid-cols-2 dark:bg-slate-900">
        <div>
          <h2 className="font-semibold text-slate-900 dark:text-slate-100">Kaynağı belli kararlar</h2>
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
            Kararlar Resmî Gazete ile doğrulanır. Henüz doğrulanmamış kayıtlar açık bir uyarıyla gösterilir.
          </p>
        </div>
        <div>
          <h2 className="font-semibold text-slate-900 dark:text-slate-100">Olay özetiniz saklanmaz</h2>
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
            Yazdığınız olay metni yalnızca arama için kullanılır; kalıcı olarak kaydedilmez ve günlüklere yazılmaz.
          </p>
        </div>
      </section>
    </div>
  );
}
