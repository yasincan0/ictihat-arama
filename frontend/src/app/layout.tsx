import type { Metadata } from "next";
import { AuthProvider } from "@/components/AuthProvider";
import { SiteHeader } from "@/components/SiteHeader";
import "./globals.css";

export const metadata: Metadata = {
  title: "İçtihat Arama",
  description: "Davanızdaki olaya uygun içtihadı birleştirme kararlarını bulun.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="tr">
      <body className="flex min-h-screen flex-col antialiased">
        <AuthProvider>
          <SiteHeader />
          <main className="flex-1">{children}</main>
          <footer className="border-t border-slate-200 px-4 py-6 text-center text-xs text-slate-500 dark:border-slate-800">
            Sonuçlar hukuki görüş değildir; kararların künyesi ve metni resmî kaynaktan kontrol edilmelidir.
          </footer>
        </AuthProvider>
      </body>
    </html>
  );
}
