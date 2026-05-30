import type { MetadataRoute } from "next";

/**
 * Public crawl policy.
 *
 * /hc/* is the public Help Center — crawl it. Everything else (auth,
 * dashboard under /accounts, BFF under /api/backend) stays out of the
 * index since it's either user-specific or requires login.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/hc/"],
        disallow: ["/accounts/", "/api/", "/login", "/forgot-password", "/reset-password", "/confirm"],
      },
    ],
  };
}
