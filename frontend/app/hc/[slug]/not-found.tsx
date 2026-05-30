import { Compass } from "lucide-react";

import { FallbackPanel } from "@/components/system/fallback-panel";

export default function HelpCenterNotFound() {
  return (
    <FallbackPanel
      icon={Compass}
      title="No encontramos este artículo"
      description="Es posible que ya no esté publicado o que el enlace haya cambiado."
    />
  );
}
