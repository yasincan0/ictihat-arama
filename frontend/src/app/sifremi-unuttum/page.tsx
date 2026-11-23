import { AuthCard } from "@/components/forms";
import { ForgotPasswordForm } from "@/components/PasswordForms";

export const metadata = { title: "Şifremi unuttum — İçtihat Arama" };

export default function Page() {
  return (
    <AuthCard title="Şifremi unuttum">
      <ForgotPasswordForm />
    </AuthCard>
  );
}
