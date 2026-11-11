"use client";

import { Volume2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  isNotificationSoundOn,
  playNotificationSound,
  setNotificationSoundOn,
} from "@/lib/notification-sound";

/**
 * Sound on this device when a notification arrives (a handoff from the
 * bot, an assignment…). Stored per device, on by default.
 */
export function SoundToggle() {
  const [on, setOn] = useState(true);

  useEffect(() => {
    setOn(isNotificationSoundOn());
  }, []);

  return (
    <div className="flex flex-wrap items-center gap-3">
      <label className="flex cursor-pointer items-center gap-2.5 text-sm text-fg">
        <input
          type="checkbox"
          checked={on}
          onChange={() => {
            const next = !on;
            setOn(next);
            setNotificationSoundOn(next);
          }}
          className="h-4 w-4 cursor-pointer rounded border-glass accent-neon"
        />
        Sonido al recibir una notificación
      </label>
      <Button
        variant="secondary"
        size="sm"
        onClick={() => playNotificationSound({ force: true })}
      >
        <Volume2 className="h-4 w-4" aria-hidden /> Probar
      </Button>
    </div>
  );
}
