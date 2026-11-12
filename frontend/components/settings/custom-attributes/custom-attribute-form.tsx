"use client";

import { Plus, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClassName } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  ATTRIBUTE_DISPLAY_TYPES,
  type AttributeDisplayType,
  type AttributeModel,
  type CustomAttribute,
  type CustomAttributeInput,
} from "@/lib/api/custom-attributes";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n/provider";
import { rich } from "@/lib/i18n/rich";

export function CustomAttributeForm({
  initial,
  submitting,
  onSubmit,
  onCancel,
}: {
  initial?: CustomAttribute;
  submitting?: boolean;
  onSubmit: (input: CustomAttributeInput) => Promise<void> | void;
  onCancel: () => void;
}) {
  const t = useT();
  const [displayName, setDisplayName] = useState(
    initial?.attribute_display_name ?? "",
  );
  const [description, setDescription] = useState(
    initial?.attribute_description ?? "",
  );
  const [displayType, setDisplayType] = useState<AttributeDisplayType>(
    initial?.attribute_display_type ?? "text",
  );
  const [model, setModel] = useState<AttributeModel>(
    initial?.attribute_model ?? "conversation_attribute",
  );
  const [regex, setRegex] = useState(initial?.regex_pattern ?? "");
  const [regexCue, setRegexCue] = useState(initial?.regex_cue ?? "");
  const [values, setValues] = useState<string[]>(
    initial?.attribute_values ?? [],
  );
  const [newValue, setNewValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  function addValue() {
    const v = newValue.trim();
    if (!v) return;
    if (values.includes(v)) return;
    setValues((prev) => [...prev, v]);
    setNewValue("");
  }

  async function submit() {
    setError(null);
    if (!displayName.trim())
      return setError(t("settingsAttrs.displayNameRequired"));
    const input: CustomAttributeInput = {
      attribute_display_name: displayName.trim(),
      attribute_display_type: displayType,
      attribute_model: model,
      attribute_description: description.trim() || null,
      regex_pattern: regex.trim() || null,
      regex_cue: regexCue.trim() || null,
      attribute_values: displayType === "list" ? values : [],
    };
    try {
      await onSubmit(input);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? t("settingsAttrs.saveFailed"),
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
        <Label htmlFor="ca-name" required>
          {t("settingsAttrs.displayName")}
        </Label>
        <Input
          id="ca-name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
        />
        {initial?.attribute_key ? (
          <p className="text-xs text-fg-muted">
            {rich(t("settingsAttrs.keyReadonly"), {
              key: <code>{initial.attribute_key}</code>,
            })}
          </p>
        ) : null}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="ca-type">{t("instagram.composer.typeLabel")}</Label>
          <select
            id="ca-type"
            className={selectClassName()}
            value={displayType}
            onChange={(e) =>
              setDisplayType(e.target.value as AttributeDisplayType)
            }
          >
            {ATTRIBUTE_DISPLAY_TYPES.map((dt) => (
              <option key={dt.value} value={dt.value}>
                {t(dt.label)}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="ca-model">{t("settingsAttrs.appliesTo")}</Label>
          <select
            id="ca-model"
            className={selectClassName()}
            value={model}
            onChange={(e) => setModel(e.target.value as AttributeModel)}
            disabled={Boolean(initial)}
          >
            <option value="conversation_attribute">{t("conversations.tabs.conversations")}</option>
            <option value="contact_attribute">{t("conversations.reports.contacts")}</option>
          </select>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="ca-desc">{t("products.form.description")}</Label>
        <Textarea
          id="ca-desc"
          rows={2}
          value={description ?? ""}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      {displayType === "text" ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="ca-regex">{t("settingsAttrs.regex")}</Label>
            <Input
              id="ca-regex"
              value={regex ?? ""}
              onChange={(e) => setRegex(e.target.value)}
              placeholder="^[A-Z]{3}-\d+$"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ca-cue">{t("settingsAttrs.regexHint")}</Label>
            <Input
              id="ca-cue"
              value={regexCue ?? ""}
              onChange={(e) => setRegexCue(e.target.value)}
              placeholder={t("settingsAttrs.regexHintPlaceholder")}
            />
          </div>
        </div>
      ) : null}

      {displayType === "list" ? (
        <div className="space-y-2">
          <Label>{t("settingsAttrs.values")}</Label>
          <div className="flex flex-wrap gap-1.5">
            {values.length === 0 ? (
              <p className="text-sm text-fg-muted">
                {t("settingsAttrs.noValues")}
              </p>
            ) : (
              values.map((v) => (
                <span
                  key={v}
                  className={cn(
                    "inline-flex items-center gap-1 rounded-sm border border-glass",
                    "bg-surface-2 px-2 py-0.5 text-xs text-fg",
                  )}
                >
                  {v}
                  <button
                    type="button"
                    aria-label={t("conversations.participants.remove", { name: v })}
                    onClick={() =>
                      setValues((prev) => prev.filter((x) => x !== v))
                    }
                    className="rounded-sm p-0.5 hover:text-danger"
                  >
                    <X className="h-3 w-3" aria-hidden />
                  </button>
                </span>
              ))
            )}
          </div>
          <div className="flex gap-2">
            <Input
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addValue();
                }
              }}
              placeholder={t("settingsAttrs.newValue")}
            />
            <Button type="button" variant="secondary" onClick={addValue}>
              <Plus className="h-4 w-4" aria-hidden />
              {t("instagram.add")}
            </Button>
          </div>
        </div>
      ) : null}

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {initial ? t("common.saveChanges") : t("settingsAttrs.create")}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          {t("actions.cancel")}
        </Button>
      </div>
    </div>
  );
}
