"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, payments } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Billing, Plan, SubscriptionState } from "@/lib/types";
import { isValidTckn, isValidTrGsm } from "@/lib/validation";
import { useAuth } from "./AuthProvider";
import { Alert, SubmitButton, TextField } from "./forms";
import { ProviderCheckout } from "./ProviderCheckout";

const RESULT_MESSAGES: Record<string, { kind: "success" | "error"; text: string }> = {
  basarili: { kind: "success", text: "Ödemeniz alındı, aboneliğiniz başladı. Teşekkür ederiz." },
  hata: { kind: "error", text: "Ödeme tamamlanamadı. Kartınızdan çekim yapılmadıysa tekrar deneyebilirsiniz." },
};

const STATUS_LABELS: Record<string, string> = {
  active: "Etkin",
  past_due: "Ödeme bekleniyor",
  canceled: "İptal edildi",
  expired: "Sona erdi",
};

const EMPTY: Billing = { ad: "", soyad: "", tckn: "", telefon: "", adres: "", sehir: "" };

export function validateBilling(b: Billing): string | null {
  if (!b.ad.trim() || !b.soyad.trim()) return "Ad ve soyadınızı girin.";
  if (!isValidTckn(b.tckn)) return "T.C. kimlik numarası geçersiz.";
  if (!isValidTrGsm(b.telefon)) return "Geçerli bir cep telefonu numarası girin.";
  if (b.adres.trim().length < 5) return "Fatura adresinizi girin.";
  if (b.sehir.trim().length < 2) return "Şehri girin.";
  return null;
}

export function SubscriptionView({ result }: { result?: string | null }) {
  const { me, loading, refresh } = useAuth();
  const [plan, setPlan] = useState<Plan | null>(null);
  const [sub, setSub] = useState<SubscriptionState | null>(null);
  const [billing, setBilling] = useState<Billing>(EMPTY);
  const [formHtml, setFormHtml] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    payments.plan().then(setPlan).catch(() => setPlan(null));
  }, []);
  useEffect(() => {
    if (me) payments.subscription().then(setSub).catch(() => setSub(null));
  }, [me]);

  const set = (k: keyof Billing) => (v: string) => setBilling((b) => ({ ...b, [k]: v }));
  const banner = result ? RESULT_MESSAGES[result] : undefined;

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Abonelik</h1>
      <p className="mt-2 text-slate-600 dark:text-slate-400">
        Abonelikle sınırsız arama yapabilirsiniz. Abonelik olmadan ayda {plan?.ucretsiz_arama_hakki ?? 3} ücretsiz arama
        hakkınız vardır.
      </p>
      {plan?.fiyat_metni && <p className="mt-2 font-medium text-slate-900 dark:text-slate-100">{plan.fiyat_metni}</p>}

      <div className="mt-6 space-y-4">
        {banner && <Alert kind={banner.kind}>{banner.text}</Alert>}
        {error && <Alert kind="error">{error}</Alert>}
        {info && <Alert kind="success">{info}</Alert>}
        {plan?.saglayici === "fake" && (
          <Alert kind="info">Geliştirme modu: ödeme sağlayıcısı sahte; gerçek ödeme alınmaz.</Alert>
        )}
      </div>

      {loading ? null : !me ? (
        <div className="mt-6">
          <Alert kind="info">
            Abone olmak için <Link href="/giris" className="font-medium underline">giriş yapın</Link>.
          </Alert>
        </div>
      ) : sub?.var ? (
        <section className="mt-6 rounded-lg border border-slate-200 p-5 dark:border-slate-800">
          <p className="text-sm text-slate-500">Durum</p>
          <p className="text-lg font-semibold">{STATUS_LABELS[sub.durum ?? ""] ?? sub.durum}</p>
          {sub.donem_sonu && (
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
              {sub.durum === "canceled" ? "Sınırsız arama şu tarihe kadar sürer: " : "Dönem sonu: "}
              {formatDate(sub.donem_sonu.slice(0, 10))}
            </p>
          )}
          {sub.iptal_edilebilir && (
            <button
              type="button"
              disabled={busy}
              className="mt-4 text-sm font-medium text-red-700 underline underline-offset-4 disabled:opacity-60 dark:text-red-400"
              onClick={async () => {
                if (!window.confirm("Aboneliğinizi iptal etmek istediğinize emin misiniz? Yenileme yapılmaz.")) return;
                setBusy(true);
                setError(null);
                try {
                  setInfo((await payments.cancel()).mesaj);
                  setSub(await payments.subscription());
                  await refresh();
                } catch (err) {
                  setError(err instanceof ApiError ? err.message : "İptal edilemedi.");
                } finally {
                  setBusy(false);
                }
              }}
            >
              Aboneliği iptal et
            </button>
          )}
        </section>
      ) : formHtml ? (
        <section className="mt-6">
          <ProviderCheckout html={formHtml} />
        </section>
      ) : (
        <form
          noValidate
          className="mt-6 space-y-4"
          onSubmit={async (e) => {
            e.preventDefault();
            const problem = validateBilling(billing);
            setError(problem);
            if (problem) return;
            setBusy(true);
            try {
              const res = await payments.checkout(billing);
              setFormHtml(res.checkout_form_content);
            } catch (err) {
              setError(err instanceof ApiError ? err.message : "Ödeme başlatılamadı.");
            } finally {
              setBusy(false);
            }
          }}
        >
          {!me.kullanici.email_verified && <Alert kind="info">Abone olmadan önce e-posta adresinizi doğrulayın.</Alert>}
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField id="ad" label="Ad" value={billing.ad} onChange={set("ad")} autoComplete="given-name" required />
            <TextField id="soyad" label="Soyad" value={billing.soyad} onChange={set("soyad")} autoComplete="family-name" required />
            <TextField id="tckn" label="T.C. kimlik no" value={billing.tckn} onChange={set("tckn")} required />
            <TextField id="telefon" label="Cep telefonu" type="tel" value={billing.telefon} onChange={set("telefon")} autoComplete="tel" required />
          </div>
          <TextField id="adres" label="Fatura adresi" value={billing.adres} onChange={set("adres")} autoComplete="street-address" required />
          <TextField id="sehir" label="Şehir" value={billing.sehir} onChange={set("sehir")} autoComplete="address-level1" required />
          <p className="text-xs text-slate-500">
            Bu bilgiler ödeme kuruluşu iyzico&apos;nun zorunlu tuttuğu bilgilerdir; yalnızca iyzico&apos;ya iletilir ve
            tarafımızda saklanmaz. Kart bilgileriniz iyzico&apos;nun ödeme formunda girilir; bize ulaşmaz.
          </p>
          <SubmitButton busy={busy}>Ödemeye geç</SubmitButton>
        </form>
      )}
    </div>
  );
}
