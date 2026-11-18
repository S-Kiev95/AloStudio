"use client";

import { ChevronLeft, Loader2, Sparkles, Undo2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  LANGUAGE_NAMES,
  REWRITE_ACTIONS,
  assistProblemKey,
  useAssist,
  useWritingAssist,
  type AssistInput,
} from "@/lib/api/writing-assist";
import { useLocale, useT } from "@/lib/i18n/provider";
import { translateOr, type MessageKey } from "@/lib/i18n/translate";
import { cn } from "@/lib/utils";

const ITEM =
  "flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-fg hover:bg-hover-glass focus-visible:bg-hover-glass focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent";

/** The composer's AI button (F17): rewrites the draft, or writes a private
 *  note summarizing the conversation. Nothing shows while the installation
 *  has it off. */
export function WritingAssist({
  accountId,
  displayId,
  draft,
  onDraft,
}: {
  accountId: string;
  displayId: number;
  draft: string;
  /** New text for the box; ``asNote`` when it belongs in a private note. */
  onDraft: (text: string, asNote?: boolean) => void;
}) {
  const t = useT();
  const locale = useLocale();
  const info = useWritingAssist(accountId);
  const assist = useAssist(accountId);
  const [open, setOpen] = useState(false);
  const [choosingLanguage, setChoosingLanguage] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  // The box before the AI's text, offered back while the box still shows it.
  const [undo, setUndo] = useState<{ before: string; after: string } | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  // What the box holds when the answer arrives (the agent may keep typing).
  const draftRef = useRef(draft);
  draftRef.current = draft;

  useEffect(() => {
    setUndo(null);
    setProblem(null);
    setOpen(false);
  }, [displayId]);

  useEffect(() => {
    if (!open) return;
    menuRef.current
      ?.querySelector<HTMLButtonElement>('[role="menuitem"]:not([disabled])')
      ?.focus();
    function onDocClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      window.removeEventListener("keydown", onKey);
    };
  }, [open, choosingLanguage]);

  if (!info.data?.enabled) return null;

  const max = info.data.text_max;
  const text = draft.trim();
  const cannotRewrite = !text || text.length > max;

  function run(input: AssistInput) {
    setOpen(false);
    setChoosingLanguage(false);
    setProblem(null);
    assist.mutate(input, {
      onSuccess: ({ text: after }) => {
        setUndo({ before: draftRef.current, after });
        onDraft(after, input.action === "summarize");
      },
      onError: (err) => setProblem(assistProblemKey(err)),
    });
  }

  function onMenuKey(e: React.KeyboardEvent<HTMLDivElement>) {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const items = [
      ...e.currentTarget.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not([disabled])'),
    ];
    const at = items.indexOf(document.activeElement as HTMLButtonElement);
    const step = e.key === "ArrowDown" ? 1 : -1;
    items[(at + step + items.length) % items.length]?.focus();
  }

  return (
    <div ref={wrapRef} className="relative flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => {
          setChoosingLanguage(false);
          setOpen((v) => !v);
        }}
        disabled={assist.isPending}
        aria-expanded={open}
        aria-haspopup="menu"
        title={t("writingAssist.menu")}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-control border px-2.5 py-1.5 text-xs font-medium transition-colors",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
          open
            ? "border-neon bg-focused text-lit"
            : "border-glass bg-field text-fg-muted hover:bg-hover-glass hover:text-fg",
        )}
      >
        {assist.isPending ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
        ) : (
          <Sparkles className="h-3.5 w-3.5" aria-hidden />
        )}
        {assist.isPending ? t("writingAssist.working") : t("writingAssist.button")}
      </button>

      {open ? (
        <div
          ref={menuRef}
          role="menu"
          aria-label={t("writingAssist.menu")}
          onKeyDown={onMenuKey}
          className="absolute bottom-full left-0 z-30 mb-1 max-h-72 w-64 overflow-auto rounded-md border border-glass bg-surface-2 py-1 shadow-menu"
        >
          {choosingLanguage ? (
            <>
              <button
                type="button"
                role="menuitem"
                onClick={() => setChoosingLanguage(false)}
                className={cn(ITEM, "text-fg-muted")}
              >
                <ChevronLeft className="h-3.5 w-3.5" aria-hidden />
                {t("writingAssist.back")}
              </button>
              {info.data.languages.map((code) => (
                <button
                  key={code}
                  type="button"
                  role="menuitem"
                  lang={code}
                  onClick={() => run({ action: "translate", text, language: code })}
                  className={ITEM}
                >
                  {LANGUAGE_NAMES[code] ?? code}
                </button>
              ))}
            </>
          ) : (
            <>
              {REWRITE_ACTIONS.map((action) => (
                <button
                  key={action}
                  type="button"
                  role="menuitem"
                  disabled={cannotRewrite}
                  onClick={() => run({ action, text })}
                  className={ITEM}
                >
                  {t(`writingAssist.actions.${action}` as MessageKey)}
                </button>
              ))}
              <button
                type="button"
                role="menuitem"
                disabled={cannotRewrite}
                onClick={() => setChoosingLanguage(true)}
                className={ITEM}
              >
                {t("writingAssist.actions.translate")}
              </button>
              {cannotRewrite ? (
                <p className="px-3 py-1 text-[11px] text-fg-muted">
                  {text ? t("writingAssist.tooLong", { max }) : t("writingAssist.writeFirst")}
                </p>
              ) : null}
              <div className="my-1 border-t border-glass" />
              <button
                type="button"
                role="menuitem"
                onClick={() =>
                  run({ action: "summarize", conversation_id: displayId, language: locale })
                }
                className={cn(ITEM, "flex-col items-start gap-0")}
              >
                {t("writingAssist.actions.summarize")}
                <span className="text-[11px] text-fg-muted">
                  {t("writingAssist.summarizeHint")}
                </span>
              </button>
            </>
          )}
        </div>
      ) : null}

      {undo && draft === undo.after ? (
        <button
          type="button"
          onClick={() => {
            onDraft(undo.before);
            setUndo(null);
          }}
          className="inline-flex items-center gap-1 rounded-control px-1.5 py-1 text-xs text-fg-muted hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
        >
          <Undo2 className="h-3.5 w-3.5" aria-hidden />
          {t("writingAssist.undo")}
        </button>
      ) : null}

      {problem ? (
        <span role="alert" className="text-xs text-danger">
          {translateOr(t, problem, t("writingAssist.problems.failed"))}
        </span>
      ) : null}
    </div>
  );
}
