import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Docker imajı için bağımsız (standalone) çıktı üretir.
  output: "standalone",
};

export default nextConfig;
