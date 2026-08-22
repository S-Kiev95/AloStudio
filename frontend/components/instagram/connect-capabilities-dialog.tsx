"use client";

import { AlertTriangle, X } from "lucide-react";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { type ConnectFlow, flowById } from "@/lib/inboxes/instagram-capabilities";

import { CapabilityList } from "./capability-list";

/**
 * What you get, shown before you commit to a way of connecting.
 *
 * The two flows differ in ways nobody could see until something failed
 * days later — one delivers DMs with their text, the other delivers
 * empty events; one can delete a post, the other cannot. Putting that in
 * front of the button is cheaper than finding out from a webhook.
 *
 * Native ``<dialog>`` so focus trap, ESC and the backdrop come from the
 * browser, matching MergeDialog.
 */
export function ConnectCapabilitiesDialog({
  flowId,
  open,
  onClose,
  onConfirm,
  pending = false,
}: {
  flowId: ConnectFlow["id"] | null;
  open: boolean;
  onClose: () => void;
  onConfirm: (flowId: ConnectFlow["id"]) => void;
  pending?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  if (flowId === null) return null;
  const flow = flowById(flowId);
  const limitations = flow.capabilities.filter((c) => c.level !== "yes");

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="connect-caps-title"
      className="w-full max-w-lg rounded-lg border border-border bg-surface p-0 text-fg shadow-xl backdrop:bg-black/50"
    >
      <div className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="connect-caps-title" className="text-lg font-semibold">
              Conectar por {flow.title}
            </h2>
            <p className="mt-1 text-sm text-fg-muted">{flow.summary}</p>
          </div>
          <button
            type="button"
            aria-label="Cerrar"
            onClick={onClose}
            className="rounded-md p-1 text-fg-muted hover:bg-surface-2"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        <CapabilityList capabilities={flow.capabilities} />

        <p className="rounded-md border border-border bg-surface-2 px-3 py-2 text-xs text-fg-muted">
          {flow.requirement}
        </p>

        {limitations.length > 0 ? (
          <p
            role="note"
            className="flex gap-2 rounded-md border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-warning"
          >
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
            <span>
              Podés cambiar de método más adelante reconectando la misma
              cuenta: se renueva el token y no se pierden conversaciones.
            </span>
          </p>
        ) : null}

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            Cancelar
          </Button>
          <Button onClick={() => onConfirm(flow.id)} loading={pending}>
            Continuar a Meta
          </Button>
        </div>
      </div>
    </dialog>
  );
}
