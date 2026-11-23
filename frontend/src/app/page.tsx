// Geçici ana sayfa. Tanıtım ve arama sayfaları Adım 6'da yapılacak.
export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center px-4 py-16">
      <h1 className="text-3xl font-semibold tracking-tight">İçtihat Arama</h1>
      <p className="mt-4 text-lg text-gray-600">
        Davanızdaki olayı kendi cümlelerinizle anlatın; size uygun içtihadı birleştirme
        kararlarını bulalım ve neden uygun olduklarını açıklayalım.
      </p>
      <p className="mt-8 text-sm text-gray-500">Yapım aşamasında.</p>
    </main>
  );
}
