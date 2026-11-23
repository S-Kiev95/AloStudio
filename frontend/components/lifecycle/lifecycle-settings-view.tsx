"use client";

import { ArrowDown, ArrowUp, Plus, Route, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  DESCRIPTION_MAX,
  type LifecycleStage,
  lifecycleProblemKey,
  NAME_MAX,
  STAGES_MAX,
  useLifecycleSettings,
  useSaveLifecycleSettings,
} from "@/lib/api/lifecycle";
import { useT } from "@/lib/i18n/provider";
import { translateOr } from "@/lib/i18n/translate";

type Draft = Omit<LifecycleStage, "key"> & { key?: string };

/** Ajustes → Etapas del contacto (F17): from new lead to customer. */
export function LifecycleSettingsView({ accountId }: { accountId: string }) {
  const t = useT();
  const settings = useLifecycleSettings(accountId);
  const save = useSaveLifecycleSettings(accountId);
  const [enabled, setEnabled] = useState(false);
  const [stages, setStages] = useState<Draft[]>([]);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const data = settings.data;
    if (!data) return;
    setEnabled(data.enabled);
    setStages(data.stages);
  }, [settings.data]);

  function edit(next: Draft[]) {
    setSaved(false);
    setStages(next);
  }

  function update(i: number, patch: Partial<Draft>) {
    edit(
      stages.map((s, j) => {
        if (j === i) {
          const merged = { ...s, ...patch };
          // A lost stage cannot be the one new contacts start in.
          return merged.kind === "lost" ? { ...merged, default: false } : merged;
        }
        // Only one default.
        return patch.default ? { ...s, default: false } : s;
      }),
    );
  }

  function move(i: number, by: -1 | 1) {
    const j = i + by;
    if (j < 0 || j >= stages.length) return;
    const next = [...stages];
    [next[i], next[j]] = [next[j], next[i]];
    edit(next);
  }

  async function submit() {
    setSaved(false);
    try {
      await save.mutateAsync({ enabled, stages });
      setSaved(true);
    } catch {
      // shown below from save.error
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Route className="h-4 w-4 text-fg-muted" aria-hidden />
          {t("lifecycle.settings.title")}
        </CardTitle>
        <p className="mt-1 text-sm text-fg-muted">{t("lifecycle.settings.intro")}</p>
      </CardHeader>
      <CardContent className="space-y-5">
        {settings.isLoading ? (
          <p className="text-sm text-fg-muted">{t("common.loading")}</p>
        ) : (
          <>
            <label className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 accent-neon"
                checked={enabled}
                onChange={() => {
                  setSaved(false);
                  setEnabled((v) => !v);
                }}
              />
              <span>
                <span className="block text-sm font-medium text-fg">
                  {t("lifecycle.settings.enabled")}
                </span>
                <span className="block text-xs text-fg-muted">
                  {t("lifecycle.settings.enabledHint")}
                </span>
              </span>
            </label>

            <fieldset className="space-y-3 border-t border-glass pt-4">
              <legend className="text-sm font-medium text-fg">{t("lifecycle.stages")}</legend>
              <p className="text-xs text-fg-muted">{t("lifecycle.settings.stagesHint")}</p>
              <ul className="space-y-3">
                {stages.map((stage, i) => {
                  const n = i + 1;
                  return (
                    <li
                      key={stage.key ?? `new-${i}`}
                      className="space-y-2 rounded-md border border-glass p-3"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <Input
                          aria-label={t("lifecycle.settings.name", { n })}
                          className="min-w-[10rem] flex-1"
                          value={stage.name}
                          maxLength={NAME_MAX}
                          onChange={(e) => update(i, { name: e.target.value })}
                        />
                        <Select
                          aria-label={t("lifecycle.settings.kind", { n })}
                          className="w-40"
                          value={stage.kind}
                          onChange={(e) => update(i, { kind: e.target.value as Draft["kind"] })}
                        >
                          <option value="stage">{t("lifecycle.settings.kindStage")}</option>
                          <option value="lost">{t("lifecycle.settings.kindLost")}</option>
                        </Select>
                        <div className="flex gap-1">
                          <IconButton
                            label={t("lifecycle.settings.up", { name: stage.name || n })}
                            disabled={i === 0}
                            onClick={() => move(i, -1)}
                          >
                            <ArrowUp className="h-4 w-4" aria-hidden />
                          </IconButton>
                          <IconButton
                            label={t("lifecycle.settings.down", { name: stage.name || n })}
                            disabled={i === stages.length - 1}
                            onClick={() => move(i, 1)}
                          >
                            <ArrowDown className="h-4 w-4" aria-hidden />
                          </IconButton>
                          <IconButton
                            label={t("lifecycle.settings.remove", { name: stage.name || n })}
                            disabled={stages.length <= 1}
                            onClick={() => edit(stages.filter((_, j) => j !== i))}
                          >
                            <Trash2 className="h-4 w-4" aria-hidden />
                          </IconButton>
                        </div>
                      </div>
                      <Input
                        aria-label={t("lifecycle.settings.description", { n })}
                        placeholder={t("lifecycle.settings.descriptionPlaceholder")}
                        value={stage.description}
                        maxLength={DESCRIPTION_MAX}
                        onChange={(e) => update(i, { description: e.target.value })}
                      />
                      {stage.kind === "stage" ? (
                        <label className="flex cursor-pointer items-center gap-2 text-xs text-fg-muted">
                          <input
                            type="radio"
                            name="lifecycle-default"
                            className="h-3.5 w-3.5 accent-neon"
                            checked={stage.default}
                            onChange={() => update(i, { default: true })}
                          />
                          {t("lifecycle.settings.default")}
                        </label>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={stages.length >= STAGES_MAX}
                  onClick={() =>
                    edit([
                      ...stages,
                      { name: "", emoji: "", description: "", kind: "stage", default: false },
                    ])
                  }
                >
                  <Plus className="h-4 w-4" aria-hidden />
                  {t("lifecycle.settings.add")}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() =>
                    edit(stages.map((s) => (s.default ? { ...s, default: false } : s)))
                  }
                  disabled={!stages.some((s) => s.default)}
                >
                  {t("lifecycle.settings.noDefault")}
                </Button>
              </div>
            </fieldset>

            <div className="flex flex-wrap items-center gap-3">
              <Button size="sm" onClick={() => void submit()} loading={save.isPending}>
                {t("lifecycle.settings.save")}
              </Button>
              {saved ? (
                <span role="status" className="text-sm text-success">
                  {t("lifecycle.settings.saved")}
                </span>
              ) : null}
              {save.error ? (
                <span role="alert" className="text-sm text-danger">
                  {translateOr(t, lifecycleProblemKey(save.error), t("lifecycle.problems.failed"))}
                </span>
              ) : null}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function IconButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="rounded-md p-1.5 text-fg-muted hover:bg-hover-glass hover:text-fg disabled:opacity-40"
    >
      {children}
    </button>
  );
}
