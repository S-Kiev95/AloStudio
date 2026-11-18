"use client";

import { ArrowDown, ArrowUp, Plus, Shuffle, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { useLabels } from "@/lib/api/labels";
import {
  LABEL_RULES_MAX,
  handoffProblemKey,
  targetFromValue,
  targetValue,
  useHandoffRules,
  useSaveHandoffRules,
} from "@/lib/api/handoff";
import { useT } from "@/lib/i18n/provider";
import { translateOr } from "@/lib/i18n/translate";

import { HandoffTargetSelect } from "./target-select";

type Row = { key: number; labelId: string; target: string };

/** Ajustes → Derivación (PLAN.agente-ia.md, 2a): who takes the
 *  conversations that a bot hands to the team, by label and for the rest. */
export function HandoffSettingsView({ accountId }: { accountId: string }) {
  const t = useT();
  const rules = useHandoffRules(accountId);
  const labels = useLabels(accountId);
  const save = useSaveHandoffRules(accountId);
  const nextKey = useRef(0);
  const [account, setAccount] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const data = rules.data;
    if (!data) return;
    setAccount(targetValue(data.account));
    setRows(
      data.labels.map((r) => ({
        key: nextKey.current++,
        labelId: String(r.label_id),
        target: targetValue(r),
      })),
    );
  }, [rules.data]);

  const aiAvailable = rules.data?.ai_available === true;
  const labelList = labels.data ?? [];

  function edit(next: Row[]) {
    setSaved(false);
    setRows(next);
  }

  function move(i: number, by: number) {
    const next = [...rows];
    const [row] = next.splice(i, 1);
    next.splice(i + by, 0, row);
    edit(next);
  }

  async function submit() {
    setSaved(false);
    try {
      await save.mutateAsync({
        account: targetFromValue(account),
        labels: rows
          .filter((r) => r.labelId)
          .map((r) => ({ label_id: Number(r.labelId), ...targetFromValue(r.target) })),
      });
      setSaved(true);
    } catch {
      // shown below from save.error
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Shuffle className="h-4 w-4 text-fg-muted" aria-hidden />
          {t("handoff.settings.title")}
        </CardTitle>
        <p className="mt-1 text-sm text-fg-muted">{t("handoff.settings.intro")}</p>
      </CardHeader>
      <CardContent className="space-y-5">
        {rules.isLoading ? (
          <p className="text-sm text-fg-muted">{t("common.loading")}</p>
        ) : rules.isError ? (
          <p role="alert" className="text-sm text-danger">
            {t("handoff.problems.loadFailed")}
          </p>
        ) : (
          <>
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium text-fg">
                {t("handoff.settings.labels")}
              </legend>
              <p className="text-xs text-fg-muted">{t("handoff.settings.labelsHint")}</p>
              {rows.length === 0 ? (
                <p className="text-sm text-fg-muted">{t("handoff.settings.noLabelRules")}</p>
              ) : (
                <ol className="space-y-2">
                  {rows.map((row, i) => (
                    <li key={row.key} className="flex flex-wrap items-center gap-2">
                      <Select
                        size="sm"
                        aria-label={t("handoff.settings.label", { n: i + 1 })}
                        value={row.labelId}
                        onChange={(e) =>
                          edit(rows.map((r, j) => (j === i ? { ...r, labelId: e.target.value } : r)))
                        }
                      >
                        <option value="">{t("handoff.settings.pickLabel")}</option>
                        {labelList.map((l) => (
                          <option
                            key={l.id}
                            value={String(l.id)}
                            disabled={rows.some((r, j) => j !== i && r.labelId === String(l.id))}
                          >
                            {l.title}
                          </option>
                        ))}
                      </Select>
                      <span className="text-xs text-fg-muted" aria-hidden>
                        →
                      </span>
                      <HandoffTargetSelect
                        size="sm"
                        accountId={accountId}
                        aiAvailable={aiAvailable}
                        emptyLabel={t("handoff.settings.pickTarget")}
                        aria-label={t("handoff.settings.target", { n: i + 1 })}
                        value={row.target}
                        onChange={(e) =>
                          edit(rows.map((r, j) => (j === i ? { ...r, target: e.target.value } : r)))
                        }
                      />
                      <div className="flex items-center">
                        <IconButton
                          label={t("handoff.settings.up", { n: i + 1 })}
                          disabled={i === 0}
                          onClick={() => move(i, -1)}
                        >
                          <ArrowUp className="h-4 w-4" aria-hidden />
                        </IconButton>
                        <IconButton
                          label={t("handoff.settings.down", { n: i + 1 })}
                          disabled={i === rows.length - 1}
                          onClick={() => move(i, 1)}
                        >
                          <ArrowDown className="h-4 w-4" aria-hidden />
                        </IconButton>
                        <IconButton
                          label={t("handoff.settings.remove", { n: i + 1 })}
                          danger
                          onClick={() => edit(rows.filter((_, j) => j !== i))}
                        >
                          <Trash2 className="h-4 w-4" aria-hidden />
                        </IconButton>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
              <Button
                variant="secondary"
                size="sm"
                disabled={rows.length >= LABEL_RULES_MAX || labelList.length === 0}
                onClick={() =>
                  edit([...rows, { key: nextKey.current++, labelId: "", target: "" }])
                }
              >
                <Plus className="h-4 w-4" aria-hidden />
                {t("handoff.settings.add")}
              </Button>
              {labels.isSuccess && labelList.length === 0 ? (
                <p className="text-xs text-fg-muted">{t("handoff.settings.noLabels")}</p>
              ) : null}
            </fieldset>

            <div className="space-y-1.5 border-t border-glass pt-4">
              <label htmlFor="handoff-account" className="block text-sm font-medium text-fg">
                {t("handoff.settings.account")}
              </label>
              <p className="text-xs text-fg-muted">{t("handoff.settings.accountHint")}</p>
              <HandoffTargetSelect
                id="handoff-account"
                className="max-w-xs"
                accountId={accountId}
                aiAvailable={aiAvailable}
                emptyLabel={t("handoff.nobody")}
                value={account}
                onChange={(e) => {
                  setSaved(false);
                  setAccount(e.target.value);
                }}
              />
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Button size="sm" onClick={() => void submit()} loading={save.isPending}>
                {t("handoff.settings.save")}
              </Button>
              {saved ? (
                <span role="status" className="text-sm text-success">
                  {t("handoff.settings.saved")}
                </span>
              ) : null}
              {save.error ? (
                <span role="alert" className="text-sm text-danger">
                  {translateOr(t, handoffProblemKey(save.error), t("handoff.problems.failed"))}
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
  onClick,
  disabled,
  danger,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className={
        danger
          ? "rounded-md p-1.5 text-fg-muted hover:bg-hover-glass hover:text-danger disabled:opacity-40"
          : "rounded-md p-1.5 text-fg-muted hover:bg-hover-glass hover:text-fg disabled:opacity-40"
      }
    >
      {children}
    </button>
  );
}
