"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, auth } from "@/lib/api";
import { validateEmail } from "@/lib/validation";
import { useAuth } from "./AuthProvider";
import { Alert, SubmitButton, TextField } from "./forms";

export function LoginForm({ next = "/ara" }: { next?: string }) {
  const router = useRouter();
  const { refresh } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [unverified, setUnverified] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  return (
    <form
      noValidate
      className="space-y-4"
      onSubmit={async (e) => {
        e.preventDefault();
        setError(null);
        setInfo(null);
        const emailError = validateEmail(email);
        if (emailError || !password) {
          setError(emailError ?? "Şifrenizi girin.");
          return;
        }
        setBusy(true);
        try {
          await auth.login(email, password);
          await refresh();
          router.push(next);
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Giriş yapılamadı.");
          setUnverified(err instanceof ApiError && err.status === 403);
        } finally {
          setBusy(false);
        }
      }}
    >
      {error && <Alert kind="error">{error}</Alert>}
      {info && <Alert kind="success">{info}</Alert>}
      <TextField id="email" label="E-posta" type="email" value={email} onChange={setEmail} autoComplete="email" required />
      <TextField id="password" label="Şifre" type="password" value={password} onChange={setPassword} autoComplete="current-password" required />
      <SubmitButton busy={busy}>Giriş yap</SubmitButton>
      {unverified && (
        <button
          type="button"
          className="w-full text-sm text-slate-700 underline underline-offset-4 dark:text-slate-300"
          onClick={async () => {
            const res = await auth.resendVerification(email).catch(() => null);
            setInfo(res?.mesaj ?? "Doğrulama bağlantısı gönderilemedi.");
          }}
        >
          Doğrulama bağlantısını yeniden gönder
        </button>
      )}
      <p className="text-right text-sm">
        <Link href="/sifremi-unuttum" className="text-slate-600 underline underline-offset-4 dark:text-slate-400">
          Şifremi unuttum
        </Link>
      </p>
    </form>
  );
}
