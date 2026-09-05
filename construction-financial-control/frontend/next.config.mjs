/** @type {import('next').NextConfig} */
const API_TARGET = process.env.API_PROXY_TARGET || "http://localhost:8000";

const nextConfig = {
  // Same-origin proxy to the FastAPI backend: the browser only ever talks to
  // the Next server, so CORS stays locked down on the API side.
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${API_TARGET}/api/v1/:path*` }];
  },
};

export default nextConfig;
