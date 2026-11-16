import { Compass } from "lucide-react";

import { FallbackPanel } from "@/components/system/fallback-panel";
import { getT } from "@/lib/i18n/server";

export default async function HelpCenterNotFound() {
  const t = await getT();
  return (
    <FallbackPanel
      icon={Compass}
      title={t("hc.notFoundTitle")}
      description={t("hc.notFoundBody")}
    />
  );
}
