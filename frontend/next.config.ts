import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // A static site in out/, served by the FastAPI backend from the same container.
  output: "export",
  // /system/ becomes system/index.html, which the backend's static server finds.
  trailingSlash: true,
  turbopack: {
    root: __dirname,
  },
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
