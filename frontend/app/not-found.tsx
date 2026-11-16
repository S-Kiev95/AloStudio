import { Compass } from "lucide-react";

import { FloatingLogos } from "@/components/brand/floating-logos";
import { FallbackPanel } from "@/components/system/fallback-panel";
import { getT } from "@/lib/i18n/server";

export default async function NotFound() {
  const t = await getT();
  return (
    <div className="min-h-dvh bg-bg text-fg">
      <div className="relative flex min-h-dvh items-center justify-center overflow-hidden p-6">
        <FloatingLogos />
        <FallbackPanel
          icon={Compass}
          title={t("errors.notFoundTitle")}
          description={t("errors.notFoundBody")}
          primary={{ label: t("errors.goHome"), href: "/" }}
        />
      </div>
    </div>
  );
}
