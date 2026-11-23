"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ApiError, auth } from "@/lib/api";
import { validateEmail, validatePassword } from "@/lib/validation";
import { Alert, SubmitButton, TextField } from "./forms";

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (done) return <Alert kind="success">{done}</Alert>;
  return (
    <form
      noValidate
      className="space-y-4"
      onSubmit={async (e) => {
        e.preventDefault();
        const problem = validateEmail(email);
        setError(problem);
        if (problem) return;
        setBusy(true);
        try {
          setDone((await auth.forgotPassword(email)).mesaj);
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "İstek gönderilemedi.");
        } finally {
          setBusy(false);
        }
      }}
    >
      {error && <Alert kind="error">{error}</Alert>}
      <TextField id="email" label="E-posta" type="email" value={email} onChange={setEmail} autoComplete="email" required />
      <SubmitButton busy={busy}>Sıfırlama bağlantısı gönder</SubmitButton>
    </form>
  );
}

export function ResetPasswordForm({ token }: { token: string | null }) {
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!token) return <Alert kind="error">Bağlantı eksik veya hatalı. E-postadaki bağlantıyı yeniden açın.</Alert>;
  if (done)
    return (
      <div className="space-y-4">
        <Alert kind="success">{done}</Alert>
        <Link href="/giris" className="block text-center text-sm font-medium underline underline-offset-4">
          Giriş yap
        </Link>
      </div>
    );

  return (
    <form
      noValidate
      className="space-y-4"
      onSubmit={async (e) => {
        e.preventDefault();
        const problem = validatePassword(password) ?? (password !== password2 ? "Şifreler aynı değil." : null);
        setError(problem);
        if (problem) return;
        setBusy(true);
        try {
          setDone((await auth.resetPassword(token, password)).mesaj);
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Şifre değiştirilemedi.");
        } finally {
          setBusy(false);
        }
      }}
    >
      {error && <Alert kind="error">{error}</Alert>}
      <TextField id="password" label="Yeni şifre" type="password" value={password} onChange={setPassword} autoComplete="new-password" hint="En az 10 karakter; harf ve rakam içermeli." required />
      <TextField id="password2" label="Yeni şifre (tekrar)" type="password" value={password2} onChange={setPassword2} autoComplete="new-password" required />
      <SubmitButton busy={busy}>Şifreyi değiştir</SubmitButton>
    </form>
  );
}

export function VerifyEmail({ token }: { token: string | null }) {
  const [state, setState] = useState<{ kind: "info" | "success" | "error"; text: string }>({
    kind: "info",
    text: "E-posta adresiniz doğrulanıyor…",
  });
  const sent = useRef(false);

  useEffect(() => {
    if (!token) {
      setState({ kind: "error", text: "Bağlantı eksik veya hatalı." });
      return;
    }
    if (sent.current) return; // jeton tek kullanımlık: React geliştirme modunda iki kez göndermeyi önle
    sent.current = true;
    auth
      .verifyEmail(token)
      .then((r) => setState({ kind: "success", text: r.mesaj }))
      .catch((err) => setState({ kind: "error", text: err instanceof ApiError ? err.message : "Doğrulama yapılamadı." }));
  }, [token]);

  return (
    <div className="space-y-4">
      <Alert kind={state.kind}>{state.text}</Alert>
      {state.kind === "success" && (
        <Link href="/giris" className="block text-center text-sm font-medium underline underline-offset-4">
          Giriş yap
        </Link>
      )}
    </div>
  );
}
