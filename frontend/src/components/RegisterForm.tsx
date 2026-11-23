"use client";

import Link from "next/link";
import { useState } from "react";
import { ApiError, auth } from "@/lib/api";
import { validateEmail, validatePassword } from "@/lib/validation";
import { Alert, SubmitButton, TextField } from "./forms";

export function RegisterForm() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [consent, setConsent] = useState(false);
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
        const problem =
          validateEmail(email) ??
          validatePassword(password) ??
          (password !== password2 ? "Şifreler aynı değil." : null) ??
          (!consent ? "Devam etmek için aydınlatma metnini okuduğunuzu ve kullanım koşullarını kabul ettiğinizi onaylayın." : null);
        setError(problem);
        if (problem) return;
        setBusy(true);
        try {
          const res = await auth.register(email, password, fullName.trim());
          setDone(res.mesaj);
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Kayıt tamamlanamadı.");
        } finally {
          setBusy(false);
        }
      }}
    >
      {error && <Alert kind="error">{error}</Alert>}
      <TextField id="full_name" label="Ad soyad (isteğe bağlı)" value={fullName} onChange={setFullName} autoComplete="name" />
      <TextField id="email" label="E-posta" type="email" value={email} onChange={setEmail} autoComplete="email" required />
      <TextField
        id="password"
        label="Şifre"
        type="password"
        value={password}
        onChange={setPassword}
        autoComplete="new-password"
        hint="En az 10 karakter; harf ve rakam içermeli."
        required
      />
      <TextField id="password2" label="Şifre (tekrar)" type="password" value={password2} onChange={setPassword2} autoComplete="new-password" required />
      <label className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1" />
        <span>
          <Link href="/aydinlatma-metni" target="_blank" className="underline underline-offset-2">Aydınlatma metnini</Link> okudum;{" "}
          <Link href="/kullanim-kosullari" target="_blank" className="underline underline-offset-2">kullanım koşullarını</Link> kabul ediyorum.
        </span>
      </label>
      <SubmitButton busy={busy}>Kayıt ol</SubmitButton>
    </form>
  );
}
