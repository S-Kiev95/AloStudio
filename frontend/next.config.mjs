/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The dashboard talks to the FastAPI backend through the same-origin
  // BFF proxy at /api/backend/* (see app/api/backend) so httpOnly auth
  // cookies are attached server-side and never exposed to the browser.
};

export default nextConfig;
