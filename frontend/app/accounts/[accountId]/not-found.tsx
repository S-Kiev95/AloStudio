import { Compass } from "lucide-react";

import { FloatingLogos } from "@/components/brand/floating-logos";
import { FallbackPanel } from "@/components/system/fallback-panel";

export default function AccountNotFound() {
  return (
    <div className="relative flex min-h-full flex-1 items-center justify-center overflow-hidden">
      <FloatingLogos />
      <FallbackPanel
        icon={Compass}
        title="No encontramos lo que buscás"
        description="La ruta no existe en esta cuenta."
      />
    </div>
  );
}
