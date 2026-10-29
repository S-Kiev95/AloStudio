"use client";

import { Check, FileSignature, Pencil, Plus, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { PublicationErrorAlert } from "@/components/publications/publication-error-alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useIsAccountAdmin } from "@/lib/api/profile";
import {
  type ParsedPublicationError,
  parsePublicationError,
  type Signature,
  useCreatePublicationSignature,
  useDeletePublicationSignature,
  usePublicationSignatures,
  useUpdatePublicationSignature,
} from "@/lib/api/publications";
import { cn } from "@/lib/utils";

const SIGNATURE_MAX_CHARS = 2000;

function formatSignatureDate(iso: string | null): string | null {
  if (!iso) return null;
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return null;
  return new Date(ms).toLocaleDateString();
}

export function SignaturesView({ accountId }: { accountId: string }) {
  const isAdmin = useIsAccountAdmin(accountId);
  const signaturesQuery = usePublicationSignatures(accountId);
  const createMutation = useCreatePublicationSignature(accountId);
  const updateMutation = useUpdatePublicationSignature(accountId);
  const deleteMutation = useDeletePublicationSignature(accountId);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Signature | null>(null);
  const [content, setContent] = useState("");
  const [autoAdd, setAutoAdd] = useState(false);
  const [pageError, setPageError] = useState<ParsedPublicationError | null>(
    null,
  );
  const [dialogError, setDialogError] = useState<ParsedPublicationError | null>(
    null,
  );

  const dialogRef = useRef<HTMLDialogElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (dialogOpen) {
      if (!el.open) {
        if (typeof el.showModal === "function") {
          el.showModal();
        } else {
          el.setAttribute("open", "");
        }
      }
    } else if (el.open) {
      if (typeof el.close === "function") {
        el.close();
      } else {
        el.removeAttribute("open");
      }
    }
  }, [dialogOpen]);

  useEffect(() => {
    if (dialogError) {
      errorRef.current?.scrollIntoView?.({ block: "nearest" });
    }
  }, [dialogError]);

  function openCreate() {
    setEditing(null);
    setContent("");
    setAutoAdd(false);
    setDialogError(null);
    setDialogOpen(true);
  }

  function openEdit(sig: Signature) {
    setEditing(sig);
    setContent(sig.content);
    setAutoAdd(sig.auto_add);
    setDialogError(null);
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setDialogError(null);
  }

  const codePointLength = Array.from(content).length;
  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setDialogError(null);

    if (Array.from(content.trim()).length < 1) {
      setDialogError({
        message: "Escribí el texto de la firma.",
        errors: [],
      });
      return;
    }

    if (codePointLength > SIGNATURE_MAX_CHARS) {
      setDialogError({
        message: `La firma no puede superar los ${SIGNATURE_MAX_CHARS} caracteres.`,
        errors: [],
      });
      return;
    }

    try {
      if (editing) {
        await updateMutation.mutateAsync({
          id: editing.id,
          patch: { content, auto_add: autoAdd },
        });
      } else {
        await createMutation.mutateAsync({
          content,
          auto_add: autoAdd,
        });
      }
      closeDialog();
    } catch (err) {
      setDialogError(
        parsePublicationError(err, "No se pudo guardar la firma."),
      );
    }
  }

  async function handleToggleAutoAdd(sig: Signature) {
    setPageError(null);
    try {
      await updateMutation.mutateAsync({
        id: sig.id,
        patch: { auto_add: !sig.auto_add },
      });
    } catch (err) {
      setPageError(
        parsePublicationError(err, "No se pudo actualizar la firma."),
      );
    }
  }

  async function handleDelete(sig: Signature) {
    setPageError(null);
    try {
      await deleteMutation.mutateAsync(sig.id);
    } catch (err) {
      setPageError(parsePublicationError(err, "No se pudo borrar la firma."));
    }
  }

  const signatures = signaturesQuery.data ?? [];

  return (
    <div className="max-w-3xl space-y-4">
      <div className="space-y-1">
        <h2 className="text-xl font-medium text-fg">Firmas</h2>
        <p className="text-sm text-fg-muted">
          Podés agregar firmas a tu cuenta para reutilizarlas en tus
          publicaciones o sumar una automáticamente a cada publicación nueva.
        </p>
      </div>

      {isAdmin ? (
        <div className="rounded-xl border border-glass bg-surface-1 p-5">
          <Button type="button" onClick={openCreate}>
            <Plus className="h-4 w-4" aria-hidden />
            Agregar firma
          </Button>
        </div>
      ) : null}

      <PublicationErrorAlert
        error={pageError}
        onDismiss={() => setPageError(null)}
      />

      <div className="overflow-hidden rounded-xl border border-glass bg-surface">
        {signaturesQuery.isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
        ) : signaturesQuery.isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            No se pudieron cargar las firmas.
          </p>
        ) : signatures.length === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            No hay firmas todavía.
          </p>
        ) : (
          <ul className="divide-y divide-glass">
            {signatures.map((sig) => {
              const dateLabel = formatSignatureDate(
                sig.updated_at ?? sig.created_at,
              );
              return (
                <li
                  key={sig.id}
                  className="flex flex-wrap items-start justify-between gap-3 px-4 py-3.5 transition-colors hover:bg-hover-glass"
                >
                  <div className="flex min-w-0 flex-1 items-start gap-3">
                    <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-focused text-lit">
                      <FileSignature className="h-4 w-4" aria-hidden />
                    </span>
                    <div className="min-w-0 flex-1 space-y-1">
                      <p className="whitespace-pre-wrap break-words text-sm text-fg">
                        {sig.content}
                      </p>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-fg-muted">
                        {sig.auto_add ? (
                          <span className="inline-flex items-center gap-1 rounded-sm border border-neon bg-focused px-2 py-0.5 font-medium text-lit">
                            <Check className="h-3 w-3" aria-hidden />
                            Automática
                          </span>
                        ) : null}
                        {dateLabel ? (
                          <span className="font-numeric tabular-nums">
                            {dateLabel}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </div>

                  {isAdmin ? (
                    <div className="flex shrink-0 items-center gap-1">
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        disabled={updateMutation.isPending}
                        onClick={() => void handleToggleAutoAdd(sig)}
                      >
                        {sig.auto_add ? "Quitar automática" : "Hacer automática"}
                      </Button>
                      <button
                        type="button"
                        aria-label="Editar firma"
                        title="Editar firma"
                        onClick={() => openEdit(sig)}
                        className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        <Pencil className="h-4 w-4" aria-hidden />
                      </button>
                      <button
                        type="button"
                        aria-label="Borrar firma"
                        title="Borrar firma"
                        disabled={deleteMutation.isPending}
                        onClick={() => void handleDelete(sig)}
                        className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        <Trash2 className="h-4 w-4" aria-hidden />
                      </button>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {isAdmin ? (
        <dialog
          ref={dialogRef}
          onClose={closeDialog}
          aria-labelledby="signature-dialog-title"
          className="max-h-[90dvh] w-full max-w-lg overflow-y-auto rounded-panel border border-glass bg-surface p-0 text-fg shadow-menu backdrop:bg-backdrop backdrop:opacity-80"
        >
          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 p-5">
            <div className="flex items-center justify-between border-b border-glass pb-3">
              <h3
                id="signature-dialog-title"
                className="text-lg font-medium text-fg"
              >
                {editing ? "Editar firma" : "Agregar firma"}
              </h3>
              <button
                type="button"
                aria-label="Cerrar diálogo"
                onClick={closeDialog}
                className="inline-flex h-8 w-8 items-center justify-center rounded-md text-fg-muted hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </div>

            <div ref={errorRef}>
              <PublicationErrorAlert
                error={dialogError}
                onDismiss={() => setDialogError(null)}
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between gap-2">
                <Label htmlFor="signature-content" required>
                  Texto de la firma
                </Label>
                <span
                  className={cn(
                    "font-numeric text-xs tabular-nums",
                    codePointLength > SIGNATURE_MAX_CHARS
                      ? "text-danger"
                      : "text-fg-muted",
                  )}
                >
                  {codePointLength} / {SIGNATURE_MAX_CHARS}
                </span>
              </div>
              <Textarea
                id="signature-content"
                rows={4}
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="Ej: Consultanos por mensaje directo o en nuestra web."
                aria-invalid={codePointLength > SIGNATURE_MAX_CHARS}
              />
            </div>

            <label className="flex cursor-pointer items-center gap-2.5 text-sm text-fg">
              <input
                type="checkbox"
                checked={autoAdd}
                onChange={(e) => setAutoAdd(e.target.checked)}
                className="h-4 w-4 rounded border-glass bg-field accent-primary"
              />
              <span>¿Agregar sola a cada publicación nueva?</span>
            </label>

            <div className="flex items-center justify-end gap-2 border-t border-glass pt-3">
              <Button
                type="button"
                variant="ghost"
                onClick={closeDialog}
                disabled={isSubmitting}
              >
                Cancelar
              </Button>
              <Button type="submit" loading={isSubmitting}>
                {editing ? "Guardar cambios" : "Guardar firma"}
              </Button>
            </div>
          </form>
        </dialog>
      ) : null}
    </div>
  );
}
