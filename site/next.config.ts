import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // The page is regenerated hourly (for the latest commits) and reads the exported calls then.
  outputFileTracingIncludes: {
    "/": ["./public/calls/*.json"],
    "/render-film/[slug]": ["./public/calls/*.json"],
  },
  async headers() {
    return [
      {
        // Recorded calls and the film never change once exported.
        source: "/:dir(calls|film)/:file*",
        headers: [{ key: "Cache-Control", value: "public, max-age=31536000, immutable" }],
      },
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default config;
