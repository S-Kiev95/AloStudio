"use client";

import { MessageSquare, Pencil, Plus, Send, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  type Delivery,
  type MatchType,
  type PostRule,
  useAutoreplyStatus,
  useCreatePostRule,
  useDeletePostRule,
  usePostRules,
  useUpdatePostRule,
} from "@/lib/api/instagram-autoreply";
import { cn } from "@/lib/utils";

import { PostReplyPicker } from "./post-reply-picker";
import { useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

const MATCHES: { value: MatchType; label: MessageKey; help: MessageKey }[] = [
  {
    value: "keyword",
    label: "instagram.rules.match.keyword",
    help: "instagram.rules.match.keywordHelp",
  },
  {
    value: "semantic",
    label: "instagram.rules.match.semantic",
    help: "instagram.rules.match.semanticHelp",
  },
  {
    value: "all",
    label: "instagram.rules.match.all",
    help: "instagram.rules.match.allHelp",
  },
];

const MATCH_LABEL: Record<MatchType, MessageKey> = {
  keyword: "instagram.rules.match.keyword",
  semantic: "instagram.rules.match.semantic",
  all: "instagram.rules.match.all",
};

/** How close a comment has to be for a similarity rule to answer.
 *
 *  Named levels rather than a raw number: the value underneath is a cosine
 *  distance, which nobody running a shop should have to reason about. The
 *  numbers come from measuring real Spanish comments — a paraphrase of the
 *  same question lands around 0.23-0.47, a different question at 0.65+. */
const STRICTNESS: {
  value: number;
  label: MessageKey;
  help: MessageKey;
}[] = [
  {
    value: 0.45,
    label: "instagram.rules.strict.strict",
    help: "instagram.rules.strict.strictHelp",
  },
  {
    value: 0.55,
    label: "instagram.rules.strict.balanced",
    help: "instagram.rules.strict.balancedHelp",
  },
  {
    value: 0.65,
    label: "instagram.rules.strict.broad",
    help: "instagram.rules.strict.broadHelp",
  },
];

const DEFAULT_STRICTNESS = 0.55;

/** The same three levels for an account that answers with the local model
 *  (EmbeddingGemma). Its distances sit on a much tighter scale, so the
 *  values differ while what each level means does not. Measured on a
 *  labelled set of Spanish comments: 0.13 made no mistake, 0.15 is the
 *  balance, 0.18 starts answering the wrong question. */
const STRICTNESS_GEMMA: typeof STRICTNESS = STRICTNESS.map((s, i) => ({
  ...s,
  value: [0.13, 0.15, 0.18][i],
}));

const DEFAULT_STRICTNESS_GEMMA = 0.15;

/** Rules on one publication. Order shown matches the order they fire in:
 *  keyword, then semantic, then catch-all — a catch-all listed first would
 *  read as if it swallowed everything, which is precisely what the backend
 *  ordering prevents. */
export function PostAutoreplyRules({
  accountId,
  postId,
}: {
  accountId: string;
  postId: number;
}) {
  const t = useT();
  const rules = usePostRules(accountId, postId);
  const status = useAutoreplyStatus(accountId);
  const create = useCreatePostRule(accountId, postId);
  const update = useUpdatePostRule(accountId);
  const del = useDeletePostRule(accountId);
  const semanticAvailable = status.data?.semantic_available !== false;
  // Each model keeps its own threshold; the form edits the one in use and
  // leaves the other untouched.
  const gemma = status.data?.embedding_model === "gemma";
  const levels = gemma ? STRICTNESS_GEMMA : STRICTNESS;
  const defaultStrictness = gemma
    ? DEFAULT_STRICTNESS_GEMMA
    : DEFAULT_STRICTNESS;
  const effectiveOf = (r: PostRule) =>
    gemma ? r.effective_max_distance_gemma : r.effective_max_distance;
  const hasSemanticRule = (rules.data ?? []).some(
    (r) => r.match_type === "semantic",
  );

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<PostRule | null>(null);
  const [matchType, setMatchType] = useState<MatchType>("keyword");
  const [keywords, setKeywords] = useState("");
  const [replyText, setReplyText] = useState("");
  // The mechanic this exists for sends the link privately, so that is the
  // default for keyword rules.
  const [delivery, setDelivery] = useState<Delivery>("dm");
  // Null until the admin picks a level: the shown level is then the rule's
  // own (editing) or the default, on whichever scale the account uses — so
  // it is right even if the status arrives after the form was opened.
  const [strictness, setStrictness] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setOpen(false);
    setEditing(null);
    setMatchType("keyword");
    setKeywords("");
    setReplyText("");
    setDelivery("dm");
    setStrictness(null);
    setError(null);
  }

  function edit(rule: PostRule) {
    setEditing(rule);
    setMatchType(rule.match_type);
    setKeywords(rule.keywords ?? "");
    setReplyText(rule.reply_text ?? "");
    setDelivery(rule.delivery);
    setStrictness(null);
    setError(null);
    setOpen(true);
  }

  const selectedStrictness =
    strictness ?? (editing ? effectiveOf(editing) : defaultStrictness);

  async function submit() {
    setError(null);
    const input = {
      match_type: matchType,
      keywords: matchType === "keyword" ? keywords : null,
      reply_text: matchType === "semantic" ? null : replyText,
      delivery,
      // Editing must not silently re-enable a rule that was turned off.
      enabled: editing ? editing.enabled : true,
      ...(gemma
        ? {
            max_distance_gemma:
              matchType === "semantic" ? selectedStrictness : null,
          }
        : { max_distance: matchType === "semantic" ? selectedStrictness : null }),
    };
    try {
      if (editing) await update.mutateAsync({ id: editing.id, input });
      else await create.mutateAsync(input);
      reset();
    } catch (e) {
      setError((e as { message?: string })?.message ?? t("instagram.saveFailed"));
    }
  }

  const needsText = matchType !== "semantic";
  const canSave =
    (matchType !== "keyword" || keywords.trim().length > 0) &&
    (!needsText || replyText.trim().length > 0);

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        {/* The card around this already carries the title. */}
        <p className="text-xs text-fg-muted">
          {t("instagram.rules.neverOwn")}
        </p>
        {!open ? (
          <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            {t("instagram.rules.add")}
          </Button>
        ) : null}
      </div>

      {open ? (
        <div className="space-y-3 rounded-md border border-glass p-3">
          {/* Named, because the form sits above the list and an edit would
              otherwise look like a second rule being written. */}
          <p className="text-sm font-medium text-fg">
            {editing ? t("instagram.rules.edit") : t("instagram.rules.new")}
          </p>
          {error ? (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          ) : null}

          <div className="grid gap-2 sm:grid-cols-3">
            {MATCHES.map((m) => (
              <button
                key={m.value}
                type="button"
                aria-pressed={matchType === m.value}
                onClick={() => setMatchType(m.value)}
                className={cn(
                  "rounded-md border p-2.5 text-left transition-colors",
                  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
                  matchType === m.value
                    ? "border-neon bg-focused"
                    : "border-glass bg-field hover:bg-hover-glass",
                )}
              >
                <span
                  className={cn(
                    "block text-sm font-medium",
                    matchType === m.value ? "text-lit" : "text-fg",
                  )}
                >
                  {t(m.label)}
                </span>
                <span className="mt-0.5 block text-xs text-fg-muted">
                  {t(m.help)}
                </span>
              </button>
            ))}
          </div>

          {matchType === "keyword" ? (
            <div className="space-y-1.5">
              <Label htmlFor="kw" required>
                {t("instagram.rules.triggerWords")}
              </Label>
              <Input
                id="kw"
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder={t("instagram.rules.triggerPlaceholder")}
              />
              <p className="text-xs text-fg-muted">
                {t("instagram.rules.triggerHelp")}
              </p>
            </div>
          ) : null}

          {needsText ? (
            <div className="space-y-1.5">
              <Label htmlFor="rt" required>
                {t("instagram.reply")}
              </Label>
              <Textarea
                id="rt"
                rows={2}
                maxLength={2200}
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                placeholder={t("instagram.rules.replyPlaceholder")}
              />
            </div>
          ) : (
            <>
              <p className="rounded-md border border-glass bg-surface-2 p-2.5 text-xs text-fg-muted">
                {semanticAvailable
                  ? t("instagram.rules.usesAnswers")
                  : t("instagram.rules.semanticOff")}
              </p>
              <div className="space-y-1.5">
                <Label>{t("instagram.rules.howClose")}</Label>
                <div className="grid gap-2 sm:grid-cols-3">
                  {levels.map((s) => (
                    <button
                      key={s.value}
                      type="button"
                      aria-pressed={selectedStrictness === s.value}
                      onClick={() => setStrictness(s.value)}
                      className={cn(
                        "rounded-md border p-2.5 text-left transition-colors",
                        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
                        selectedStrictness === s.value
                          ? "border-neon bg-focused"
                          : "border-glass bg-field hover:bg-hover-glass",
                      )}
                    >
                      <span
                        className={cn(
                          "block text-sm font-medium",
                          selectedStrictness === s.value
                            ? "text-lit"
                            : "text-fg",
                        )}
                      >
                        {t(s.label)}
                      </span>
                      <span className="mt-0.5 block text-xs text-fg-muted">
                        {t(s.help)}
                      </span>
                    </button>
                  ))}
                </div>
                <p className="text-xs text-fg-muted">
                  {t("instagram.rules.noMatchHuman")}
                </p>
              </div>
            </>
          )}

          <div className="space-y-1.5">
            <Label>{t("instagram.rules.where")}</Label>
            <div className="flex flex-wrap gap-2">
              {(
                [
                  {
                    v: "dm" as Delivery,
                    icon: Send,
                    label: t("instagram.rules.dm"),
                    help: t("instagram.rules.dmHelp"),
                  },
                  {
                    v: "public" as Delivery,
                    icon: MessageSquare,
                    label: t("instagram.rules.public"),
                    help: t("instagram.rules.publicHelp"),
                  },
                ] as const
              ).map((d) => {
                const Icon = d.icon;
                return (
                  <button
                    key={d.v}
                    type="button"
                    aria-pressed={delivery === d.v}
                    onClick={() => setDelivery(d.v)}
                    className={cn(
                      "flex-1 rounded-md border p-2.5 text-left transition-colors",
                      "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
                      delivery === d.v
                        ? "border-neon bg-focused"
                        : "border-glass bg-field hover:bg-hover-glass",
                    )}
                  >
                    <span
                      className={cn(
                        "flex items-center gap-1.5 text-sm font-medium",
                        delivery === d.v ? "text-lit" : "text-fg",
                      )}
                    >
                      <Icon className="h-4 w-4" aria-hidden />
                      {d.label}
                    </span>
                    <span className="mt-0.5 block text-xs text-fg-muted">
                      {d.help}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={submit}
              loading={create.isPending || update.isPending}
              disabled={!canSave}
            >
              {editing ? t("common.saveChanges") : t("instagram.rules.save")}
            </Button>
            <Button size="sm" variant="ghost" onClick={reset}>
              {t("actions.cancel")}
            </Button>
          </div>
        </div>
      ) : null}

      {rules.isLoading ? (
        <p className="py-4 text-center text-sm text-fg-muted">{t("common.loading")}</p>
      ) : (rules.data?.length ?? 0) === 0 ? (
        <p className="py-4 text-center text-sm text-fg-muted">
          {t("instagram.rules.none")}
        </p>
      ) : (
        <ul className="divide-y divide-glass overflow-hidden rounded-md border border-glass">
          {rules.data?.map((r: PostRule) => (
            <li
              key={r.id}
              className="flex items-start gap-3 p-3 transition-colors hover:bg-hover-glass"
            >
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-1.5 text-xs">
                  <span className="rounded-pill bg-surface-2 px-2 py-0.5 font-medium text-fg">
                    {t(MATCH_LABEL[r.match_type])}
                  </span>
                  {r.keywords ? (
                    <span className="font-medium text-lit">
                      {r.keywords}
                    </span>
                  ) : null}
                  <span className="text-fg-muted">
                    {r.delivery === "dm" ? t("instagram.rules.viaDm") : t("instagram.rules.viaPublic")}
                  </span>
                  {r.match_type === "semantic" ? (
                    <span className="text-fg-muted">
                      ·{" "}
                      {(() => {
                        const level = levels.find((s) => s.value === effectiveOf(r));
                        return level
                          ? t(level.label)
                          : t("instagram.rules.strictnessValue", { value: effectiveOf(r) });
                      })()}
                    </span>
                  ) : null}
                </p>
                <p className="mt-1 truncate text-sm text-fg">
                  {r.reply_text ?? t("instagram.rules.usesAnswersShort")}
                </p>
              </div>
              <button
                type="button"
                aria-label={t("instagram.rules.edit")}
                onClick={() => edit(r)}
                className="rounded-md p-1.5 text-fg-muted hover:bg-hover-glass hover:text-fg"
              >
                <Pencil className="h-4 w-4" aria-hidden />
              </button>
              <button
                type="button"
                aria-label={t("instagram.rules.delete")}
                disabled={del.isPending}
                onClick={() => {
                  if (window.confirm(t("instagram.rules.deleteConfirm"))) del.mutate(r.id);
                }}
                className="rounded-md p-1.5 text-fg-muted hover:bg-hover-glass hover:text-danger disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Only once a rule can actually use them — answers with no semantic
          rule on the post would sit there doing nothing. */}
      {hasSemanticRule ? (
        <div className="space-y-2 border-t border-glass pt-4">
          <div>
            <p className="text-sm font-medium text-fg">
              {t("instagram.rules.whichAnswers")}
            </p>
            <p className="text-xs text-fg-muted">
              {t("instagram.rules.whichAnswersHelp")}
            </p>
          </div>
          <PostReplyPicker accountId={accountId} postId={postId} />
        </div>
      ) : null}
    </div>
  );
}
