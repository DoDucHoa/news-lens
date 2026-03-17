import type { NextConfig } from "next";

function normalizeBaseUrl(input: string): string {
  return input.endsWith("/") ? input.slice(0, -1) : input;
}

const nextConfig: NextConfig = {
  /* config options here */
  reactCompiler: true,
  async rewrites() {
    const rawTarget =
      process.env.INTERNAL_API_URL ??
      process.env.API_PROXY_TARGET ??
      process.env.NEXT_PUBLIC_API_DIRECT_URL ??
      "http://localhost:8001";

    const backendTarget = normalizeBaseUrl(rawTarget);

    return [
      {
        source: "/api/:path*",
        destination: `${backendTarget}/:path*`,
      },
    ];
  },
};

export default nextConfig;
