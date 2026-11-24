"use client";

import { ImagePlus, Sparkles, X } from "lucide-react";
import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  type GeneratedEmailDesign,
  useGenerateEmailDesign,
} from "@/lib/api/email-templates";
import type { CanvasKind } from "@/lib/inboxes/email-blocks";
import { useT } from "@/lib/i18n/provider";

const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(new Error("read_failed"));
    reader.readAsDataURL(file);
  });
}

/**
 * Modal dialog to ask the AI for an email template or signature from a text
 * description and/or an example screenshot. Never saves on its own: hands the
 * sanitized HTML back to the canvas so the user can review and edit it.
 */
export function AiDesignDialog({
  accountId,
  kind,
  open,
  onClose,
  onGenerated,
}: {
  accountId: string;
  kind: CanvasKind;
  open: boolean;
  onClose: () => void;
  onGenerated: (result: GeneratedEmailDesign) => void;
}) {
  const t = useT();
  const generate = useGenerateEmailDesign(accountId);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const [prompt, setPrompt] = useState("");
  const [imageDataUrl, setImageDataUrl] = useState<string | null>(null);
  const [imageName, setImageName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open) {
      if (!el.open) {
        if (typeof el.showModal === "function") {
          el.showModal();
        } else {
          el.setAttribute("open", "");
        }
      }
    } else if (el.open) {
      if (typeof el.close === "function") {
        el.close();
      } else {
        el.removeAttribute("open");
      }
    }
  }, [open]);

  async function onPickImage(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setError(null);
    if (file.size > MAX_IMAGE_BYTES) {
      setError(t("settingsEmailTpl.ai.imageTooLarge"));
      return;
    }
    try {
      const dataUrl = await readFileAsDataUrl(file);
      setImageDataUrl(dataUrl);
      setImageName(file.name);
    } catch {
      setError(t("settingsEmailTpl.uploadFailed"));
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!prompt.trim() && !imageDataUrl) {
      setError(t("settingsEmailTpl.ai.needPromptOrImage"));
      return;
    }
    try {
      const res = await generate.mutateAsync({
        prompt: prompt.trim(),
        image: imageDataUrl,
        kind,
      });
      onGenerated(res);
      setPrompt("");
      setImageDataUrl(null);
      setImageName(null);
      onClose();
    } catch (err) {
      setError(
        (err as { message?: string })?.message ?? t("settingsEmailTpl.ai.failed"),
      );
    }
  }

  if (!open) return null;

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      aria-labelledby="ai-email-design-title"
      className="max-h-[90dvh] w-full max-w-lg overflow-y-auto rounded-panel border border-glass bg-surface p-0 text-fg shadow-menu backdrop:bg-backdrop"
    >
      <form onSubmit={onSubmit} className="space-y-4 p-5">
        <div className="flex items-center justify-between border-b border-glass pb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-lit" aria-hidden />
            <h3 id="ai-email-design-title" className="text-lg font-medium text-fg">
              {t("settingsEmailTpl.ai.title")}
            </h3>
          </div>
          <button
            type="button"
            aria-label={t("actions.closeDialog")}
            onClick={onClose}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md text-fg-muted hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        <p className="text-xs text-fg-muted">
          {kind === "signature"
            ? t("settingsEmailTpl.ai.hintSignature")
            : t("settingsEmailTpl.ai.hintTemplate")}
        </p>

        {error ? (
          <p role="alert" className="rounded-md border border-danger bg-surface-2 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        ) : null}

        <div className="space-y-1.5">
          <Label htmlFor="ai-design-prompt">
            {t("settingsEmailTpl.ai.promptLabel")}
          </Label>
          <Textarea
            id="ai-design-prompt"
            rows={4}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={
              kind === "signature"
                ? t("settingsEmailTpl.ai.placeholderSignature")
                : t("settingsEmailTpl.ai.placeholderTemplate")
            }
          />
        </div>

        <div className="space-y-2">
          <Label>{t("settingsEmailTpl.ai.referenceImage")}</Label>
          <div className="flex flex-wrap items-center gap-2">
            <input
              ref={fileRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={onPickImage}
              className="hidden"
              aria-label={t("settingsEmailTpl.ai.uploadExample")}
            />
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() => fileRef.current?.click()}
            >
              <ImagePlus className="h-4 w-4" aria-hidden />
              {t("settingsEmailTpl.ai.uploadExample")}
            </Button>
            {imageName ? (
              <span className="inline-flex items-center gap-1.5 rounded-sm border border-glass bg-surface-2 px-2 py-1 text-xs text-fg">
                {imageName}
                <button
                  type="button"
                  aria-label={t("common.remove")}
                  onClick={() => {
                    setImageDataUrl(null);
                    setImageName(null);
                  }}
                  className="text-fg-muted hover:text-danger"
                >
                  <X className="h-3.5 w-3.5" aria-hidden />
                </button>
              </span>
            ) : null}
          </div>
          {imageDataUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={imageDataUrl}
              alt={t("settingsEmailTpl.ai.referenceAlt")}
              className="max-h-40 rounded-md border border-glass object-contain"
            />
          ) : null}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-glass pt-3">
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={generate.isPending}
          >
            {t("actions.cancel")}
          </Button>
          <Button
            type="submit"
            loading={generate.isPending}
            disabled={!prompt.trim() && !imageDataUrl}
          >
            <Sparkles className="h-4 w-4" aria-hidden />
            {t("settingsEmailTpl.ai.generate")}
          </Button>
        </div>
      </form>
    </dialog>
  );
}
