import { Compass } from "lucide-react";

import { FallbackPanel } from "@/components/system/fallback-panel";

export default function NotFound() {
  return (
    <div className="min-h-dvh bg-bg text-fg">
      <div className="flex min-h-dvh items-center justify-center p-6">
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
