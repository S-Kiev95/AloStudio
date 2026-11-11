"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { WhatsApp } from "@/components/ui/brand-icons";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/errors";
import {
  useConnectWhatsappEmbeddedSignup,
  useWhatsappEmbeddedSignup,
} from "@/lib/api/inboxes";

const SDK_URL = "https://connect.facebook.net/es_LA/sdk.js";
const ALLOWED_ORIGINS = new Set([
  "https://www.facebook.com",
  "https://web.facebook.com",
]);

export type FBLoginResponse = {
  authResponse?: {
    code?: string;
  } | null;
};

export type FBSDK = {
  init: (params: {
    appId: string;
    version: string;
    xfbml: boolean;
  }) => void;
  login: (
    callback: (response: FBLoginResponse) => void,
    options: {
      config_id: string;
      response_type: "code";
      override_default_response_type: true;
      extras: { setup: Record<string, never>; sessionInfoVersion: "3" };
    },
  ) => void;
};

declare global {
  interface Window {
    FB?: FBSDK;
    fbAsyncInit?: () => void;
  }
}

function ensureFacebookSdk(): Promise<FBSDK> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("Sin ventana"));
  }
  let script = document.querySelector<HTMLScriptElement>(
    `script[src="${SDK_URL}"]`,
  );
  if (!script) {
    script = document.createElement("script");
    script.src = SDK_URL;
    script.async = true;
    script.defer = true;
    document.head.appendChild(script);
  }
  if (window.FB) {
    return Promise.resolve(window.FB);
  }
  return new Promise<FBSDK>((resolve, reject) => {
    const prev = window.fbAsyncInit;
    window.fbAsyncInit = () => {
      prev?.();
      if (window.FB) resolve(window.FB);
    };
    script!.addEventListener("load", () => {
      if (window.FB) resolve(window.FB);
    });
    script!.addEventListener("error", () => {
      reject(new Error("No se pudo cargar el SDK de Meta."));
    });
  });
}

type EmbeddedSignupMessage = {
  type?: string;
  event?: string;
  data?: {
    phone_number_id?: string;
    waba_id?: string;
    current_step?: string;
    error_message?: string;
  };
};

export function WhatsappEmbeddedSignup({
  accountId,
  onlyWhenReady = false,
  showManualHint = false,
}: {
  accountId: string;
  onlyWhenReady?: boolean;
  showManualHint?: boolean;
}) {
  const router = useRouter();
  const info = useWhatsappEmbeddedSignup(accountId);
  const connect = useConnectWhatsappEmbeddedSignup(accountId);

  const [starting, setStarting] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const codeRef = useRef<string | null>(null);
  const idsRef = useRef<{ waba_id: string; phone_number_id: string } | null>(
    null,
  );
  const completingRef = useRef(false);

  const tryComplete = useCallback(async () => {
    const code = codeRef.current;
    const ids = idsRef.current;
    if (!code || !ids || completingRef.current) return;
    completingRef.current = true;
    setStarting(false);
    setConnecting(true);
    setError(null);
    try {
      const result = await connect.mutateAsync({
        code,
        waba_id: ids.waba_id,
        phone_number_id: ids.phone_number_id,
      });
      router.push(`/accounts/${accountId}/settings/inboxes/${result.inbox.id}`);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "No se pudo conectar WhatsApp.",
      );
      codeRef.current = null;
      idsRef.current = null;
    } finally {
      setConnecting(false);
      completingRef.current = false;
    }
  }, [accountId, connect, router]);

  useEffect(() => {
    function onMessage(ev: MessageEvent) {
      if (!ALLOWED_ORIGINS.has(ev.origin)) return;
      let payload: unknown = ev.data;
      if (typeof payload === "string") {
        try {
          payload = JSON.parse(payload);
        } catch {
          return;
        }
      }
      if (!payload || typeof payload !== "object") return;
      const msg = payload as EmbeddedSignupMessage;
      if (msg.type !== "WA_EMBEDDED_SIGNUP") return;

      if (typeof msg.event === "string" && msg.event.startsWith("FINISH")) {
        const phoneNumberId = msg.data?.phone_number_id;
        const wabaId = msg.data?.waba_id;
        if (phoneNumberId && wabaId) {
          idsRef.current = {
            waba_id: String(wabaId),
            phone_number_id: String(phoneNumberId),
          };
          void tryComplete();
        }
        return;
      }

      if (msg.event === "CANCEL") {
        const step = msg.data?.current_step;
        setError(
          step
            ? `Cancelaste la conexión (${step}).`
            : "Cancelaste la conexión.",
        );
        setStarting(false);
        codeRef.current = null;
        idsRef.current = null;
        return;
      }

      if (msg.event === "ERROR") {
        setError(
          msg.data?.error_message || "No se pudo completar la conexión con Meta.",
        );
        setStarting(false);
        codeRef.current = null;
        idsRef.current = null;
      }
    }

    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [tryComplete]);

  if (onlyWhenReady && !info.data?.ready) {
    return null;
  }

  const ready = Boolean(info.data?.ready);
  const missing = info.data?.missing ?? [];
  const busy = starting || connecting || connect.isPending;

  async function start() {
    if (!info.data?.ready) return;
    setError(null);
    codeRef.current = null;
    idsRef.current = null;
    completingRef.current = false;
    setStarting(true);
    try {
      const FB = await ensureFacebookSdk();
      FB.init({
        appId: info.data.app_id,
        version: info.data.graph_api_version,
        xfbml: false,
      });
      FB.login(
        (response) => {
          const code = response?.authResponse?.code;
          if (code) {
            codeRef.current = code;
            void tryComplete();
          } else {
            setStarting(false);
          }
        },
        {
          config_id: info.data.config_id,
          response_type: "code",
          override_default_response_type: true,
          extras: { setup: {}, sessionInfoVersion: "3" },
        },
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "No se pudo iniciar la conexión con Meta.",
      );
      setStarting(false);
    }
  }

  return (
    <div className="space-y-3 rounded-md border border-glass bg-surface p-5">
      {error ? (
        <p
          role="alert"
          className="rounded-control border border-danger bg-surface-2 px-3 py-2 text-sm text-danger"
        >
          {error}
        </p>
      ) : null}

      {info.data && !info.data.ready ? (
        <p
          role="status"
          className="rounded-control border border-glass bg-surface-2 px-3 py-2 text-sm text-fg-muted"
        >
          Falta configurar en Ajustes → Instalación: {missing.join(", ")}
        </p>
      ) : null}

      <div className="space-y-2">
        <p className="text-sm text-fg-muted">
          Conectá tu número de WhatsApp Business desde Meta. La bandeja queda
          lista automáticamente.
        </p>
        <Button
          type="button"
          disabled={!ready || busy}
          loading={busy}
          onClick={() => void start()}
        >
          <WhatsApp mono className="h-4 w-4" aria-hidden />
          {busy ? "Conectando…" : "Conectar WhatsApp"}
        </Button>
      </div>

      {showManualHint ? (
        <p className="border-t border-glass pt-3 text-xs text-fg-muted">
          También podés cargar los datos a mano en el formulario de abajo.
        </p>
      ) : null}
    </div>
  );
}
