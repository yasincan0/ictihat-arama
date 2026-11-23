"use client";

// Giriş/kayıt sayfalarında ortak kullanılan form parçaları.

export function AuthCard({ title, children, footer }: { title: string; children: React.ReactNode; footer?: React.ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-md px-4 py-12">
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">{title}</h1>
        <div className="mt-6">{children}</div>
      </div>
      {footer && <div className="mt-4 text-center text-sm text-slate-600 dark:text-slate-400">{footer}</div>}
    </div>
  );
}

export function TextField(props: {
  id: string;
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
  hint?: string;
  required?: boolean;
}) {
  return (
    <div>
      <label htmlFor={props.id} className="block text-sm font-medium text-slate-800 dark:text-slate-200">
        {props.label}
      </label>
      <input
        id={props.id}
        type={props.type ?? "text"}
        value={props.value}
        required={props.required}
        autoComplete={props.autoComplete}
        onChange={(e) => props.onChange(e.target.value)}
        className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-base text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-300 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
      />
      {props.hint && <p className="mt-1 text-xs text-slate-500">{props.hint}</p>}
    </div>
  );
}

export function SubmitButton({ busy, children }: { busy?: boolean; children: React.ReactNode }) {
  return (
    <button
      type="submit"
      disabled={busy}
      className="w-full rounded-md bg-slate-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-60 dark:bg-slate-100 dark:text-slate-900"
    >
      {busy ? "Lütfen bekleyin…" : children}
    </button>
  );
}

export function Alert({ kind, children }: { kind: "error" | "success" | "info"; children: React.ReactNode }) {
  const styles = {
    error: "bg-red-50 text-red-800 ring-red-200 dark:bg-red-950 dark:text-red-200 dark:ring-red-800",
    success: "bg-emerald-50 text-emerald-800 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-200 dark:ring-emerald-800",
    info: "bg-slate-50 text-slate-800 ring-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700",
  }[kind];
  return (
    <div role={kind === "error" ? "alert" : "status"} className={`rounded-md p-3 text-sm ring-1 ${styles}`}>
      {children}
    </div>
  );
}
