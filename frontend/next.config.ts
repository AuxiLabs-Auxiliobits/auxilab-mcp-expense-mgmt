import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // TypeScript type-checking stays enabled during builds; ESLint is run
  // separately via `npm run lint` so a style warning never blocks a build.
  eslint: { ignoreDuringBuilds: true },
  images: {
    remotePatterns: [{ protocol: "https", hostname: "lh3.googleusercontent.com" }],
  },
};

export default nextConfig;
