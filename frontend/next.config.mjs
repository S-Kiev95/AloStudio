/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone server output — minimal runtime image for the Docker
  // recipe in DEPLOY.md. No effect on Vercel (which uses its own
  // adapter) or on `npm run dev`.
  output: "standalone",
  // The dashboard talks to the FastAPI backend through the same-origin
  // BFF proxy at /api/backend/* (see app/api/backend) so httpOnly auth
  // cookies are attached server-side and never exposed to the browser.
};

export default nextConfig;
