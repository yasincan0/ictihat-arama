import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl px-4 py-24 text-center">
      <h1 className="text-2xl font-semibold">Sayfa bulunamadı</h1>
      <Link href="/" className="mt-6 inline-block text-sm underline underline-offset-4">Ana sayfaya dön</Link>
    </div>
  );
}
