import { Compass } from "lucide-react";

import { FloatingLogos } from "@/components/brand/floating-logos";
import { FallbackPanel } from "@/components/system/fallback-panel";
import { getT } from "@/lib/i18n/server";

export default async function AccountNotFound() {
  const t = await getT();
  return (
    <div className="relative flex min-h-full flex-1 items-center justify-center overflow-hidden">
      <FloatingLogos />
      <FallbackPanel
        icon={Compass}
        title={t("errors.accountNotFoundTitle")}
        description={t("errors.accountNotFoundBody")}
      />
    </div>
  );
}
