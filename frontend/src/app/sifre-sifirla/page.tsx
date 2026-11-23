import { AuthCard } from "@/components/forms";
import { ResetPasswordForm } from "@/components/PasswordForms";

export const metadata = { title: "Şifre sıfırla — İçtihat Arama" };

export default async function Page({ searchParams }: { searchParams: Promise<{ jeton?: string }> }) {
  const { jeton } = await searchParams;
  return (
    <AuthCard title="Yeni şifre belirleyin">
      <ResetPasswordForm token={jeton ?? null} />
    </AuthCard>
  );
}
