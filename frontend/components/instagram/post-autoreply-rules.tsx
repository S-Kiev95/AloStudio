"use client";

import { MessageSquare, Plus, Send, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  type Delivery,
  type MatchType,
  type PostRule,
  useCreatePostRule,
  useDeletePostRule,
  usePostRules,
} from "@/lib/api/instagram-autoreply";
import { cn } from "@/lib/utils";

const MATCHES: { value: MatchType; label: string; help: string }[] = [
  {
    value: "keyword",
    label: "Palabra clave",
    help: "“Comentá INFO y te lo paso”. Solo responde si el comentario incluye alguna de las palabras.",
  },
  {
    value: "semantic",
    label: "Por similitud",
    help: "Busca en tus respuestas preparadas la más parecida. Si ninguna se acerca, no responde.",
  },
  {
    value: "all",
    label: "Todos",
    help: "Contesta cualquier comentario que no haya coincidido antes.",
  },
];

const MATCH_LABEL: Record<MatchType, string> = {
  keyword: "Palabra clave",
  semantic: "Por similitud",
  all: "Todos",
};

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
  const rules = usePostRules(accountId, postId);
  const create = useCreatePostRule(accountId, postId);
  const del = useDeletePostRule(accountId);

  const [open, setOpen] = useState(false);
  const [matchType, setMatchType] = useState<MatchType>("keyword");
  const [keywords, setKeywords] = useState("");
  const [replyText, setReplyText] = useState("");
  // The mechanic this exists for sends the link privately, so that is the
  // default for keyword rules.
  const [delivery, setDelivery] = useState<Delivery>("dm");
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setOpen(false);
    setMatchType("keyword");
    setKeywords("");
    setReplyText("");
    setDelivery("dm");
    setError(null);
  }

  async function submit() {
    setError(null);
    try {
      await create.mutateAsync({
        match_type: matchType,
        keywords: matchType === "keyword" ? keywords : null,
        reply_text: matchType === "semantic" ? null : replyText,
        delivery,
        enabled: true,
      });
      reset();
    } catch (e) {
      setError((e as { message?: string })?.message ?? "No se pudo guardar.");
    }
  }

  const needsText = matchType !== "semantic";
  const canSave =
    (matchType !== "keyword" || keywords.trim().length > 0) &&
    (!needsText || replyText.trim().length > 0);

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-fg">Respuestas automáticas</p>
          <p className="text-xs text-fg-muted">
            Nunca responde a tus propios comentarios ni dos veces al mismo.
          </p>
        </div>
        {!open ? (
          <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            Agregar regla
          </Button>
        ) : null}
      </div>

      {open ? (
        <div className="space-y-3 rounded-lg border border-border p-3">
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
                  "rounded-lg border p-2.5 text-left transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  matchType === m.value
                    ? "border-primary bg-primary/10"
                    : "border-border bg-surface hover:bg-surface-2",
                )}
              >
                <span className="block text-sm font-semibold text-fg">
                  {m.label}
                </span>
                <span className="mt-0.5 block text-xs text-fg-muted">
                  {m.help}
                </span>
              </button>
            ))}
          </div>

          {matchType === "keyword" ? (
            <div className="space-y-1.5">
              <Label htmlFor="kw" required>
                Palabras que lo disparan
              </Label>
              <Input
                id="kw"
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="info, link, precio"
              />
              <p className="text-xs text-fg-muted">
                Separadas por coma. No distingue mayúsculas ni acentos.
              </p>
            </div>
          ) : null}

          {needsText ? (
            <div className="space-y-1.5">
              <Label htmlFor="rt" required>
                Responder
              </Label>
              <Textarea
                id="rt"
                rows={2}
                maxLength={2200}
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                placeholder="¡Ahí va! https://tutienda.com/promo"
              />
            </div>
          ) : (
            <p className="rounded-lg border border-border bg-surface-2 p-2.5 text-xs text-fg-muted">
              Usa las respuestas preparadas de la cuenta. Cargalas en
              Instagram → Respuestas automáticas.
            </p>
          )}

          <div className="space-y-1.5">
            <Label>Dónde responder</Label>
            <div className="flex flex-wrap gap-2">
              {(
                [
                  {
                    v: "dm" as Delivery,
                    icon: Send,
                    label: "Mensaje privado",
                    help: "El link no queda a la vista y te deja el contacto en la bandeja.",
                  },
                  {
                    v: "public" as Delivery,
                    icon: MessageSquare,
                    label: "Respuesta pública",
                    help: "Debajo del comentario, a la vista de todos.",
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
                      "flex-1 rounded-lg border p-2.5 text-left transition-colors",
                      delivery === d.v
                        ? "border-primary bg-primary/10"
                        : "border-border bg-surface hover:bg-surface-2",
                    )}
                  >
                    <span className="flex items-center gap-1.5 text-sm font-semibold text-fg">
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
              loading={create.isPending}
              disabled={!canSave}
            >
              Guardar regla
            </Button>
            <Button size="sm" variant="ghost" onClick={reset}>
              Cancelar
            </Button>
          </div>
        </div>
      ) : null}

      {rules.isLoading ? (
        <p className="py-4 text-center text-sm text-fg-muted">Cargando…</p>
      ) : (rules.data?.length ?? 0) === 0 ? (
        <p className="py-4 text-center text-sm text-fg-muted">
          Sin reglas: los comentarios de esta publicación quedan para que los
          responda una persona.
        </p>
      ) : (
        <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border">
          {rules.data?.map((r: PostRule) => (
            <li key={r.id} className="flex items-start gap-3 p-3">
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-1.5 text-xs">
                  <span className="rounded-full bg-surface-2 px-2 py-0.5 font-medium text-fg">
                    {MATCH_LABEL[r.match_type]}
                  </span>
                  {r.keywords ? (
                    <span className="font-medium text-primary">
                      {r.keywords}
                    </span>
                  ) : null}
                  <span className="text-fg-muted">
                    {r.delivery === "dm" ? "· por privado" : "· en público"}
                  </span>
                </p>
                <p className="mt-1 truncate text-sm text-fg">
                  {r.reply_text ?? "Usa las respuestas preparadas"}
                </p>
              </div>
              <button
                type="button"
                aria-label="Eliminar regla"
                disabled={del.isPending}
                onClick={() => {
                  if (window.confirm("¿Eliminar esta regla?")) del.mutate(r.id);
                }}
                className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
