"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";

export function SiteHeader() {
  const { me, loading, logout } = useAuth();
  const router = useRouter();

  return (
    <header className="border-b border-slate-200 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
      <nav className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
        <Link href="/" className="text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          İçtihat Arama
        </Link>
        <div className="flex items-center gap-4 text-sm">
          <Link href="/ara" className="text-slate-700 hover:text-slate-950 dark:text-slate-300 dark:hover:text-white">
            Ara
          </Link>
          {loading ? null : me ? (
            <>
              <Link href="/abonelik" className="text-slate-700 hover:text-slate-950 dark:text-slate-300 dark:hover:text-white">
                Abonelik
              </Link>
              <span className="hidden text-slate-500 sm:inline" title={me.kullanici.email}>
                {me.kullanici.full_name || me.kullanici.email}
              </span>
              <button
                type="button"
                onClick={async () => {
                  await logout();
                  router.push("/");
                }}
                className="text-slate-700 hover:text-slate-950 dark:text-slate-300 dark:hover:text-white"
              >
                Çıkış
              </button>
            </>
          ) : (
            <>
              <Link href="/giris" className="text-slate-700 hover:text-slate-950 dark:text-slate-300 dark:hover:text-white">
                Giriş
              </Link>
              <Link href="/kayit" className="rounded-md bg-slate-900 px-3 py-1.5 font-medium text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white">
                Kayıt ol
              </Link>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}
