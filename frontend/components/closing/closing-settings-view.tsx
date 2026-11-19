"use client";

import { ClipboardCheck, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  CATEGORIES_MAX,
  CATEGORY_MAX,
  closingProblemKey,
  useClosingSettings,
  useSaveClosingSettings,
} from "@/lib/api/closing";
import { useT } from "@/lib/i18n/provider";
import { translateOr } from "@/lib/i18n/translate";

/** Ajustes → Notas de cierre (F17): ask why a conversation closes. */
export function ClosingSettingsView({ accountId }: { accountId: string }) {
  const t = useT();
  const settings = useClosingSettings(accountId);
  const save = useSaveClosingSettings(accountId);
  const [enabled, setEnabled] = useState(false);
  const [required, setRequired] = useState(false);
  const [categories, setCategories] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const data = settings.data;
    if (!data) return;
    setEnabled(data.enabled);
    setRequired(data.required);
    setCategories(data.categories);
  }, [settings.data]);

  function edited() {
    setSaved(false);
  }

  async function submit() {
    edited();
    try {
      await save.mutateAsync({ enabled, required, categories });
      setSaved(true);
    } catch {
      // shown below from save.error
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <ClipboardCheck className="h-4 w-4 text-fg-muted" aria-hidden />
          {t("closing.settings.title")}
        </CardTitle>
        <p className="mt-1 text-sm text-fg-muted">{t("closing.settings.intro")}</p>
      </CardHeader>
      <CardContent className="space-y-5">
        {settings.isLoading ? (
          <p className="text-sm text-fg-muted">{t("common.loading")}</p>
        ) : (
          <>
            <div className="space-y-3">
              <Check
                checked={enabled}
                onChange={() => {
                  edited();
                  setEnabled((v) => !v);
                }}
                label={t("closing.settings.enabled")}
                hint={t("closing.settings.enabledHint")}
              />
              <Check
                checked={required}
                disabled={!enabled}
                onChange={() => {
                  edited();
                  setRequired((v) => !v);
                }}
                label={t("closing.settings.required")}
                hint={t("closing.settings.requiredHint")}
              />
            </div>

            <fieldset className="space-y-2 border-t border-glass pt-4">
              <legend className="text-sm font-medium text-fg">
                {t("closing.settings.categories")}
              </legend>
              <p className="text-xs text-fg-muted">{t("closing.settings.categoriesHint")}</p>
              <ul className="space-y-2">
                {categories.map((category, i) => (
                  <li key={i} className="flex items-center gap-2">
                    <Input
                      aria-label={t("closing.settings.category", { n: i + 1 })}
                      value={category}
                      maxLength={CATEGORY_MAX}
                      onChange={(e) => {
                        edited();
                        const next = [...categories];
                        next[i] = e.target.value;
                        setCategories(next);
                      }}
                    />
                    <button
                      type="button"
                      aria-label={t("closing.settings.remove", { category: category || i + 1 })}
                      disabled={categories.length <= 1}
                      onClick={() => {
                        edited();
                        setCategories(categories.filter((_, j) => j !== i));
                      }}
                      className="rounded-md p-1.5 text-fg-muted hover:bg-hover-glass hover:text-danger disabled:opacity-40"
                    >
                      <Trash2 className="h-4 w-4" aria-hidden />
                    </button>
                  </li>
                ))}
              </ul>
              <Button
                variant="secondary"
                size="sm"
                disabled={categories.length >= CATEGORIES_MAX}
                onClick={() => {
                  edited();
                  setCategories([...categories, ""]);
                }}
              >
                <Plus className="h-4 w-4" aria-hidden />
                {t("closing.settings.add")}
              </Button>
            </fieldset>

            <div className="flex flex-wrap items-center gap-3">
              <Button size="sm" onClick={() => void submit()} loading={save.isPending}>
                {t("closing.settings.save")}
              </Button>
              {saved ? (
                <span role="status" className="text-sm text-success">
                  {t("closing.settings.saved")}
                </span>
              ) : null}
              {save.error ? (
                <span role="alert" className="text-sm text-danger">
                  {translateOr(t, closingProblemKey(save.error), t("closing.problems.failed"))}
                </span>
              ) : null}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function Check({
  checked,
  onChange,
  disabled,
  label,
  hint,
}: {
  checked: boolean;
  onChange: () => void;
  disabled?: boolean;
  label: string;
  hint: string;
}) {
  return (
    <label
      className="flex cursor-pointer items-start gap-3 aria-disabled:cursor-not-allowed aria-disabled:opacity-60"
      aria-disabled={disabled}
    >
      <input
        type="checkbox"
        className="mt-0.5 h-4 w-4 accent-neon"
        checked={checked}
        onChange={onChange}
        disabled={disabled}
      />
      <span>
        <span className="block text-sm font-medium text-fg">{label}</span>
        <span className="block text-xs text-fg-muted">{hint}</span>
      </span>
    </label>
  );
}
