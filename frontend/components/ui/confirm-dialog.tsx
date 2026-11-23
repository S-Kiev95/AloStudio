"use client";

import { animate } from "animejs";
import { AlertTriangle, X } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n/provider";
import { NEON_EASE, prefersReducedMotion } from "@/lib/motion/neon-motion";

export interface ConfirmOptions {
  title?: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
}

export type ConfirmFn = (options: string | ConfirmOptions) => Promise<boolean>;

interface PendingConfirm {
  options: ConfirmOptions;
  resolve: (accepted: boolean) => void;
}

const ConfirmContext = createContext<ConfirmFn | null>(null);

/**
 * Shared confirmation modal following "The Hand-Bent Neon Room" design system
 * (replaces browser-native `window.confirm`). Focus starts on Cancel so
 * destructive actions cannot be triggered accidentally with Enter.
 */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  cancelLabel,
  destructive = true,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title?: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const t = useT();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const cancelBtnRef = useRef<HTMLButtonElement>(null);
  const id = useId();

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open) {
      if (!el.open) {
        if (typeof el.showModal === "function") el.showModal();
        else el.setAttribute("open", "");
      }
      cancelBtnRef.current?.focus();
      if (!prefersReducedMotion()) {
        const anim = animate(el, {
          opacity: [0, 1],
          scale: [0.97, 1],
          translateY: [6, 0],
          duration: 180,
          ease: NEON_EASE,
        });
        return () => {
          anim.cancel();
        };
      }
    } else if (el.open) {
      if (typeof el.close === "function") el.close();
      else el.removeAttribute("open");
    }
  }, [open]);

  if (!open) return null;

  return (
    <dialog
      ref={dialogRef}
      role="alertdialog"
      aria-modal="true"
      aria-labelledby={`${id}-title`}
      aria-describedby={`${id}-desc`}
      onCancel={(e) => {
        e.preventDefault();
        onCancel();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
      className="w-full max-w-md rounded-panel border border-glass bg-surface p-0 text-fg shadow-menu backdrop:bg-backdrop/75"
    >
      <div className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            {destructive ? (
              <span
                aria-hidden
                className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-control border border-danger/40 bg-danger/10 text-danger"
              >
                <AlertTriangle className="h-4 w-4" />
              </span>
            ) : null}
            <div className="min-w-0">
              <h2
                id={`${id}-title`}
                className="text-base font-medium leading-snug text-fg"
              >
                {title ?? t("actions.confirmTitle")}
              </h2>
              <p
                id={`${id}-desc`}
                className="mt-1.5 text-sm leading-relaxed text-fg-muted"
              >
                {message}
              </p>
            </div>
          </div>
          <button
            type="button"
            aria-label={t("actions.closeDialog")}
            onClick={onCancel}
            className="inline-flex h-11 w-11 -mr-2 -mt-2 shrink-0 items-center justify-center rounded-control text-fg-muted transition-colors hover:bg-hover-glass hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        <div className="flex justify-end gap-2 pt-1">
          <Button
            ref={cancelBtnRef}
            type="button"
            variant="secondary"
            size="sm"
            onClick={onCancel}
          >
            {cancelLabel ?? t("actions.cancel")}
          </Button>
          <Button
            type="button"
            variant={destructive ? "destructive" : "primary"}
            size="sm"
            onClick={onConfirm}
          >
            {confirmLabel ?? t("actions.confirm")}
          </Button>
        </div>
      </div>
    </dialog>
  );
}

export function ConfirmDialogProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<PendingConfirm | null>(null);
  const pendingRef = useRef<PendingConfirm | null>(null);
  pendingRef.current = pending;

  const confirm = useCallback<ConfirmFn>((input) => {
    const options: ConfirmOptions =
      typeof input === "string" ? { message: input } : input;
    return new Promise<boolean>((resolve) => {
      if (pendingRef.current) {
        pendingRef.current.resolve(false);
      }
      setPending({ options, resolve });
    });
  }, []);

  const settle = useCallback((accepted: boolean) => {
    setPending((curr) => {
      curr?.resolve(accepted);
      return null;
    });
  }, []);

  useEffect(() => {
    return () => {
      pendingRef.current?.resolve(false);
    };
  }, []);

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <ConfirmDialog
        open={pending !== null}
        title={pending?.options.title}
        message={pending?.options.message ?? ""}
        confirmLabel={pending?.options.confirmLabel}
        cancelLabel={pending?.options.cancelLabel}
        destructive={pending?.options.destructive ?? true}
        onConfirm={() => settle(true)}
        onCancel={() => settle(false)}
      />
    </ConfirmContext.Provider>
  );
}

/**
 * Returns an async `confirm(messageOrOptions)` function backed by the shared
 * neon `<ConfirmDialog>` mounted in `Providers`. Falls back to `window.confirm`
 * only when a component is mounted standalone outside `ConfirmDialogProvider`
 * (e.g. isolated unit tests).
 */
export function useConfirm(): ConfirmFn {
  const ctx = useContext(ConfirmContext);
  return useCallback<ConfirmFn>(
    (input) => {
      if (ctx) return ctx(input);
      const message = typeof input === "string" ? input : input.message;
      return Promise.resolve(
        typeof window !== "undefined" ? window.confirm(message) : false,
      );
    },
    [ctx],
  );
}
