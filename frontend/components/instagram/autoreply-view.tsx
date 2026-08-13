"use client";

import { Pencil, Plus, Trash2, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  type CommentReply,
  useCommentReplies,
  useCreateCommentReply,
  useDeleteCommentReply,
  useUpdateCommentReply,
} from "@/lib/api/instagram-autoreply";

/** The account-wide library of prepared answers.
 *
 *  Account-level on purpose: the same answers about shipping or prices
 *  apply across every post. Which posts actually use them is decided by a
 *  `semantic` rule on each publication. */
export function AutoreplyView({ accountId }: { accountId: string }) {
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
