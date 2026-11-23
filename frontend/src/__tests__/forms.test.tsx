import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { LoginForm } from "@/components/LoginForm";
import { ResetPasswordForm, VerifyEmail } from "@/components/PasswordForms";
import { RegisterForm } from "@/components/RegisterForm";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status });

describe("RegisterForm", () => {
  it("istemci tarafında şifre ve onay kontrolü yapar, sonra kaydeder", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(202, { mesaj: "Kayıt isteğiniz alındı." }));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<RegisterForm />);
    await user.type(screen.getByLabelText("E-posta"), "avukat@ornek.com");
    await user.type(screen.getByLabelText("Şifre"), "kisa");
    await user.click(screen.getByRole("button", { name: "Kayıt ol" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/en az 10/);
    expect(fetchMock).not.toHaveBeenCalled();

    await user.clear(screen.getByLabelText("Şifre"));
    await user.type(screen.getByLabelText("Şifre"), "guvenli-sifre-1");
    await user.type(screen.getByLabelText("Şifre (tekrar)"), "guvenli-sifre-1");
    await user.click(screen.getByRole("button", { name: "Kayıt ol" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/aydınlatma metnini/);

    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Kayıt ol" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Kayıt isteğiniz alındı."));
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body).toEqual({ email: "avukat@ornek.com", password: "guvenli-sifre-1", full_name: null });
  });
});

describe("LoginForm", () => {
  it("hatalı girişte sunucu mesajını gösterir", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(401, { detail: "E-posta adresi veya şifre hatalı" })));
    const user = userEvent.setup();
    render(<LoginForm />);
    await user.type(screen.getByLabelText("E-posta"), "avukat@ornek.com");
    await user.type(screen.getByLabelText("Şifre"), "yanlis-sifre-1");
    await user.click(screen.getByRole("button", { name: "Giriş yap" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("E-posta adresi veya şifre hatalı"));
    expect(push).not.toHaveBeenCalled();
  });

  it("doğrulanmamış hesapta yeniden gönderme seçeneği sunar", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce(json(403, { detail: "Giriş yapmadan önce e-posta adresinizi doğrulayın" }))
        .mockResolvedValueOnce(json(202, { mesaj: "Doğrulama bağlantısı gönderildi." })),
    );
    const user = userEvent.setup();
    render(<LoginForm />);
    await user.type(screen.getByLabelText("E-posta"), "avukat@ornek.com");
    await user.type(screen.getByLabelText("Şifre"), "guvenli-sifre-1");
    await user.click(screen.getByRole("button", { name: "Giriş yap" }));
    await user.click(await screen.findByRole("button", { name: /yeniden gönder/ }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Doğrulama bağlantısı gönderildi."));
  });

  it("başarılı girişte yönlendirir", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(200, { id: 1, email: "avukat@ornek.com", full_name: null, email_verified: true })));
    const user = userEvent.setup();
    render(<LoginForm next="/ara" />);
    await user.type(screen.getByLabelText("E-posta"), "avukat@ornek.com");
    await user.type(screen.getByLabelText("Şifre"), "guvenli-sifre-1");
    await user.click(screen.getByRole("button", { name: "Giriş yap" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/ara"));
  });
});

describe("e-posta bağlantıları", () => {
  it("jeton yoksa hata gösterir", () => {
    render(<ResetPasswordForm token={null} />);
    expect(screen.getByRole("alert")).toHaveTextContent(/Bağlantı eksik/);
  });

  it("doğrulama jetonunu yalnızca bir kez gönderir", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(200, { mesaj: "E-posta adresiniz doğrulandı." }));
    vi.stubGlobal("fetch", fetchMock);
    const { rerender } = render(<VerifyEmail token="jeton-1234567890" />);
    rerender(<VerifyEmail token="jeton-1234567890" />);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("doğrulandı"));
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
