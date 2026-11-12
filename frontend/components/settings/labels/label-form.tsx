"use client";

import { Check } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  LABEL_SWATCHES,
  type Label as LabelType,
  type LabelInput,
} from "@/lib/api/labels";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n/provider";

export function LabelForm({
  initial,
  submitting,
  onSubmit,
  onCancel,
}: {
  initial?: LabelType;
  submitting?: boolean;
  onSubmit: (input: LabelInput) => Promise<void> | void;
  onCancel: () => void;
}) {
  const t = useT();
  const [title, setTitle] = useState(initial?.title ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [color, setColor] = useState(
    initial?.color ?? LABEL_SWATCHES[0],
  );
  const [showOnSidebar, setShowOnSidebar] = useState(
    initial?.show_on_sidebar ?? true,
  );
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    if (!title.trim()) return setError(t("agenda.dialog.titleRequired"));
    try {
      await onSubmit({
        title: title.trim(),
        description: description.trim() || null,
        color: color || null,
        show_on_sidebar: showOnSidebar,
      });
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? t("settingsLabels.saveFailed"),
      );
    }
  }

  return (
    <div className="space-y-4">
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className="space-y-1.5">
        <Label htmlFor="l-title" required>
          {t("agenda.dialog.titleLabel")}
        </Label>
        <Input
          id="l-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={255}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="l-desc">{t("products.form.description")}</Label>
        <Textarea
          id="l-desc"
          rows={2}
          value={description ?? ""}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <Label>{t("helpCenter.color")}</Label>
        <div className="flex flex-wrap gap-2">
          {LABEL_SWATCHES.map((c) => {
            const on = c === color;
            return (
              <button
                key={c}
                type="button"
                aria-label={c}
                aria-pressed={on}
                onClick={() => setColor(c)}
                className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-full border-2",
                  on ? "border-fg" : "border-transparent hover:border-border",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                )}
                style={{ backgroundColor: c }}
              >
                {on ? <Check className="h-4 w-4 text-white" aria-hidden /> : null}
              </button>
            );
          })}
        </div>
      </div>

      <label className="flex items-center gap-2 text-sm text-fg">
        <input
          type="checkbox"
          checked={showOnSidebar}
          onChange={(e) => setShowOnSidebar(e.target.checked)}
        />
        {t("settingsLabels.showInSidebar")}
      </label>

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {initial ? t("common.saveChanges") : t("settingsLabels.create")}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          {t("actions.cancel")}
        </Button>
      </div>
    </div>
  );
}
