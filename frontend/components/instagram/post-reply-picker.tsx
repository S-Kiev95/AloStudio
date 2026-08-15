"use client";

import { Check, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  useCommentReplies,
  useSetReplyPicks,
} from "@/lib/api/instagram-autoreply";
import { cn } from "@/lib/utils";

/** Which of the account's prepared answers this publication offers.
 *
 *  A picker rather than a per-post editor: an answer about shipping is
 *  worth offering under many posts, and writing it once and ticking it in
 *  several places beats keeping copies in sync.
 *
 *  Picking nothing means the post offers everything — stated plainly,
 *  because an empty checklist otherwise reads as "answers nothing", which
 *  is the opposite of what happens. */
export function PostReplyPicker({
  accountId,
  postId,
}: {
  accountId: string;
  postId: number;
}) {
  const list = useCommentReplies(accountId, { postId });
  const save = useSetReplyPicks(accountId, postId);

  // Null until touched, so the server's selection shows through until the
  // moment the admin actually changes something.
  const [draft, setDraft] = useState<Set<number> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const saved = useMemo(
    () => new Set((list.data ?? []).filter((r) => r.selected).map((r) => r.id)),
    [list.data],
  );
  const current = draft ?? saved;
  const dirty = draft !== null;

  function toggle(id: number) {
    const next = new Set(current);
    if (!next.delete(id)) next.add(id);
    setDraft(next);
  }

  async function commit() {
    setError(null);
    try {
      await save.mutateAsync([...current]);
      setDraft(null);
    } catch (e) {
      setError((e as { message?: string })?.message ?? "No se pudo guardar.");
    }
  }

  if (list.isLoading) {
    return <p className="py-4 text-center text-sm text-fg-muted">Cargando…</p>;
  }

  const answers = list.data ?? [];
  if (answers.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-fg-muted">
        Todavía no cargaste respuestas preparadas. Cargalas en Instagram →
        Respuestas automáticas y después elegí cuáles usa esta publicación.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      <p className="text-xs text-fg-muted">
        {current.size === 0
          ? `Sin elegir ninguna, esta publicación puede usar las ${answers.length}.`
          : `Esta publicación usa ${current.size} de ${answers.length}.`}
      </p>

      <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border">
        {answers.map((r) => {
          const on = current.has(r.id);
          return (
            <li key={r.id}>
              <button
                type="button"
                role="checkbox"
                aria-checked={on}
                onClick={() => toggle(r.id)}
                className={cn(
                  "flex w-full items-start gap-3 p-3 text-left transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  on ? "bg-primary/5" : "hover:bg-surface-2",
                )}
              >
                <span
                  aria-hidden
                  className={cn(
                    "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border",
                    on
                      ? "border-primary bg-primary text-primary-fg"
                      : "border-border",
                  )}
                >
                  {on ? <Check className="h-3 w-3" /> : null}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-fg">
                    {r.trigger}
                  </span>
                  <span className="block truncate text-xs text-fg-muted">
                    {r.reply}
                  </span>
                  {!r.indexed ? (
                    <span className="mt-1 flex items-center gap-1 text-xs text-warning">
                      <TriangleAlert className="h-3 w-3" aria-hidden />
                      Sin indexar — no se va a usar aunque la elijas.
                    </span>
                  ) : null}
                </span>
              </button>
            </li>
          );
        })}
      </ul>

      {dirty ? (
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={commit} loading={save.isPending}>
            Guardar selección
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>
            Descartar
          </Button>
        </div>
      ) : null}
    </div>
  );
}
