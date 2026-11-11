import { Compass } from "lucide-react";

import { FloatingLogos } from "@/components/brand/floating-logos";
import { FallbackPanel } from "@/components/system/fallback-panel";

export default function NotFound() {
  return (
    <div className="min-h-dvh bg-bg text-fg">
      <div className="relative flex min-h-dvh items-center justify-center overflow-hidden p-6">
        <FloatingLogos />
        <FallbackPanel
          icon={Compass}
          title="Página no encontrada"
          description="La URL no existe o el contenido ya no está disponible."
          primary={{ label: "Ir al inicio", href: "/" }}
        />
      </div>
    </div>
  );
}
