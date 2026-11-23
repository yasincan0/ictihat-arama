"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, auth } from "@/lib/api";
import { useAuth } from "./AuthProvider";
import { Alert, TextField } from "./forms";

export function AccountView() {
  const { me, loading, refresh, config } = useAuth();
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (loading) return null;
  if (!me)
    return (
      <div className="mx-auto max-w-2xl px-4 py-10">
        <Alert kind="info">
          Hesabınızı görmek için <Link href="/giris" className="font-medium underline">giriş yapın</Link>.
        </Alert>
      </div>
    );

  const k = me.kota;
  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Hesabım</h1>
      <dl className="mt-6 grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
        <dt className="text-slate-500">E-posta</dt>
        <dd>{me.kullanici.email}</dd>
        {me.kullanici.full_name && (
          <>
            <dt className="text-slate-500">Ad soyad</dt>
            <dd>{me.kullanici.full_name}</dd>
          </>
        )}
        <dt className="text-slate-500">Arama hakkı</dt>
        <dd>{k.sinirsiz ? "Sınırsız" : `Bu ay ${k.kalan} / ${k.hak} kaldı`}</dd>
      </dl>
      {config?.abonelik_acik && (
        <p className="mt-4 text-sm">
          <Link href="/abonelik" className="underline underline-offset-4">Abonelik yönetimi</Link>
        </p>
      )}

      <section className="mt-12 rounded-lg border border-red-200 p-5 dark:border-red-900">
        <h2 className="font-semibold text-red-800 dark:text-red-300">Hesabı sil</h2>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
          Hesabınız ve kişisel verileriniz kalıcı olarak silinir; bu işlem geri alınamaz. Etkin bir aboneliğiniz varsa önce
          iptal etmeniz gerekir. Kimliğinizle ilişkilendirilmeyen arama istatistikleri (olay metni içermez) anonim olarak kalır.
        </p>
        <form
          noValidate
          className="mt-4 space-y-3"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!confirm || !password) {
              setError("Şifrenizi girin ve silme işlemini onaylayın.");
              return;
            }
            setBusy(true);
            setError(null);
            try {
              await auth.deleteAccount(password);
              await refresh();
              router.push("/?hesap=silindi");
            } catch (err) {
              setError(err instanceof ApiError ? err.message : "Hesap silinemedi.");
            } finally {
              setBusy(false);
            }
          }}
        >
          {error && <Alert kind="error">{error}</Alert>}
          <TextField id="sil-sifre" label="Şifreniz" type="password" value={password} onChange={setPassword} autoComplete="current-password" />
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} className="mt-1" />
            <span>Hesabımın ve verilerimin kalıcı olarak silineceğini anlıyorum.</span>
          </label>
          <button
            type="submit"
            disabled={busy}
            className="rounded-md bg-red-700 px-4 py-2 text-sm font-medium text-white hover:bg-red-600 disabled:opacity-60"
          >
            {busy ? "Siliniyor…" : "Hesabımı kalıcı olarak sil"}
          </button>
        </form>
      </section>
    </div>
  );
}
