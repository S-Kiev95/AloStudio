"use client";

import { AlertTriangle, Search, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  type Contact,
  useMergeContacts,
  useSearchContacts,
} from "@/lib/api/contacts";
import { cn } from "@/lib/utils";

/**
 * Confirmation dialog for merging two contacts. The ``base`` is the
 * contact we're keeping; the user picks the ``mergee`` via search. The
 * mergee's conversations + notes + JSONB attrs are folded into base
 * and the mergee row is destroyed — irreversible, so we surface a
 * warning + a two-step confirmation.
 *
 * Uses the native ``<dialog>`` element so focus trap + ESC-to-close +
 * backdrop are handled by the browser without an extra dep.
 */
export function MergeDialog({
  accountId,
  base,
  open,
  onClose,
  onMerged,
}: {
  accountId: string;
  base: Contact;
  open: boolean;
  onClose: () => void;
  onMerged?: (mergedBase: Contact) => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<Contact | null>(null);
  const [error, setError] = useState<string | null>(null);

  const search = useSearchContacts(accountId, q, 1);
  const merge = useMergeContacts(accountId);

  // Sync open prop with the native dialog API.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  // Reset state every time the dialog re-opens.
  useEffect(() => {
    if (open) {
      setQ("");
      setSelected(null);
      setError(null);
    }
  }, [open]);

  async function submit() {
    if (!selected) return;
    setError(null);
    try {
      const merged = await merge.mutateAsync({
        base_contact_id: base.id,
        mergee_contact_id: selected.id,
      });
      onMerged?.(merged);
      onClose();
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? "No se pudo combinar los contactos.",
      );
    }
  }

  const baseLabel =
    base.name?.trim() || base.email?.trim() || `Contacto #${base.id}`;

  // Filter out the base contact from the search results so users can't
  // try to merge a contact into itself.
  const candidates = (search.data?.payload ?? []).filter(
    (c) => c.id !== base.id,
  );

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      className="rounded-lg border border-border bg-surface p-0 text-fg shadow-xl backdrop:bg-black/50 w-full max-w-md"
    >
      <div className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-fg">
              Combinar contactos
            </h2>
            <p className="mt-1 text-sm text-fg-muted">
              Las conversaciones, notas y atributos del contacto elegido
              pasan a <strong>{baseLabel}</strong>. Esta acción no se puede
              deshacer.
            </p>
          </div>
          <button
            type="button"
            aria-label="Cerrar"
            onClick={onClose}
            className="rounded-md p-1 text-fg-muted hover:bg-surface-2"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        {/* Search picker */}
        <div className="space-y-2">
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted"
              aria-hidden
            />
            <Input
              aria-label="Buscar contacto a combinar"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setSelected(null);
              }}
              placeholder="Buscar por nombre, email, teléfono…"
              className="pl-9"
            />
          </div>

          {q.trim().length > 0 ? (
            search.isLoading ? (
              <p className="text-sm text-fg-muted">Buscando…</p>
            ) : candidates.length === 0 ? (
              <p className="text-sm text-fg-muted">Sin resultados.</p>
            ) : (
              <ul className="max-h-48 divide-y divide-border overflow-y-auto rounded-md border border-border bg-surface">
                {candidates.map((c) => {
                  const label =
                    c.name?.trim() ||
                    c.email?.trim() ||
                    c.phone_number?.trim() ||
                    `Contacto #${c.id}`;
                  const sub = [c.email, c.phone_number]
                    .filter(Boolean)
                    .join(" · ");
                  const isSelected = selected?.id === c.id;
                  return (
                    <li key={c.id}>
                      <button
                        type="button"
                        onClick={() => setSelected(c)}
                        className={cn(
                          "flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left text-sm hover:bg-surface-2",
                          isSelected && "bg-primary/10 text-primary",
                        )}
                      >
                        <span className="font-medium">{label}</span>
                        {sub ? (
                          <span className="text-xs text-fg-muted">{sub}</span>
                        ) : null}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )
          ) : null}
        </div>

        {selected ? (
          <div className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/5 p-3 text-sm">
            <AlertTriangle
              className="mt-0.5 h-4 w-4 shrink-0 text-warning"
              aria-hidden
            />
            <div>
              <p className="text-fg">
                Vas a combinar{" "}
                <strong>
                  {selected.name?.trim() ||
                    selected.email?.trim() ||
                    `Contacto #${selected.id}`}
                </strong>{" "}
                en <strong>{baseLabel}</strong>.
              </p>
              <p className="mt-1 text-xs text-fg-muted">
                El segundo contacto se elimina al finalizar.
              </p>
            </div>
          </div>
        ) : null}

        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={merge.isPending}>
            Cancelar
          </Button>
          <Button
            onClick={submit}
            loading={merge.isPending}
            disabled={!selected}
          >
            Combinar contactos
          </Button>
        </div>
      </div>
    </dialog>
  );
}
