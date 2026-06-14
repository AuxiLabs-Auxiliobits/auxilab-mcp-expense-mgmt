/** @type {import('next').NextConfig} */
// REFERENCE SCAFFOLD ONLY — see README.md.
const nextConfig = {
  reactStrictMode: true,
  // The portal talks to the FastAPI backend (NEXT_PUBLIC_API_BASE_URL) over REST/HTTPS.
  // In a real deployment, prefer a same-origin rewrite or APIM in front of the API
  // rather than calling the backend directly from the browser. Example (stubbed):
  //
  // async rewrites() {
  //   return [
  //     {
  //       source: "/api/backend/:path*",
  //       destination: `${process.env.NEXT_PUBLIC_API_BASE_URL}/:path*`,
  //     },
  //   ];
  // },
  experimental: {
    // AG Grid Enterprise / ECharts are heavy client-only deps; keep them out of RSC bundles.
    optimizePackageImports: ["lucide-react", "@tremor/react"],
  },
};

export default nextConfig;
