"use client";

import { Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  type DecisionProvider,
  type DecisionQuestion,
  PRIORITY_BY_URGENCY,
  TEAM_QUESTION,
  URGENCY_QUESTION,
  useDecisionReport,
  useDecisionSettings,
  useNextToLabel,
  useSaveDecisionSettings,
  useSaveLabels,
} from "@/lib/api/decisions";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import { type MessageKey, translateOr } from "@/lib/i18n/translate";
import { cn } from "@/lib/utils";

type Tab = "setup" | "label" | "results";

function problemKey(err: unknown): string {
  const code = (err as { body?: { code?: unknown } })?.body?.code;
  if (typeof code === "string" && code.startsWith("decisions.")) {
    return `decisions.problems.${code.slice(10)}`;
  }
  return "decisions.problems.failed";
}

/** The question's title in the reader's language for the built-in ones. */
function useQuestionTitle() {
  const t = useT();
  return (q: { key: string; instructions: string }) =>
    translateOr(t, `decisions.questionNames.${q.key}`, q.instructions);
}

/**
 * Ajustes → Clasificación (F10): the decisions service (Jev now, Laya later)
 * reads each conversation and picks intent, sentiment, urgency and team. In
 * shadow mode it only stores and measures; people label conversations
 * without seeing its answer, which is how it is measured — and, later, what
 * Laya learns from (Jev's own answers may not train another model).
 */
export function DecisionsView({ accountId }: { accountId: string }) {
  const t = useT();
  const [tab, setTab] = useState<Tab>("setup");
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-fg">{t("decisions.title")}</h2>
        <p className="mt-1 max-w-3xl text-sm text-fg-muted">{t("decisions.intro")}</p>
      </div>
      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList>
          <TabsTrigger value="setup">{t("decisions.tabs.setup")}</TabsTrigger>
          <TabsTrigger value="label">{t("decisions.tabs.label")}</TabsTrigger>
          <TabsTrigger value="results">{t("decisions.tabs.results")}</TabsTrigger>
        </TabsList>
      </Tabs>
      {tab === "setup" ? <Setup accountId={accountId} /> : null}
      {tab === "label" ? <Labeling accountId={accountId} /> : null}
      {tab === "results" ? <Results accountId={accountId} /> : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------
function Setup({ accountId }: { accountId: string }) {
  const t = useT();
  const title = useQuestionTitle();
  const settings = useDecisionSettings(accountId);
  const save = useSaveDecisionSettings(accountId);
  const [enabled, setEnabled] = useState(false);
  const [provider, setProvider] = useState<DecisionProvider>("api");
  const [context, setContext] = useState("");
  const [applyPriority, setApplyPriority] = useState(false);
  const [questions, setQuestions] = useState<DecisionQuestion[]>([]);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!settings.data) return;
    setEnabled(settings.data.enabled);
    setProvider(settings.data.provider ?? "api");
    setContext(settings.data.context ?? "");
    setApplyPriority(settings.data.apply_priority ?? false);
    setQuestions(settings.data.questions);
  }, [settings.data]);

  function change(index: number, next: Partial<DecisionQuestion>) {
    setSaved(false);
    setQuestions((qs) => qs.map((q, i) => (i === index ? { ...q, ...next } : q)));
  }

  async function submit() {
    setSaved(false);
    try {
      await save.mutateAsync({
        enabled,
        provider,
        context,
        apply_priority: applyPriority,
        // Options without text are dropped; the team's come from the teams.
        questions: questions.map((q) =>
          q.key === TEAM_QUESTION
            ? { ...q, options: [] }
            : { ...q, options: q.options.filter((o) => o.description.trim()) },
        ),
      });
      setSaved(true);
    } catch {
      // shown below from save.error
    }
  }

  // The automatic priority needs the urgency question on, with options it
  // can turn into a priority (baja, media, alta, urgente).
  const urgency = questions.find((q) => q.key === URGENCY_QUESTION);
  const priorityReady = Boolean(
    urgency?.enabled && urgency.options.some((o) => PRIORITY_BY_URGENCY[o.key]),
  );

  if (settings.isLoading) return <p className="text-sm text-fg-muted">{t("decisions.loading")}</p>;
  if (settings.error || !settings.data) {
    return (
      <p role="alert" className="text-sm text-danger">
        {translateOr(t, problemKey(settings.error), t("decisions.problems.failed"))}
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {!(settings.data.providers?.[provider] ?? settings.data.configured) ? (
        <p role="status" className="rounded-panel border border-warning bg-surface-2 p-3 text-sm text-warning">
          {provider === "local" ? t("decisions.notConfiguredLocal") : t("decisions.notConfigured")}{" "}
          <Link
            href={`/accounts/${accountId}/settings/installation`}
            className="text-lit underline-offset-2 hover:underline"
          >
            {t("decisions.installationLink")}
          </Link>
        </p>
      ) : null}
      <Card>
        <CardContent className="space-y-2 pt-4">
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
              <span className="block text-sm font-medium text-fg">{t("decisions.shadow")}</span>
              <span className="block text-xs text-fg-muted">
                {t("decisions.shadowHint", {
                  model: settings.data.models?.[provider] ?? settings.data.model,
                })}
              </span>
            </span>
          </label>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("decisions.who")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div role="radiogroup" aria-label={t("decisions.who")} className="space-y-2">
            {(["api", "local"] as const).map((p) => (
              <label key={p} className="flex cursor-pointer items-start gap-3">
                <input
                  type="radio"
                  name="decisions-provider"
                  className="mt-0.5 h-4 w-4 accent-neon"
                  checked={provider === p}
                  onChange={() => {
                    setSaved(false);
                    setProvider(p);
                  }}
                />
                <span>
                  <span className="block text-sm font-medium text-fg">
                    {p === "api" ? t("decisions.providerApi") : t("decisions.providerLocal")}
                    {settings.data?.providers && !settings.data.providers[p] ? (
                      <span className="ml-2 text-xs font-normal text-warning">
                        {t("decisions.unavailable")}
                      </span>
                    ) : null}
                  </span>
                  <span className="block text-xs text-fg-muted">
                    {p === "api" ? t("decisions.providerApiHint") : t("decisions.providerLocalHint")}
                  </span>
                </span>
              </label>
            ))}
          </div>
          {provider === "local" ? (
            <div className="space-y-1">
              <label className="text-xs font-medium text-fg-muted" htmlFor="decisions-context">
                {t("decisions.context")}
              </label>
              <Textarea
                id="decisions-context"
                rows={4}
                maxLength={2000}
                value={context}
                onChange={(e) => {
                  setSaved(false);
                  setContext(e.target.value);
                }}
              />
              <p className="text-xs text-fg-muted">{t("decisions.contextHint")}</p>
            </div>
          ) : null}
          <label className="flex cursor-pointer items-start gap-3 border-t border-glass pt-3">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 accent-neon"
              checked={applyPriority}
              onChange={() => {
                setSaved(false);
                setApplyPriority((v) => !v);
              }}
            />
            <span>
              <span className="block text-sm font-medium text-fg">{t("decisions.applyPriority")}</span>
              <span className="block text-xs text-fg-muted">{t("decisions.applyPriorityHint")}</span>
              {applyPriority && !priorityReady ? (
                <span role="status" className="mt-1 block text-xs text-warning">
                  {t("decisions.priorityNotReady")}
                </span>
              ) : null}
            </span>
          </label>
        </CardContent>
      </Card>

      {questions.map((q, index) => (
        <Card key={q.key}>
          <CardHeader>
            <CardTitle className="flex items-center gap-3 text-base">
              <input
                type="checkbox"
                className="h-4 w-4 accent-neon"
                checked={q.enabled}
                onChange={() => change(index, { enabled: !q.enabled })}
                aria-label={t("decisions.askQuestion", { question: title(q) })}
              />
              {title(q)}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-fg-muted" htmlFor={`instr-${q.key}`}>
                {t("decisions.instructions")}
              </label>
              <Input
                id={`instr-${q.key}`}
                value={q.instructions}
                maxLength={300}
                onChange={(e) => change(index, { instructions: e.target.value })}
              />
            </div>
            {q.key === TEAM_QUESTION ? (
              <p className="text-xs text-fg-muted">
                {q.options.length
                  ? t("decisions.teamOptions", {
                      teams: q.options.map((o) => o.description).join(" · "),
                    })
                  : t("decisions.noTeams")}
              </p>
            ) : (
              <div className="space-y-2">
                <p className="text-xs font-medium text-fg-muted">{t("decisions.options")}</p>
                {q.options.map((o, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Input
                      aria-label={t("decisions.optionLabel", { n: i + 1 })}
                      value={o.description}
                      maxLength={300}
                      onChange={(e) =>
                        change(index, {
                          options: q.options.map((x, j) =>
                            j === i ? { ...x, description: e.target.value } : x,
                          ),
                        })
                      }
                    />
                    {q.key === URGENCY_QUESTION && PRIORITY_BY_URGENCY[o.key] ? (
                      <span className="shrink-0 text-xs text-fg-muted">
                        {t("decisions.setsPriority", {
                          level: t(`conversations.priority.${PRIORITY_BY_URGENCY[o.key]}` as MessageKey),
                        })}
                      </span>
                    ) : null}
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={t("decisions.removeOption")}
                      disabled={q.options.length <= 2}
                      onClick={() => change(index, { options: q.options.filter((_, j) => j !== i) })}
                    >
                      <Trash2 className="h-4 w-4" aria-hidden />
                    </Button>
                  </div>
                ))}
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={q.options.length >= 12}
                  onClick={() =>
                    change(index, { options: [...q.options, { key: "", description: "" }] })
                  }
                >
                  <Plus className="h-4 w-4" aria-hidden />
                  {t("decisions.addOption")}
                </Button>
                <p className="text-xs text-fg-muted">{t("decisions.optionsHint")}</p>
              </div>
            )}
          </CardContent>
        </Card>
      ))}

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={() => void submit()} loading={save.isPending}>
          {t("decisions.save")}
        </Button>
        {saved ? (
          <span role="status" className="text-sm text-success">
            {t("decisions.saved")}
          </span>
        ) : null}
        {save.error ? (
          <span role="alert" className="text-sm text-danger">
            {translateOr(t, problemKey(save.error), t("decisions.problems.failed"))}
          </span>
        ) : null}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Labeling, blind
// ---------------------------------------------------------------------------
function Labeling({ accountId }: { accountId: string }) {
  const t = useT();
  const title = useQuestionTitle();
  const [skip, setSkip] = useState<number[]>([]);
  const next = useNextToLabel(accountId, skip);
  const save = useSaveLabels(accountId);
  const [picked, setPicked] = useState<Record<string, string>>({});
  const item = next.data;

  useEffect(() => {
    setPicked(item?.answered ?? {});
  }, [item?.conversation_id, item?.answered]);

  if (next.isLoading) return <p className="text-sm text-fg-muted">{t("decisions.loading")}</p>;
  if (!item) {
    return <p className="text-sm text-fg-muted">{t("decisions.nothingToLabel")}</p>;
  }
  const complete = item.questions.every((q) => picked[q.key]);

  async function submit() {
    if (!item) return;
    try {
      await save.mutateAsync({ conversation_id: item.conversation_id, answers: picked });
    } catch {
      // shown below
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-fg-muted">{t("decisions.labelHint")}</p>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            <Link
              href={`/accounts/${accountId}/conversations/${item.conversation_id}`}
              className="text-lit underline-offset-2 hover:underline"
            >
              #{item.conversation_id}
            </Link>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="max-h-80 overflow-y-auto whitespace-pre-wrap break-words font-sans text-sm text-fg">
            {item.text}
          </pre>
        </CardContent>
      </Card>
      {item.questions.map((q) => (
        <fieldset key={q.key} className="space-y-2">
          <legend className="text-sm font-medium text-fg">{title(q)}</legend>
          <div className="flex flex-wrap gap-2">
            {q.options.map((o) => (
              <button
                key={o.key}
                type="button"
                aria-pressed={picked[q.key] === o.key}
                onClick={() => setPicked((p) => ({ ...p, [q.key]: o.key }))}
                className={cn(
                  "rounded-control border px-3 py-1.5 text-left text-sm transition-colors",
                  picked[q.key] === o.key
                    ? "border-neon bg-hover-glass text-fg"
                    : "border-glass text-fg-muted hover:text-fg",
                )}
              >
                {o.description}
              </button>
            ))}
          </div>
        </fieldset>
      ))}
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={() => void submit()} disabled={!complete} loading={save.isPending}>
          {t("decisions.saveAndNext")}
        </Button>
        <Button variant="ghost" onClick={() => setSkip((s) => [...s, item.conversation_id])}>
          {t("decisions.skip")}
        </Button>
        {save.error ? (
          <span role="alert" className="text-sm text-danger">
            {translateOr(t, problemKey(save.error), t("decisions.problems.failed"))}
          </span>
        ) : null}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Results
// ---------------------------------------------------------------------------
function Results({ accountId }: { accountId: string }) {
  const t = useT();
  const tag = useIntlTag();
  const title = useQuestionTitle();
  const report = useDecisionReport(accountId);
  const data = report.data;
  if (report.isLoading) return <p className="text-sm text-fg-muted">{t("decisions.loading")}</p>;
  if (!data) return null;
  const pct = (n: number | null) =>
    n === null ? "—" : new Intl.NumberFormat(tag, { style: "percent", maximumFractionDigits: 0 }).format(n);
  const money = new Intl.NumberFormat(tag, { style: "currency", currency: "USD" });
  // Jev costs millionths of a dollar per call: "US$ 0,00" would read as free.
  const cost = data.month.cost_usd;
  const usd =
    cost > 0 && cost < 0.01
      ? t("decisions.lessThan", { amount: money.format(0.01) })
      : money.format(cost);
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label={t("decisions.stats.decided", { days: data.days })} value={String(data.conversations)} />
        <Stat label={t("decisions.stats.labeled")} value={String(data.labeled_conversations)} />
        <Stat label={t("decisions.stats.cost", { calls: data.month.calls })} value={usd} />
      </div>
      <p className="text-xs text-fg-muted">{t("decisions.resultsHint")}</p>
      {data.priority && data.priority.set_by_ai > 0 ? (
        <p className="text-sm text-fg">
          {t("decisions.priorityStats", {
            set: data.priority.set_by_ai,
            changed: data.priority.changed_by_others,
          })}
        </p>
      ) : null}
      {data.questions.map((q) => {
        const names = Object.fromEntries(q.options.map((o) => [o.key, o.description]));
        const top = Object.entries(q.answers).sort((a, b) => b[1] - a[1]);
        return (
          <Card key={q.key}>
            <CardHeader>
              <CardTitle className="text-base">{title(q)}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <p className="text-fg">
                {q.compared
                  ? t("decisions.agreement", {
                      pct: pct(q.agreement),
                      agreed: q.agreed,
                      compared: q.compared,
                    })
                  : t("decisions.notCompared")}
              </p>
              <p className="text-xs text-fg-muted">
                {t("decisions.confidence", { pct: pct(q.mean_confidence), decided: q.decided })}
              </p>
              {top.length ? (
                <div className="flex flex-wrap gap-1.5">
                  {top.map(([key, count]) => (
                    <span
                      key={key}
                      className="rounded-full border border-glass px-2.5 py-0.5 text-xs text-fg-muted"
                    >
                      {names[key] ?? key} · {count}
                    </span>
                  ))}
                </div>
              ) : null}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-panel border border-glass bg-surface p-3">
      <p className="text-xs text-fg-muted">{label}</p>
      <p className="mt-1 font-numeric text-xl tabular-nums text-fg">{value}</p>
    </div>
  );
}
