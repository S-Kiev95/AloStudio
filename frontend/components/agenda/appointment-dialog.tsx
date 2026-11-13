"use client";

import { Search, User as UserIcon, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClassName } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  type Appointment,
  type AppointmentContact,
  type AppointmentStatus,
  useCreateAppointment,
  useUpdateAppointment,
} from "@/lib/api/appointments";
import { useContacts, useSearchContacts } from "@/lib/api/contacts";
import { useProducts } from "@/lib/api/products";
import { cn } from "@/lib/utils";

import { APPOINTMENT_STATUS_OPTIONS } from "./status-badge";
import { fromDatetimeLocalInput, toDatetimeLocalInput } from "./week-utils";
import { useT } from "@/lib/i18n/provider";
import type { Translate } from "@/lib/i18n/translate";

function contactDisplayName(c: AppointmentContact, t: Translate): string {
  return (
    c.name?.trim() ||
    c.email?.trim() ||
    c.phone_number?.trim() ||
    t("conversations.contact.fallbackName", { id: c.id })
  );
}

export function AppointmentDialog({
  accountId,
  open,
  onClose,
  initial,
  presetContact,
  defaultStartsAt,
}: {
  accountId: string;
  open: boolean;
  onClose: () => void;
  initial?: Appointment | null;
  presetContact?: AppointmentContact | null;
  defaultStartsAt?: Date | null;
}) {
  const t = useT();
  const dialogRef = useRef<HTMLDialogElement>(null);

  const [contactQuery, setContactQuery] = useState("");
  const [selectedContact, setSelectedContact] =
    useState<AppointmentContact | null>(null);
  const [pickingContact, setPickingContact] = useState(false);

  const [productId, setProductId] = useState<string>("");
  const [title, setTitle] = useState("");
  const [titleError, setTitleError] = useState<string | null>(null);
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [status, setStatus] = useState<AppointmentStatus>("scheduled");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const searchContacts = useSearchContacts(accountId, contactQuery, 1);
  const recentContacts = useContacts(accountId, 1);
  const products = useProducts(accountId);

  const createMutation = useCreateAppointment(accountId);
  const updateMutation = useUpdateAppointment(accountId);
  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open) {
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
  }, [open]);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setTitleError(null);
    setContactQuery("");

    if (initial) {
      const initContact: AppointmentContact = initial.contact ?? {
        id: initial.contact_id,
        name: null,
        email: null,
        phone_number: null,
      };
      setSelectedContact(initContact);
      setPickingContact(false);
      setProductId(initial.product_id != null ? String(initial.product_id) : "");
      setTitle(initial.title);
      setStartsAt(toDatetimeLocalInput(initial.starts_at));
      setEndsAt(toDatetimeLocalInput(initial.ends_at));
      setStatus(initial.status);
      setNotes(initial.notes ?? "");
    } else {
      const startDefault =
        defaultStartsAt ??
        (() => {
          const d = new Date();
          d.setMinutes(0, 0, 0);
          d.setHours(d.getHours() + 1);
          return d;
        })();
      setSelectedContact(presetContact ?? null);
      setPickingContact(!presetContact);
      setProductId("");
      setTitle("");
      setStartsAt(toDatetimeLocalInput(startDefault));
      setEndsAt("");
      setStatus("scheduled");
      setNotes("");
    }
  }, [open, initial, presetContact, defaultStartsAt]);

  const candidateContacts: AppointmentContact[] =
    contactQuery.trim().length > 0
      ? (searchContacts.data?.payload ?? [])
      : (recentContacts.data?.payload ?? []);

  const availableProducts = (products.data ?? []).filter(
    (p) => p.enabled || (initial?.product_id != null && p.id === initial.product_id),
  );

  function validateTitleOnBlur() {
    if (!title.trim()) {
      setTitleError(t("agenda.dialog.titleRequired"));
    } else {
      setTitleError(null);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!selectedContact) {
      setError(t("agenda.dialog.pickContact"));
      return;
    }
    if (!title.trim()) {
      setTitleError(t("agenda.dialog.titleRequired"));
      setError(t("agenda.dialog.titleRequired"));
      return;
    }
    const isoStart = fromDatetimeLocalInput(startsAt);
    if (!isoStart) {
      setError(t("agenda.dialog.startInvalid"));
      return;
    }
    const isoEnd = endsAt.trim() ? fromDatetimeLocalInput(endsAt) : null;
    if (endsAt.trim() && !isoEnd) {
      setError(t("agenda.dialog.endInvalid"));
      return;
    }
    if (isoEnd && new Date(isoEnd).getTime() < new Date(isoStart).getTime()) {
      setError(t("agenda.dialog.endBeforeStart"));
      return;
    }

    const parsedProductId = productId ? Number(productId) : null;

    try {
      if (initial) {
        await updateMutation.mutateAsync({
          id: initial.id,
          patch: {
            contact_id: selectedContact.id,
            product_id: parsedProductId,
            title: title.trim(),
            starts_at: isoStart,
            ends_at: isoEnd,
            status,
            notes: notes.trim() || null,
          },
        });
      } else {
        await createMutation.mutateAsync({
          contact_id: selectedContact.id,
          product_id: parsedProductId,
          title: title.trim(),
          starts_at: isoStart,
          ends_at: isoEnd,
          status,
          notes: notes.trim() || null,
        });
      }
      onClose();
    } catch (err) {
      setError(
        (err as { message?: string })?.message ??
          t("agenda.dialog.saveFailed"),
      );
    }
  }

  if (!open) return null;

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      aria-labelledby="appointment-dialog-title"
      className="w-full max-w-lg rounded-panel border border-glass bg-surface p-0 text-fg shadow-menu backdrop:bg-backdrop/75"
    >
      <form onSubmit={handleSubmit} className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <h2
            id="appointment-dialog-title"
            className="text-lg font-medium text-fg"
          >
            {initial ? t("agenda.dialog.editTitle") : t("agenda.newAppointment")}
          </h2>
          <button
            type="button"
            aria-label={t("actions.closeDialog")}
            onClick={onClose}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md text-fg-muted hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}

        {/* Contacto */}
        <div className="space-y-1.5">
          <Label htmlFor="appt-contact-search" required>
            {t("conversations.contact.title")}
          </Label>
          {selectedContact && !pickingContact ? (
            <div className="flex items-center justify-between gap-2 rounded-control border border-glass bg-field px-3 py-2 text-sm">
              <div className="flex min-w-0 items-center gap-2">
                <UserIcon
                  className="h-4 w-4 shrink-0 text-fg-muted"
                  aria-hidden
                />
                <div className="min-w-0">
                  <p className="truncate font-medium text-fg">
                    {contactDisplayName(selectedContact, t)}
                  </p>
                  {selectedContact.email || selectedContact.phone_number ? (
                    <p className="truncate text-xs text-fg-muted">
                      {[selectedContact.email, selectedContact.phone_number]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  ) : null}
                </div>
              </div>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => setPickingContact(true)}
              >
                {t("agenda.dialog.change")}
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="relative">
                <Search
                  className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted"
                  aria-hidden
                />
                <Input
                  id="appt-contact-search"
                  value={contactQuery}
                  onChange={(e) => setContactQuery(e.target.value)}
                  placeholder={t("agenda.dialog.searchPlaceholder")}
                  className="pl-9"
                />
              </div>
              {contactQuery.trim().length > 0 && searchContacts.isLoading ? (
                <p className="text-xs text-fg-muted">{t("agenda.dialog.searching")}</p>
              ) : candidateContacts.length === 0 ? (
                <p className="text-xs text-fg-muted">
                  {t("agenda.dialog.noContacts")}
                </p>
              ) : (
                <ul className="max-h-40 divide-y divide-glass overflow-y-auto rounded-md border border-glass bg-surface">
                  {candidateContacts.map((c) => {
                    const label = contactDisplayName(c, t);
                    const sub = [c.email, c.phone_number]
                      .filter(Boolean)
                      .join(" · ");
                    return (
                      <li key={c.id}>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedContact(c);
                            setPickingContact(false);
                          }}
                          className={cn(
                            "flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left text-sm hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon",
                            selectedContact?.id === c.id && "bg-focused text-lit",
                          )}
                        >
                          <span className="font-medium text-fg">{label}</span>
                          {sub ? (
                            <span className="text-xs text-fg-muted">{sub}</span>
                          ) : null}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          )}
        </div>

        {/* Título */}
        <div className="space-y-1.5">
          <Label htmlFor="appt-title" required>
            {t("agenda.dialog.titleLabel")}
          </Label>
          <Input
            id="appt-title"
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              if (titleError && e.target.value.trim()) setTitleError(null);
            }}
            onBlur={validateTitleOnBlur}
            maxLength={255}
            placeholder={t("agenda.dialog.titlePlaceholder")}
          />
          {titleError ? (
            <p role="alert" aria-live="polite" className="text-xs text-danger">
              {titleError}
            </p>
          ) : null}
        </div>

        {/* Inicio y Fin */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="appt-starts-at" required>
              {t("agenda.dialog.start")}
            </Label>
            <Input
              id="appt-starts-at"
              type="datetime-local"
              value={startsAt}
              onChange={(e) => setStartsAt(e.target.value)}
              className="tabular-nums"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="appt-ends-at">{t("agenda.dialog.end")}</Label>
            <Input
              id="appt-ends-at"
              type="datetime-local"
              value={endsAt}
              onChange={(e) => setEndsAt(e.target.value)}
              className="tabular-nums"
            />
          </div>
        </div>

        {/* Producto y Estado */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="appt-product">{t("agenda.dialog.product")}</Label>
            <select
              id="appt-product"
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
              className={selectClassName()}
            >
              <option value="">{t("agenda.dialog.noProduct")}</option>
              {availableProducts.map((p) => (
                <option key={p.id} value={String(p.id)}>
                  {p.name}
                  {p.price != null
                    ? ` (${p.price}${p.currency ? ` ${p.currency}` : ""})`
                    : ""}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="appt-status">{t("conversations.filters.attr.status")}</Label>
            <select
              id="appt-status"
              value={status}
              onChange={(e) => setStatus(e.target.value as AppointmentStatus)}
              className={selectClassName()}
            >
              {APPOINTMENT_STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {t(opt.label)}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Notas */}
        <div className="space-y-1.5">
          <Label htmlFor="appt-notes">{t("agenda.dialog.notes")}</Label>
          <Textarea
            id="appt-notes"
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder={t("agenda.dialog.notesPlaceholder")}
          />
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={isSubmitting}
          >
            {t("actions.cancel")}
          </Button>
          <Button type="submit" loading={isSubmitting}>
            {initial ? t("common.saveChanges") : t("agenda.schedule")}
          </Button>
        </div>
      </form>
    </dialog>
  );
}
