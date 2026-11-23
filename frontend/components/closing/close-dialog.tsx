"use client";

import { X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  type ClosingSettings,
  closingProblemKey,
  NOTE_MAX,
  useCloseConversation,
} from "@/lib/api/closing";
import { useT } from "@/lib/i18n/provider";
import { translateOr } from "@/lib/i18n/translate";
import { animateDialogIn } from "@/lib/motion/neon-motion";
import { cn } from "@/lib/utils";

/** Resolving a conversation from the panel, saying why (F17). */
export function CloseDialog({
  accountId,
  displayId,
  settings,
  open,
  onClose,
}: {
  accountId: string;
  displayId: number;
  settings: ClosingSettings;
  open: boolean;
  onClose: () => void;
}) {
  const t = useT();
  const ref = useRef<HTMLDialogElement>(null);
  const noteId = useId();
  const [category, setCategory] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const close = useCloseConversation(accountId, displayId);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open) {
      if (!el.open) el.showModal();
      return animateDialogIn(el);
    }
    if (el.open) el.close();
  }, [open]);

  useEffect(() => {
    if (open) {
      setCategory(null);
      setNote("");
      setProblem(null);
    }
  }, [open]);

  const missing = settings.required && category === null;

  async function submit() {
    setProblem(null);
    try {
      await close.mutateAsync({ category, note: note.trim() || null });
      onClose();
    } catch (err) {
      setProblem(closingProblemKey(err));
    }
  }

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby={`${noteId}-title`}
      className="w-full max-w-md rounded-panel border border-glass bg-surface p-0 text-fg shadow-menu backdrop:bg-backdrop/75"
    >
      <div className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <h2 id={`${noteId}-title`} className="text-lg font-medium text-fg">
            {t("closing.dialog.title")}
          </h2>
          <button
            type="button"
            aria-label={t("closing.dialog.cancel")}
            onClick={onClose}
            className="rounded-md p-1 text-fg-muted hover:bg-hover-glass hover:text-fg"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        <fieldset className="space-y-2">
          <legend className="mb-2 text-sm font-medium text-fg">
            {t("closing.dialog.question")}
          </legend>
          <div role="radiogroup" className="flex flex-wrap gap-2">
            {settings.categories.map((option) => {
              const chosen = category === option;
              return (
                <button
                  key={option}
                  type="button"
                  role="radio"
                  aria-checked={chosen}
                  onClick={() => setCategory(chosen ? null : option)}
                  className={cn(
                    "rounded-control border px-3 py-1.5 text-sm transition-colors",
                    chosen
                      ? "border-neon bg-neon/10 text-fg"
                      : "border-glass text-fg-muted hover:bg-hover-glass hover:text-fg",
                  )}
                >
                  {option}
                </button>
              );
            })}
          </div>
          {!settings.required ? (
            <p className="text-xs text-fg-muted">{t("closing.dialog.optional")}</p>
          ) : null}
        </fieldset>

        <div className="space-y-1.5">
          <Label htmlFor={noteId}>{t("closing.dialog.note")}</Label>
          <Textarea
            id={noteId}
            rows={3}
            value={note}
            maxLength={NOTE_MAX}
            placeholder={t("closing.dialog.notePlaceholder")}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>

        {problem ? (
          <p role="alert" className="text-sm text-danger">
            {translateOr(t, problem, t("closing.problems.failed"))}
          </p>
        ) : null}

        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            {t("closing.dialog.cancel")}
          </Button>
          <Button
            size="sm"
            disabled={missing}
            loading={close.isPending}
            onClick={() => void submit()}
          >
            {t("closing.dialog.resolve")}
          </Button>
        </div>
      </div>
    </dialog>
  );
}
