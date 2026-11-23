"use client";

import { useState } from "react";
import { QUERY_MAX, validateQuery } from "@/lib/validation";

export function SearchForm({ onSearch, busy }: { onSearch: (q: string) => void; busy?: boolean }) {
  const [text, setText] = useState("");
  const [touched, setTouched] = useState(false);
  const error = validateQuery(text);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        setTouched(true);
        if (!error) onSearch(text.trim());
      }}
      className="space-y-3"
    >
      <label htmlFor="olay" className="block text-sm font-medium text-slate-900 dark:text-slate-100">
        Davanızdaki olayı anlatın
      </label>
      <textarea
        id="olay"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => setTouched(true)}
        rows={8}
        maxLength={QUERY_MAX}
        placeholder="Örn. Müvekkilimin işyerine belediye mühür vurdu, kendisine önceden bir bildirim yapılmadı…"
        className="w-full rounded-lg border border-slate-300 bg-white p-3 text-base text-slate-900 shadow-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        aria-invalid={touched && !!error}
        aria-describedby="olay-yardim"
      />
      <div id="olay-yardim" className="flex flex-wrap justify-between gap-2 text-xs text-slate-500">
        <span>Olay özetiniz kaydedilmez; yalnızca bu arama için kullanılır. Kişisel veri yazmamaya özen gösterin.</span>
        <span>
          {text.length}/{QUERY_MAX}
        </span>
      </div>
      {touched && error && (
        <p role="alert" className="text-sm text-red-700 dark:text-red-400">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={busy}
        className="rounded-md bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-60 dark:bg-slate-100 dark:text-slate-900"
      >
        {busy ? "Aranıyor…" : "Uygun kararları bul"}
      </button>
    </form>
  );
}
