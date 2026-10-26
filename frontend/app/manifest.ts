import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "AloStudio",
    short_name: "AloStudio",
    description: "AloStudio — Bandeja omnicanal, publicaciones y CRM",
    start_url: "/",
    display: "standalone",
    background_color: "#060912",
    theme_color: "#3d6bff",
    icons: [
      {
        src: "/brand/alostudio-icon-192.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        src: "/brand/alostudio-icon-512.png",
        sizes: "512x512",
        type: "image/png",
      },
    ],
  };
}
