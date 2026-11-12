"use client";

import { Eye, EyeOff, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type Label as LabelType,
  type LabelInput,
  useCreateLabel,
  useDeleteLabel,
  useLabels,
  useUpdateLabel,
} from "@/lib/api/labels";

import { LabelForm } from "./label-form";
import { useT } from "@/lib/i18n/provider";

export function LabelsView({ accountId }: { accountId: string }) {
  const t = useT();
  const { data, isLoading, isError } = useLabels(accountId);
  const create = useCreateLabel(accountId);
  const update = useUpdateLabel(accountId);

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<LabelType | null>(null);

  async function handleCreate(input: LabelInput) {
    await create.mutateAsync(input);
    setCreating(false);
  }

  async function handleUpdate(input: LabelInput) {
    if (!editing) return;
    await update.mutateAsync({ id: editing.id, patch: input });
    setEditing(null);
  }

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-medium text-fg">{t("settings.items.labels")}</h2>
        {!creating && !editing ? (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            {t("settingsLabels.new")}
          </Button>
        ) : null}
      </div>

      {creating ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("settingsLabels.new")}</CardTitle>
          </CardHeader>
          <CardContent>
            <LabelForm
              submitting={create.isPending}
              onSubmit={handleCreate}
              onCancel={() => setCreating(false)}
            />
          </CardContent>
        </Card>
      ) : null}

      {editing ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("settingsLabels.edit")}</CardTitle>
          </CardHeader>
          <CardContent>
            <LabelForm
              initial={editing}
              submitting={update.isPending}
              onSubmit={handleUpdate}
              onCancel={() => setEditing(null)}
            />
          </CardContent>
        </Card>
      ) : null}

      <div className="overflow-hidden rounded-md border border-glass bg-surface">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            {t("settingsLabels.loadFailed")}
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            {t("settingsLabels.empty")}
          </p>
        ) : (
          <ul className="divide-y divide-glass">
            {data?.map((l) => (
              <LabelRow
                key={l.id}
                accountId={accountId}
                label={l}
                onEdit={() => {
                  setCreating(false);
                  setEditing(l);
                }}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function LabelRow({
  accountId,
  label,
  onEdit,
}: {
  accountId: string;
  label: LabelType;
  onEdit: () => void;
}) {
  const t = useT();
  const del = useDeleteLabel(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onDelete() {
    if (!window.confirm(t("instagram.answers.deleteConfirm", { name: label.title }))) return;
    setError(null);
    try {
      await del.mutateAsync(label.id);
    } catch (e) {
      setError((e as { message?: string })?.message ?? t("actions.deleteFailed"));
    }
  }

  return (
    <li className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-hover-glass">
      <span
        className="h-5 w-5 shrink-0 rounded-full border border-glass"
        aria-hidden
        style={{ backgroundColor: label.color ?? "transparent" }}
      />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-fg">{label.title}</p>
        {label.description ? (
          <p className="truncate text-xs text-fg-muted">{label.description}</p>
        ) : null}
        {error ? (
          <p role="alert" className="text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
      <span
        className="flex items-center gap-1 text-xs text-fg-muted"
        title={
          label.show_on_sidebar
            ? t("settingsLabels.visibleInSidebar")
            : t("settingsLabels.hiddenInSidebar")
        }
      >
        {label.show_on_sidebar ? (
          <Eye className="h-4 w-4" aria-hidden />
        ) : (
          <EyeOff className="h-4 w-4" aria-hidden />
        )}
      </span>
      <button
        type="button"
        aria-label={t("actions.edit")}
        title={t("actions.edit")}
        onClick={onEdit}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Pencil className="h-4 w-4" aria-hidden />
      </button>
      <button
        type="button"
        aria-label={t("actions.delete")}
        title={t("actions.delete")}
        onClick={onDelete}
        disabled={del.isPending}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
    </li>
  );
}
