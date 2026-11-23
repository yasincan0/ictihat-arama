import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "İçtihat Arama",
  description: "Davanızdaki olaya uygun içtihadı birleştirme kararlarını bulun.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="tr">
      <body className="antialiased">{children}</body>
    </html>
  );
}
