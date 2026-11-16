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
  type Opportunity,
  type OpportunityInput,
  type Pipeline,
  useCreateOpportunity,
  useDeleteOpportunity,
  useUpdateOpportunity,
} from "@/lib/api/crm";
import { useProducts } from "@/lib/api/products";
import { useT } from "@/lib/i18n/provider";

import { ContactPicker, type PickedContact } from "./contact-picker";
import { stageLabel } from "./stage-label";

/** Create or edit an opportunity. ``presetContact`` fixes the contact when
 *  it is opened from a contact's page. */
export function OpportunityDialog({
  accountId,
  pipeline,
  open,
  onClose,
  initial,
  presetContact,
  defaultStageId,
}: {
  accountId: string;
  pipeline: Pipeline;
  open: boolean;
  onClose: () => void;
  initial?: Opportunity | null;
  presetContact?: PickedContact | null;
  defaultStageId?: number | null;
}) {
  const t = useT();
  const dialogRef = useRef<HTMLDialogElement>(null);

  const [contact, setContact] = useState<PickedContact | null>(null);
  const [title, setTitle] = useState("");
  const [stageId, setStageId] = useState("");
  const [value, setValue] = useState("");
  const [currency, setCurrency] = useState("");
  const [expected, setExpected] = useState("");
  const [productId, setProductId] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const [description, setDescription] = useState("");
  const [lostReason, setLostReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const products = useProducts(accountId);
  const agents = useAgents(accountId);
  const create = useCreateOpportunity(accountId);
  const update = useUpdateOpportunity(accountId);
  const remove = useDeleteOpportunity(accountId);
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
    const firstStage = pipeline.stages[0]?.id;
    if (initial) {
      setContact(initial.contact ?? null);
      setTitle(initial.title);
      setStageId(String(initial.stage_id));
      setValue(initial.value != null ? String(initial.value) : "");
      setCurrency(initial.currency ?? "");
      setExpected(initial.expected_close_on ?? "");
      setProductId(initial.product_id != null ? String(initial.product_id) : "");
      setOwnerId(initial.owner_id != null ? String(initial.owner_id) : "");
      setDescription(initial.description ?? "");
      setLostReason(initial.lost_reason ?? "");
    } else {
      setContact(presetContact ?? null);
      setTitle("");
      setStageId(String(defaultStageId ?? firstStage ?? ""));
      setValue("");
      setCurrency("");
      setExpected("");
      setProductId("");
      setOwnerId("");
      setDescription("");
      setLostReason("");
    }
  }, [open, initial, presetContact, defaultStageId, pipeline]);

  const stage = pipeline.stages.find((s) => String(s.id) === stageId);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!title.trim()) {
      setError(t("opportunities.titleRequired"));
      return;
    }
    const parsedValue = value.trim() ? Number(value.replace(",", ".")) : null;
    if (parsedValue !== null && (Number.isNaN(parsedValue) || parsedValue < 0)) {
      setError(t("opportunities.valueInvalid"));
      return;
    }
    const payload: OpportunityInput = {
      title: title.trim(),
      stage_id: Number(stageId),
      value: parsedValue,
      currency: currency.trim().toUpperCase() || null,
      contact_id: contact?.id ?? null,
      product_id: productId ? Number(productId) : null,
      expected_close_on: expected || null,
      description: description.trim() || null,
      lost_reason: stage?.kind === "lost" ? lostReason.trim() || null : null,
    };
    if (ownerId) payload.owner_id = Number(ownerId);
    else if (initial) payload.owner_id = null;
    try {
      if (initial) await update.mutateAsync({ id: initial.id, patch: payload });
      else await create.mutateAsync(payload);
      onClose();
    } catch (err) {
      setError((err as { message?: string })?.message ?? t("opportunities.saveFailed"));
    }
  }

  async function handleDelete() {
    if (!initial) return;
    if (!window.confirm(t("opportunities.deleteConfirm", { title: initial.title }))) return;
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
      aria-labelledby="opportunity-dialog-title"
      className="w-full max-w-lg rounded-panel border border-glass bg-surface p-0 text-fg shadow-menu backdrop:bg-backdrop/75"
    >
      <form onSubmit={handleSubmit} className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <h2 id="opportunity-dialog-title" className="text-lg font-medium text-fg">
            {initial ? t("opportunities.edit") : t("opportunities.new")}
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

        <div className="space-y-1.5">
          <Label htmlFor="opp-title" required>
            {t("opportunities.title")}
          </Label>
          <Input
            id="opp-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={255}
            placeholder={t("opportunities.titlePlaceholder")}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="opp-contact-search">{t("conversations.contact.title")}</Label>
          <ContactPicker
            accountId={accountId}
            inputId="opp-contact-search"
            value={contact}
            onChange={setContact}
            locked={Boolean(presetContact)}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="opp-stage">{t("opportunities.stage")}</Label>
            <select
              id="opp-stage"
              value={stageId}
              onChange={(e) => setStageId(e.target.value)}
              className={selectClassName()}
            >
              {pipeline.stages.map((s) => (
                <option key={s.id} value={String(s.id)}>
                  {stageLabel(t, s)}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="opp-expected">{t("opportunities.expectedClose")}</Label>
            <Input
              id="opp-expected"
              type="date"
              value={expected}
              onChange={(e) => setExpected(e.target.value)}
              className="tabular-nums"
            />
          </div>
        </div>

        <div className="grid grid-cols-[1fr_6rem] gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="opp-value">{t("opportunities.value")}</Label>
            <Input
              id="opp-value"
              inputMode="decimal"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              className="tabular-nums"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="opp-currency">{t("opportunities.currency")}</Label>
            <Input
              id="opp-currency"
              value={currency}
              maxLength={8}
              onChange={(e) => setCurrency(e.target.value)}
              placeholder="UYU" // i18n-ignore
            />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="opp-product">{t("agenda.dialog.product")}</Label>
            <select
              id="opp-product"
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
              className={selectClassName()}
            >
              <option value="">{t("agenda.dialog.noProduct")}</option>
              {(products.data ?? [])
                .filter((p) => p.enabled || String(p.id) === productId)
                .map((p) => (
                  <option key={p.id} value={String(p.id)}>
                    {p.name}
                  </option>
                ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="opp-owner">{t("opportunities.owner")}</Label>
            <select
              id="opp-owner"
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

        {stage?.kind === "lost" ? (
          <div className="space-y-1.5">
            <Label htmlFor="opp-lost">{t("opportunities.lostReason")}</Label>
            <Input id="opp-lost" value={lostReason} onChange={(e) => setLostReason(e.target.value)} />
          </div>
        ) : null}

        <div className="space-y-1.5">
          <Label htmlFor="opp-description">{t("opportunities.notes")}</Label>
          <Textarea
            id="opp-description"
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
              {initial ? t("common.saveChanges") : t("opportunities.create")}
            </Button>
          </span>
        </div>
      </form>
    </dialog>
  );
}
