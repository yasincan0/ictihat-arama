import { AuthCard } from "@/components/forms";
import { VerifyEmail } from "@/components/PasswordForms";

export const metadata = { title: "E-posta doğrulama — İçtihat Arama" };

export default async function Page({ searchParams }: { searchParams: Promise<{ jeton?: string }> }) {
  const { jeton } = await searchParams;
  return (
    <AuthCard title="E-posta doğrulama">
      <VerifyEmail token={jeton ?? null} />
    </AuthCard>
  );
}
