import { notFound } from "next/navigation";

import { IconsShowcase } from "./icons-showcase";

export default function DevIconsPage() {
  if (process.env.NODE_ENV !== "development") {
    notFound();
  }

  return <IconsShowcase />;
}
