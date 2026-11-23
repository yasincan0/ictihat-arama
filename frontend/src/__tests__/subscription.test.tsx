import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AuthProvider } from "@/components/AuthProvider";
import { ProviderCheckout } from "@/components/ProviderCheckout";
import { SubscriptionView, validateBilling } from "@/components/SubscriptionView";
import { isValidTckn, isValidTrGsm } from "@/lib/validation";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status });
const ME = {
  kullanici: { id: 1, email: "a@ornek.com", full_name: null, email_verified: true },
  kota: { sinirsiz: false, kullanilan: 0, hak: 3, kalan: 3, donem_baslangici: "2026-11-01T00:00:00Z" },
};
const PLAN = { fiyat_metni: "Aylık 100 TL", saglayici: "fake", ucretsiz_arama_hakki: 3 };

function router(routes: Record<string, () => Response>) {
  return vi.fn((url: string) => {
    const path = new URL(url).pathname;
    const h = routes[path];
    return Promise.resolve(h ? h() : json(404, { detail: "yok" }));
  });
}

describe("fatura bilgisi doğrulama", () => {
  it("TCKN ve telefon arka uçla aynı kurallarla denetlenir", () => {
    expect(isValidTckn("10000000146")).toBe(true);
    expect(isValidTckn("12345678901")).toBe(false);
    expect(isValidTrGsm("0532 123 45 67")).toBe(true);
    expect(isValidTrGsm("+90 532 123 45 67")).toBe(true);
    expect(isValidTrGsm("0212 123 45 67")).toBe(false);
    const ok = { ad: "A", soyad: "B", tckn: "10000000146", telefon: "05321234567", adres: "Adres 1", sehir: "Ankara" };
    expect(validateBilling(ok)).toBeNull();
    expect(validateBilling({ ...ok, tckn: "1" })).toMatch(/kimlik/);
  });
});

describe("ProviderCheckout", () => {
  it("sağlayıcı formundaki scriptleri çalıştırılabilir hale getirir", () => {
    // jsdom script çalıştırmaz; innerHTML'deki etkisiz script'in yenisiyle değiştirildiğini denetle
    const spy = vi.spyOn(document, "createElement");
    render(<ProviderCheckout html={'<p>form</p><script src="https://ornek/odeme.js" async></script><script>var x = 1;</script>'} />);
    expect(screen.getByText("form")).toBeInTheDocument();
    const created = spy.mock.results.filter((r) => (r.value as Element).tagName === "SCRIPT").map((r) => r.value as HTMLScriptElement);
    expect(created).toHaveLength(2);
    expect(created[0].getAttribute("src")).toBe("https://ornek/odeme.js");
    expect(created[1].text).toBe("var x = 1;");
    expect(screen.getByTestId("odeme-formu").querySelectorAll("script")).toHaveLength(2);
  });
});

describe("SubscriptionView", () => {
  it("abone olmayan kullanıcı için fatura formunu gösterir ve ödeme formunu açar", async () => {
    const fetchMock = router({
      "/auth/me": () => json(200, ME),
      "/payments/plan": () => json(200, PLAN),
      "/payments/subscription": () => json(200, { var: false, durum: null, donem_sonu: null, plan: null, iptal_edilebilir: false }),
      "/payments/checkout": () => json(200, { token: "t", checkout_form_content: "<p>SAHTE ODEME FORMU</p>", saglayici: "fake" }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <SubscriptionView />
      </AuthProvider>,
    );
    expect(await screen.findByText("Aylık 100 TL")).toBeInTheDocument();
    expect(screen.getByText(/Geliştirme modu/)).toBeInTheDocument();
    await user.type(await screen.findByLabelText("Ad"), "Ayşe");
    await user.type(screen.getByLabelText("Soyad"), "Yılmaz");
    await user.type(screen.getByLabelText("T.C. kimlik no"), "12345678901");
    await user.type(screen.getByLabelText("Cep telefonu"), "05321234567");
    await user.type(screen.getByLabelText("Fatura adresi"), "Örnek Mah. 1");
    await user.type(screen.getByLabelText("Şehir"), "Ankara");
    await user.click(screen.getByRole("button", { name: "Ödemeye geç" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/kimlik/);

    await user.clear(screen.getByLabelText("T.C. kimlik no"));
    await user.type(screen.getByLabelText("T.C. kimlik no"), "10000000146");
    await user.click(screen.getByRole("button", { name: "Ödemeye geç" }));
    expect(await screen.findByText("SAHTE ODEME FORMU")).toBeInTheDocument();
    const call = fetchMock.mock.calls.find((c) => String(c[0]).endsWith("/payments/checkout"))!;
    expect(JSON.parse((call[1] as RequestInit).body as string).tckn).toBe("10000000146");
  });

  it("etkin abonelikte durumu ve iptal düğmesini gösterir; dönüş sonucunu bildirir", async () => {
    vi.stubGlobal(
      "fetch",
      router({
        "/auth/me": () => json(200, ME),
        "/payments/plan": () => json(200, PLAN),
        "/payments/subscription": () =>
          json(200, { var: true, durum: "active", donem_sonu: "2026-12-20T00:00:00Z", plan: "aylik", iptal_edilebilir: true }),
      }),
    );
    render(
      <AuthProvider>
        <SubscriptionView result="basarili" />
      </AuthProvider>,
    );
    expect(await screen.findByText("Etkin")).toBeInTheDocument();
    expect(screen.getByText(/20.12.2026/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aboneliği iptal et" })).toBeInTheDocument();
    expect(screen.getByText(/Ödemeniz alındı/)).toBeInTheDocument();
  });

  it("oturum yoksa giriş ister", async () => {
    vi.stubGlobal("fetch", router({ "/payments/plan": () => json(200, PLAN), "/auth/me": () => json(401, { detail: "x" }) }));
    render(
      <AuthProvider>
        <SubscriptionView />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByRole("link", { name: "giriş yapın" })).toBeInTheDocument());
  });
});
