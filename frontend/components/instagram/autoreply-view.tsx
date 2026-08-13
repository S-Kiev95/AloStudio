"use client";

import { Info, Pencil, Plus, Trash2, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  type AutoreplyMode,
  type CommentReply,
  useAutoreplyConfig,
  useCommentReplies,
  useCreateCommentReply,
  useDeleteCommentReply,
  useUpdateAutoreplyConfig,
  useUpdateCommentReply,
} from "@/lib/api/instagram-autoreply";
import { useInstagramInboxes } from "@/lib/api/instagram";
import { cn } from "@/lib/utils";

const MODES: { value: AutoreplyMode; label: string; help: string }[] = [
  {
    value: "off",
    label: "Desactivado",
    help: "Los comentarios quedan para que los responda una persona.",
  },
  {
    value: "fixed",
    label: "Respuesta fija",
    help: "Todos los comentarios reciben el mismo mensaje.",
  },
  {
    value: "semantic",
    label: "Por similitud",
    help:
      "Se busca la respuesta preparada más parecida a lo que preguntaron. " +
      "Si ninguna se acerca lo suficiente, no responde.",
  },
];

export function AutoreplyView({ accountId }: { accountId: string }) {
  const inboxes = useInstagramInboxes(accountId);
  const [channelId, setChannelId] = useState<number | null>(null);

  // Default to the first connected account rather than making the admin
  // pick before anything renders.
  useEffect(() => {
    if (channelId == null && inboxes.data?.length) {
      setChannelId(inboxes.data[0].channel_id);
    }
  }, [inboxes.data, channelId]);

  const config = useAutoreplyConfig(accountId, channelId);
  const update = useUpdateAutoreplyConfig(accountId, channelId);
  const [error, setError] = useState<string | null>(null);

  const mode = config.data?.mode ?? "off";
  const [text, setText] = useState("");
  useEffect(() => {
    setText(config.data?.text ?? "");
  }, [config.data?.text]);

  async function save(patch: Parameters<typeof update.mutateAsync>[0]) {
    setError(null);
    try {
      await update.mutateAsync(patch);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? "No se pudo guardar.",
      );
    }
  }

  if ((inboxes.data?.length ?? 0) === 0 && !inboxes.isLoading) {
    return (
      <p className="py-10 text-center text-sm text-fg-muted">
        Conectá una cuenta de Instagram para configurar respuestas automáticas.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {(inboxes.data?.length ?? 0) > 1 ? (
        <div className="flex items-center gap-2">
          <Label htmlFor="ig-account">Cuenta</Label>
          <select
            id="ig-account"
            value={channelId ?? ""}
            onChange={(e) => setChannelId(Number(e.target.value))}
            className="h-9 rounded-md border border-border bg-surface px-2 text-sm text-fg"
          >
            {inboxes.data?.map((ib) => (
              <option key={ib.id} value={ib.channel_id}>
                {ib.name}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Respuesta automática a comentarios</CardTitle>
          <p className="mt-1 text-sm text-fg-muted">
            Nunca responde a tus propios comentarios ni dos veces al mismo, y
            solo contesta comentarios nuevos —no respuestas dentro de un hilo.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {error ? (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          ) : null}

          <div className="grid gap-2 sm:grid-cols-3">
            {MODES.map((m) => {
              const disabled =
                m.value === "semantic" && config.data?.semantic_available === false;
              const active = mode === m.value;
              return (
                <button
                  key={m.value}
                  type="button"
                  disabled={disabled || update.isPending}
                  aria-pressed={active}
                  onClick={() => save({ mode: m.value })}
                  className={cn(
                    "rounded-lg border p-3 text-left transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    active
                      ? "border-primary bg-primary/10"
                      : "border-border bg-surface hover:bg-surface-2",
                    disabled && "cursor-not-allowed opacity-50",
                  )}
                >
                  <p className="text-sm font-semibold text-fg">{m.label}</p>
                  <p className="mt-1 text-xs text-fg-muted">{m.help}</p>
                </button>
              );
            })}
          </div>

          {config.data?.semantic_available === false ? (
            <p className="flex items-start gap-2 rounded-lg border border-border bg-surface-2 p-3 text-xs text-fg-muted">
              <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              El modo por similitud necesita una clave de OpenAI configurada en
              el servidor. Sin ella no se pueden comparar los comentarios.
            </p>
          ) : null}

          {mode === "fixed" ? (
            <div className="space-y-2">
              <Label htmlFor="fixed-text" required>
                Mensaje
              </Label>
              <Textarea
                id="fixed-text"
                rows={2}
                value={text}
                maxLength={2200}
                onChange={(e) => setText(e.target.value)}
                placeholder="¡Gracias por escribir! Te respondemos por mensaje directo."
              />
              <Button
                size="sm"
                loading={update.isPending}
                disabled={!text.trim()}
                onClick={() => save({ text })}
              >
                Guardar mensaje
              </Button>
            </div>
          ) : null}

          {mode === "semantic" ? (
            <SensitivityControl
              value={config.data?.max_distance ?? 0.35}
              saving={update.isPending}
              onChange={(v) => save({ max_distance: v })}
            />
          ) : null}
        </CardContent>
      </Card>

      {mode === "semantic" ? <RepliesLibrary accountId={accountId} /> : null}
    </div>
  );
}

/** Cosine distance, presented as sensitivity — an admin should not have to
 *  reason about vector distance to decide how cautious the bot is. */
function SensitivityControl({
  value,
  saving,
  onChange,
}: {
  value: number;
  saving: boolean;
  onChange: (v: number) => void;
}) {
  const LEVELS = [
    { v: 0.2, label: "Muy exigente", help: "Solo responde a preguntas casi idénticas." },
    { v: 0.35, label: "Equilibrado", help: "Recomendado." },
    { v: 0.5, label: "Permisivo", help: "Responde más, con más riesgo de errar." },
  ];
  return (
    <div className="space-y-2">
      <Label>Qué tan parecido tiene que ser</Label>
      <div className="flex flex-wrap gap-2">
        {LEVELS.map((l) => (
          <button
            key={l.v}
            type="button"
            disabled={saving}
            aria-pressed={Math.abs(value - l.v) < 0.01}
            onClick={() => onChange(l.v)}
            className={cn(
              "rounded-lg border px-3 py-2 text-left text-xs transition-colors",
              Math.abs(value - l.v) < 0.01
                ? "border-primary bg-primary/10"
                : "border-border bg-surface hover:bg-surface-2",
            )}
          >
            <span className="block font-semibold text-fg">{l.label}</span>
            <span className="text-fg-muted">{l.help}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function RepliesLibrary({ accountId }: { accountId: string }) {
  const list = useCommentReplies(accountId);
  const create = useCreateCommentReply(accountId);
  const update = useUpdateCommentReply(accountId);
  const del = useDeleteCommentReply(accountId);

  const [editing, setEditing] = useState<CommentReply | null>(null);
  const [trigger, setTrigger] = useState("");
  const [reply, setReply] = useState("");
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setEditing(null);
    setTrigger("");
    setReply("");
  }

  async function submit() {
    setError(null);
    const input = { trigger: trigger.trim(), reply: reply.trim(), enabled: true };
    if (!input.trigger || !input.reply) return;
    try {
      if (editing) await update.mutateAsync({ id: editing.id, input });
      else await create.mutateAsync(input);
      reset();
    } catch (e) {
      setError((e as { message?: string })?.message ?? "No se pudo guardar.");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Respuestas preparadas</CardTitle>
        <p className="mt-1 text-sm text-fg-muted">
          Escribí un ejemplo de cómo lo preguntaría alguien y qué contestar.
          Podés cargar varios ejemplos con la misma respuesta para cubrir
          distintas formas de preguntar lo mismo.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}

        <div className="space-y-2 rounded-lg border border-border p-3">
          <div className="space-y-1.5">
            <Label htmlFor="trigger" required>
              Si preguntan algo como…
            </Label>
            <Input
              id="trigger"
              value={trigger}
              onChange={(e) => setTrigger(e.target.value)}
              placeholder="¿Hacen envíos al interior?"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="reply" required>
              Responder
            </Label>
            <Textarea
              id="reply"
              rows={2}
              value={reply}
              maxLength={2200}
              onChange={(e) => setReply(e.target.value)}
              placeholder="¡Sí! Enviamos a todo el país. Te paso los costos por DM."
            />
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={submit}
              loading={create.isPending || update.isPending}
              disabled={!trigger.trim() || !reply.trim()}
            >
              <Plus className="h-4 w-4" aria-hidden />
              {editing ? "Guardar cambios" : "Agregar"}
            </Button>
            {editing ? (
              <Button size="sm" variant="ghost" onClick={reset}>
                Cancelar
              </Button>
            ) : null}
          </div>
        </div>

        {list.isLoading ? (
          <p className="py-6 text-center text-sm text-fg-muted">Cargando…</p>
        ) : (list.data?.length ?? 0) === 0 ? (
          <p className="py-6 text-center text-sm text-fg-muted">
            Todavía no cargaste respuestas. Sin ninguna, este modo no contesta
            nada.
          </p>
        ) : (
          <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border">
            {list.data?.map((r) => (
              <li key={r.id} className="flex items-start gap-3 p-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-fg">
                    {r.trigger}
                  </p>
                  <p className="truncate text-xs text-fg-muted">{r.reply}</p>
                  {!r.indexed ? (
                    <p className="mt-1 flex items-center gap-1 text-xs text-warning">
                      <TriangleAlert className="h-3 w-3" aria-hidden />
                      Sin indexar — no se va a usar. Volvé a guardarla.
                    </p>
                  ) : null}
                </div>
                <button
                  type="button"
                  aria-label="Editar"
                  onClick={() => {
                    setEditing(r);
                    setTrigger(r.trigger);
                    setReply(r.reply);
                  }}
                  className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-fg"
                >
                  <Pencil className="h-4 w-4" aria-hidden />
                </button>
                <button
                  type="button"
                  aria-label="Eliminar"
                  disabled={del.isPending}
                  onClick={() => {
                    if (window.confirm(`¿Eliminar "${r.trigger}"?`)) {
                      del.mutate(r.id);
                    }
                  }}
                  className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50"
                >
                  <Trash2 className="h-4 w-4" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
