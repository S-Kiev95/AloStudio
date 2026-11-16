"use client";

import { Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClassName } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useAgents } from "@/lib/api/account";
import {
  type Activity,
  type ActivityInput,
  type ActivityKind,
  useCreateActivity,
  useDeleteActivity,
  useOpportunities,
  useUpdateActivity,
} from "@/lib/api/crm";
import { useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

import { ContactPicker, type PickedContact } from "./contact-picker";

export const ACTIVITY_KINDS: { value: ActivityKind; label: MessageKey }[] = [
  { value: "task", label: "activities.kinds.task" },
  { value: "call", label: "activities.kinds.call" },
  { value: "meeting", label: "activities.kinds.meeting" },
  { value: "email", label: "activities.kinds.email" },
];

/** ``datetime-local`` value for a unix-seconds instant, in local time. */
function toLocalInput(unix: number | null): string {
  if (!unix) return "";
  const d = new Date(unix * 1000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function ActivityDialog({
  accountId,
  open,
  onClose,
  initial,
  presetContact,
}: {
  accountId: string;
  open: boolean;
  onClose: () => void;
  initial?: Activity | null;
  presetContact?: PickedContact | null;
}) {
  const t = useT();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [kind, setKind] = useState<ActivityKind>("task");
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const [contact, setContact] = useState<PickedContact | null>(null);
  const [opportunityId, setOpportunityId] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  const agents = useAgents(accountId);
  const opportunities = useOpportunities(accountId, contact ? { contact_id: contact.id } : {});
  const create = useCreateActivity(accountId);
  const update = useUpdateActivity(accountId);
  const remove = useDeleteActivity(accountId);
  const submitting = create.isPending || update.isPending;

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open && !el.open) {
      if (typeof el.showModal === "function") el.showModal();
      else el.setAttribute("open", "");
    } else if (!open && el.open) {
      if (typeof el.close === "function") el.close();
      else el.removeAttribute("open");
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setKind(initial?.kind ?? "task");
    setTitle(initial?.title ?? "");
    setDue(toLocalInput(initial?.due_at ?? null));
    setOwnerId(initial?.owner_id != null ? String(initial.owner_id) : "");
    setContact(initial?.contact ?? presetContact ?? null);
    setOpportunityId(initial?.opportunity_id != null ? String(initial.opportunity_id) : "");
    setDescription(initial?.description ?? "");
  }, [open, initial, presetContact]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!title.trim()) {
      setError(t("opportunities.titleRequired"));
      return;
    }
    const dueDate = due ? new Date(due) : null;
    if (dueDate && Number.isNaN(dueDate.getTime())) {
      setError(t("activities.dueInvalid"));
      return;
    }
    const payload: ActivityInput = {
      kind,
      title: title.trim(),
      due_at: dueDate ? dueDate.toISOString() : null,
      contact_id: contact?.id ?? null,
      opportunity_id: opportunityId ? Number(opportunityId) : null,
      description: description.trim() || null,
    };
    if (ownerId) payload.owner_id = Number(ownerId);
    else if (initial) payload.owner_id = null;
    try {
      if (initial) await update.mutateAsync({ id: initial.id, patch: payload });
      else await create.mutateAsync(payload);
      onClose();
    } catch (err) {
      setError((err as { message?: string })?.message ?? t("activities.saveFailed"));
    }
  }

  async function handleDelete() {
    if (!initial) return;
    if (!window.confirm(t("activities.deleteConfirm", { title: initial.title }))) return;
    try {
      await remove.mutateAsync(initial.id);
      onClose();
    } catch (err) {
      setError((err as { message?: string })?.message ?? t("actions.deleteFailed"));
    }
  }

  if (!open) return null;

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      aria-labelledby="activity-dialog-title"
      className="w-full max-w-lg rounded-panel border border-glass bg-surface p-0 text-fg shadow-menu backdrop:bg-backdrop/75"
    >
      <form onSubmit={handleSubmit} className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <h2 id="activity-dialog-title" className="text-lg font-medium text-fg">
            {initial ? t("activities.edit") : t("activities.new")}
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

        <div className="grid grid-cols-[8rem_1fr] gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="act-kind">{t("activities.kind")}</Label>
            <select
              id="act-kind"
              value={kind}
              onChange={(e) => setKind(e.target.value as ActivityKind)}
              className={selectClassName()}
            >
              {ACTIVITY_KINDS.map((k) => (
                <option key={k.value} value={k.value}>
                  {t(k.label)}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="act-title" required>
              {t("opportunities.title")}
            </Label>
            <Input
              id="act-title"
              value={title}
              maxLength={255}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={t("activities.titlePlaceholder")}
            />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="act-due">{t("activities.due")}</Label>
            <Input
              id="act-due"
              type="datetime-local"
              value={due}
              onChange={(e) => setDue(e.target.value)}
              className="tabular-nums"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="act-owner">{t("opportunities.owner")}</Label>
            <select
              id="act-owner"
              value={ownerId}
              onChange={(e) => setOwnerId(e.target.value)}
              className={selectClassName()}
            >
              <option value="">{initial ? t("opportunities.noOwner") : t("opportunities.me")}</option>
              {(agents.data ?? []).map((a) => (
                <option key={a.id} value={String(a.id)}>
                  {a.available_name || a.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="act-contact-search">{t("conversations.contact.title")}</Label>
          <ContactPicker
            accountId={accountId}
            inputId="act-contact-search"
            value={contact}
            onChange={(c) => {
              setContact(c);
              setOpportunityId("");
            }}
            locked={Boolean(presetContact)}
          />
        </div>

        {contact && (opportunities.data?.length ?? 0) > 0 ? (
          <div className="space-y-1.5">
            <Label htmlFor="act-opportunity">{t("activities.opportunity")}</Label>
            <select
              id="act-opportunity"
              value={opportunityId}
              onChange={(e) => setOpportunityId(e.target.value)}
              className={selectClassName()}
            >
              <option value="">{t("activities.noOpportunity")}</option>
              {opportunities.data?.map((o) => (
                <option key={o.id} value={String(o.id)}>
                  {o.title}
                </option>
              ))}
            </select>
          </div>
        ) : null}

        <div className="space-y-1.5">
          <Label htmlFor="act-notes">{t("opportunities.notes")}</Label>
          <Textarea
            id="act-notes"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        <div className="flex items-center justify-between gap-2 pt-2">
          {initial ? (
            <Button type="button" variant="ghost" onClick={handleDelete} disabled={remove.isPending}>
              <Trash2 className="h-4 w-4" aria-hidden />
              {t("actions.delete")}
            </Button>
          ) : (
            <span />
          )}
          <span className="flex gap-2">
            <Button type="button" variant="ghost" onClick={onClose} disabled={submitting}>
              {t("actions.cancel")}
            </Button>
            <Button type="submit" loading={submitting}>
              {initial ? t("common.saveChanges") : t("activities.create")}
            </Button>
          </span>
        </div>
      </form>
    </dialog>
  );
}
