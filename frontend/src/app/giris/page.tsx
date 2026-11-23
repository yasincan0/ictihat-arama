import Link from "next/link";
import { AuthCard } from "@/components/forms";
import { LoginForm } from "@/components/LoginForm";

export const metadata = { title: "Giriş — İçtihat Arama" };

export default function Page() {
  return (
    <AuthCard title="Giriş yap" footer={<>Hesabınız yok mu? <Link href="/kayit" className="font-medium underline underline-offset-4">Kayıt olun</Link></>}>
      <LoginForm />
    </AuthCard>
  );
}
