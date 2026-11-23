import type { NextConfig } from "next";

// Tüm sayfalara eklenen güvenlik başlıkları.
// Not: İçerik Güvenliği Politikası (CSP) iyzico ödeme formunun yüklediği alan adları
// sandbox'ta doğrulandıktan sonra eklenecek (bkz. docs/guvenlik.md).
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), interest-cohort=()" },
  ...(process.env.NODE_ENV === "production" && process.env.ENABLE_HSTS === "true"
    ? [{ key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" }]
    : []),
];

const nextConfig: NextConfig = {
  // Docker imajı için bağımsız (standalone) çıktı üretir.
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
