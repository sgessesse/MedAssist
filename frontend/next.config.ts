import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "https://medassist.us-east-2.elasticbeanstalk.com/api/:path*", // Note: HTTPS
      },
    ];
  },
};

export default nextConfig;
