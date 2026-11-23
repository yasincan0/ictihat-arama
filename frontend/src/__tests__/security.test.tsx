import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import AydinlatmaMetni from "@/app/aydinlatma-metni/page";
import KullanimKosullari from "@/app/kullanim-kosullari/page";
import { AccountView } from "@/components/AccountView";
import { AuthProvider } from "@/components/AuthProvider";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status });
const ME = {
  kullanici: { id: 1, email: "a@ornek.com", full_name: null, email_verified: true },
  kota: { sinirsiz: false, kullanilan: 1, hak: 3, kalan: 2, donem_baslangici: "2026-11-01T00:00:00Z" },
};

describe("hukuki taslak sayfalar", () => {
  it.each([
    ["aydınlatma metni", AydinlatmaMetni],
    ["kullanım koşulları", KullanimKosullari],
  ])("%s TASLAK uyarısı taşır", (_n, Page) => {
    render(<Page />);
    expect(screen.getByRole("note")).toHaveTextContent("TASLAK");
  });

  it("aydınlatma metni olay özetinin saklanmadığını ve ödeme bilgilerinin aktarımını belirtir", () => {
    render(<AydinlatmaMetni />);
    expect(screen.getByText(/olay özeti kalıcı olarak saklanmaz/)).toBeInTheDocument();
    expect(screen.getByText(/doğrudan ödeme kuruluşuna iletilir/)).toBeInTheDocument();
  });
});

describe("AccountView", () => {
  it("onay ve şifre olmadan hesabı silmez; onayla siler ve yönlendirir", async () => {
    const fetchMock = vi.fn((url: string) => {
      const path = new URL(url).pathname;
      if (path === "/auth/me") return Promise.resolve(json(200, ME));
      if (path === "/auth/delete-account") return Promise.resolve(json(200, { mesaj: "silindi" }));
      return Promise.resolve(json(404, {}));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <AccountView />
      </AuthProvider>,
    );
    expect(await screen.findByText("Bu ay 2 / 3 kaldı")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /kalıcı olarak sil/ }));
    expect(screen.getByRole("alert")).toHaveTextContent(/onaylayın/);
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/auth/delete-account"))).toBe(false);

    await user.type(screen.getByLabelText("Şifreniz"), "guvenli-sifre-1");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /kalıcı olarak sil/ }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/?hesap=silindi"));
  });
});
