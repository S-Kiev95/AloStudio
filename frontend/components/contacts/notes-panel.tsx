"use client";

import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  type ContactNote,
  useContactNotes,
  useCreateContactNote,
  useDeleteContactNote,
  useUpdateContactNote,
} from "@/lib/api/contacts";
import { relativeTime } from "@/lib/time";

export function NotesPanel({
  accountId,
  contactId,
}: {
  accountId: string;
  contactId: number;
}) {
  const { data, isLoading, isError } = useContactNotes(accountId, contactId);
  const create = useCreateContactNote(accountId, contactId);

  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const content = draft.trim();
    if (!content) return;
    setError(null);
    try {
      await create.mutateAsync(content);
      setDraft("");
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? "No se pudo agregar la nota.",
      );
    }
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}
        <Textarea
          aria-label="Nueva nota"
          rows={3}
          placeholder="Agregá una nota sobre este contacto…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <div className="flex justify-end">
          <Button
            size="sm"
            onClick={submit}
            loading={create.isPending}
            disabled={!draft.trim()}
          >
            <Plus className="h-4 w-4" aria-hidden />
            Agregar nota
          </Button>
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm text-fg-muted">Cargando notas…</p>
      ) : isError ? (
        <p role="alert" className="text-sm text-danger">
          No se pudieron cargar las notas.
        </p>
      ) : (data?.length ?? 0) === 0 ? (
        <p className="text-sm text-fg-muted">
          Sin notas todavía.
        </p>
      ) : (
        <ul className="space-y-2">
          {data?.map((n) => (
            <NoteRow
              key={n.id}
              accountId={accountId}
              contactId={contactId}
              note={n}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function NoteRow({
  accountId,
  contactId,
  note,
}: {
  accountId: string;
  contactId: number;
  note: ContactNote;
}) {
  const update = useUpdateContactNote(accountId, contactId);
  const del = useDeleteContactNote(accountId, contactId);

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(note.content);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    const content = draft.trim();
    if (!content) return;
    setError(null);
    try {
      await update.mutateAsync({ id: note.id, content });
      setEditing(false);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? "No se pudo actualizar.",
      );
    }
  }

  async function onDelete() {
    if (!window.confirm("¿Eliminar esta nota?")) return;
    setError(null);
    try {
      await del.mutateAsync(note.id);
    } catch (e) {
      setError((e as { message?: string })?.message ?? "No se pudo eliminar.");
    }
  }

  return (
    <li className="rounded-lg border border-border bg-surface p-3">
      {editing ? (
        <div className="space-y-2">
          <Textarea
            aria-label="Editar nota"
            rows={3}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <div className="flex gap-2">
            <Button size="sm" onClick={save} loading={update.isPending}>
              Guardar
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setEditing(false);
                setDraft(note.content);
              }}
            >
              Cancelar
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-1">
          <p className="whitespace-pre-wrap break-words text-sm text-fg">
            {note.content}
          </p>
          <div className="flex items-center justify-between text-xs text-fg-muted">
            <span>
              {note.user?.name ?? "Sistema"} ·{" "}
              {note.created_at ? relativeTime(note.created_at) : "—"}
            </span>
            <div className="flex gap-0.5">
              <button
                type="button"
                aria-label="Editar"
                title="Editar"
                onClick={() => setEditing(true)}
                className="rounded-md p-1 hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Pencil className="h-3.5 w-3.5" aria-hidden />
              </button>
              <button
                type="button"
                aria-label="Eliminar"
                title="Eliminar"
                onClick={onDelete}
                disabled={del.isPending}
                className="rounded-md p-1 hover:bg-surface-2 hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Trash2 className="h-3.5 w-3.5" aria-hidden />
              </button>
            </div>
          </div>
          {error ? (
            <p role="alert" className="text-xs text-danger">
              {error}
            </p>
          ) : null}
        </div>
      )}
    </li>
  );
}
