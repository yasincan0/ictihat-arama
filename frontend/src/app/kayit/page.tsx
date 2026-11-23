import Link from "next/link";
import { AuthCard } from "@/components/forms";
import { RegisterForm } from "@/components/RegisterForm";

export const metadata = { title: "Kayıt — İçtihat Arama" };

export default function Page() {
  return (
    <AuthCard title="Hesap oluştur" footer={<>Zaten hesabınız var mı? <Link href="/giris" className="font-medium underline underline-offset-4">Giriş yapın</Link></>}>
      <RegisterForm />
    </AuthCard>
  );
}
