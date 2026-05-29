import { Compass } from "lucide-react";

import { FallbackPanel } from "@/components/system/fallback-panel";

export default function AccountNotFound() {
  return (
    <FallbackPanel
      icon={Compass}
      title="No encontramos lo que buscás"
      description="La ruta no existe en esta cuenta."
    />
  );
}
