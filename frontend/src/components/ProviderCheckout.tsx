"use client";

import { useEffect, useRef } from "react";

/**
 * Ödeme sağlayıcısının döndürdüğü form içeriğini (HTML + script) sayfaya yerleştirir.
 * innerHTML ile eklenen <script> etiketleri çalışmadığı için yeniden oluşturulur.
 * İçerik yalnızca kendi arka ucumuzdan (sağlayıcı yanıtı) gelir; kullanıcı girdisi değildir.
 */
export function ProviderCheckout({ html }: { html: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = ref.current;
    if (!host) return;
    host.innerHTML = html;
    host.querySelectorAll("script").forEach((old) => {
      const s = document.createElement("script");
      for (const attr of Array.from(old.attributes)) s.setAttribute(attr.name, attr.value);
      s.text = old.text;
      old.replaceWith(s);
    });
    return () => {
      host.innerHTML = "";
    };
  }, [html]);

  return (
    <div>
      <div id="iyzipay-checkout-form" className="responsive" />
      <div ref={ref} data-testid="odeme-formu" />
    </div>
  );
}
