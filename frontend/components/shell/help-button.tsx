"use client";

import { ArrowRight, CircleHelp, Loader2 } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  helpProblemKey,
  type HelpAnswer,
  useAskHelp,
  useHelpAssistant,
} from "@/lib/api/help-assistant";
import { useT } from "@/lib/i18n/provider";
import { translateOr } from "@/lib/i18n/translate";
import { cn } from "@/lib/utils";

type Turn = { question: string; answer: HelpAnswer };

/** Topbar "?" button: ask how to do something in AloStudio. Answered by the
 *  local model from AloStudio's own help; hidden while it is not set up. */
export function HelpButton({ accountId }: { accountId: string }) {
  const t = useT();
  const pathname = usePathname() ?? "";
  const info = useHelpAssistant(accountId);
  const ask = useAskHelp(accountId);
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    function onDocClick(e: MouseEvent) {
      if (detailsRef.current && !detailsRef.current.contains(e.target as Node)) {
        detailsRef.current.removeAttribute("open");
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  if (!info.data?.enabled) return null;
  const max = info.data.question_max;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const text = question.trim();
    if (!text || ask.isPending) return;
    setProblem(null);
    ask.mutate(
      { question: text, page: pathname },
      {
        onSuccess: (answer) => {
          setTurns((prev) => [...prev, { question: text, answer }].slice(-5));
          setQuestion("");
        },
        onError: (err) => setProblem(helpProblemKey(err)),
      },
    );
  }

  return (
    <details
      ref={detailsRef}
      className="group relative"
      onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}
    >
      <summary
        aria-label={t("helpAssistant.title")}
        title={t("helpAssistant.title")}
        className={cn(
          "relative flex h-10 w-10 cursor-pointer list-none items-center justify-center rounded-control text-fg-muted transition-colors",
          "hover:bg-hover-glass hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
        )}
      >
        <CircleHelp className="h-5 w-5" aria-hidden />
      </summary>

      <div
        role="dialog"
        aria-label={t("helpAssistant.title")}
        className="absolute right-0 z-30 mt-1.5 flex w-[24rem] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-md border border-glass bg-surface-2 shadow-menu"
      >
        <div className="border-b border-glass px-3 py-2.5">
          <h2 className="text-sm font-medium text-fg">{t("helpAssistant.title")}</h2>
          <p className="text-xs text-fg-muted">{t("helpAssistant.intro")}</p>
        </div>

        <div className="max-h-[24rem] space-y-3 overflow-y-auto px-3 py-3 text-sm">
          {turns.length === 0 && !ask.isPending ? (
            <p className="text-xs text-fg-muted">{t("helpAssistant.examples")}</p>
          ) : null}
          {turns.map((turn, i) => (
            <div key={i} className="space-y-1.5">
              <p className="text-xs font-medium text-fg-muted">{turn.question}</p>
              <p className={cn("text-fg", !turn.answer.known && "text-fg-muted")}>
                {turn.answer.answer}
              </p>
              {turn.answer.screen ? (
                <Link
                  href={
                    turn.answer.screen.path
                      ? `/accounts/${accountId}/${turn.answer.screen.path}`
                      : `/accounts/${accountId}`
                  }
                  onClick={() => {
                    detailsRef.current?.removeAttribute("open");
                    setOpen(false);
                  }}
                  className="inline-flex items-center gap-1 text-xs font-medium text-info hover:underline"
                >
                  {t("helpAssistant.goTo", { screen: turn.answer.screen.label })}
                  <ArrowRight className="h-3.5 w-3.5" aria-hidden />
                </Link>
              ) : null}
              {turn.answer.note ? (
                <p className="text-xs text-fg-muted">{turn.answer.note}</p>
              ) : null}
            </div>
          ))}
          {ask.isPending ? (
            <p className="inline-flex items-center gap-2 text-xs text-fg-muted" role="status">
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
              {t("helpAssistant.thinking")}
            </p>
          ) : null}
          {problem ? (
            <p role="alert" className="text-xs text-danger">
              {translateOr(t, problem, t("helpAssistant.problems.failed"))}
            </p>
          ) : null}
        </div>

        <form onSubmit={submit} className="flex gap-2 border-t border-glass p-2">
          <input
            ref={inputRef}
            value={question}
            maxLength={max}
            onChange={(e) => setQuestion(e.target.value)}
            aria-label={t("helpAssistant.question")}
            placeholder={t("helpAssistant.placeholder")}
            className="glass-field h-9 min-w-0 flex-1 rounded-control border border-glass bg-field px-2.5 text-xs text-fg placeholder:text-fg-muted"
          />
          <Button type="submit" size="sm" disabled={!question.trim() || ask.isPending}>
            {t("helpAssistant.ask")}
          </Button>
        </form>
      </div>
    </details>
  );
}
