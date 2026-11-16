"use client";

import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type AssignmentPolicy,
  type AssignmentPolicyInput,
  useAssignmentPolicies,
  useCreateAssignmentPolicy,
  useDeleteAssignmentPolicy,
  useUpdateAssignmentPolicy,
} from "@/lib/api/assignment-policies";

import { AssignmentPolicyForm } from "./assignment-policy-form";
import { useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

const PRIORITY_LABELS: Record<string, MessageKey> = {
  earliest_created: "settingsAssign.priority.earliest_created",
  longest_waiting: "settingsAssign.priority.longest_waiting",
};

export function AssignmentPoliciesView({ accountId }: { accountId: string }) {
  const t = useT();
  const { data, isLoading, isError } = useAssignmentPolicies(accountId);
  const create = useCreateAssignmentPolicy(accountId);
  const update = useUpdateAssignmentPolicy(accountId);

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<AssignmentPolicy | null>(null);

  async function handleCreate(input: AssignmentPolicyInput) {
    await create.mutateAsync(input);
    setCreating(false);
  }

  async function handleUpdate(input: AssignmentPolicyInput) {
    if (!editing) return;
    await update.mutateAsync({ id: editing.id, patch: input });
    setEditing(null);
  }

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-medium text-fg">
            {t("settings.items.assignment_policies")}
          </h2>
          <p className="text-sm text-fg-muted">
            {t("settingsAssign.subtitle")}
          </p>
        </div>
        {!creating && !editing ? (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            {t("settingsAssign.new")}
          </Button>
        ) : null}
      </div>

      {creating ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("settingsAssign.new")}</CardTitle>
          </CardHeader>
          <CardContent>
            <AssignmentPolicyForm
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
            <CardTitle>{t("settingsAssign.edit")}</CardTitle>
          </CardHeader>
          <CardContent>
            <AssignmentPolicyForm
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
            {t("settingsAssign.loadFailed")}
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            {t("settingsAssign.empty")}
          </p>
        ) : (
          <ul className="divide-y divide-glass">
            {data?.map((policy) => (
              <PolicyRow
                key={policy.id}
                accountId={accountId}
                policy={policy}
                onEdit={() => {
                  setCreating(false);
                  setEditing(policy);
                }}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function PolicyRow({
  accountId,
  policy,
  onEdit,
}: {
  accountId: string;
  policy: AssignmentPolicy;
  onEdit: () => void;
}) {
  const t = useT();
  const del = useDeleteAssignmentPolicy(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onDelete() {
    if (!window.confirm(t("settingsAssign.deleteConfirm", { name: policy.name }))) return;
    setError(null);
    try {
      await del.mutateAsync(policy.id);
    } catch (e) {
      setError((e as { message?: string })?.message ?? t("actions.deleteFailed"));
    }
  }

  return (
    <li className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-hover-glass">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="truncate text-sm font-medium text-fg">{policy.name}</p>
          {!policy.enabled ? (
            <span className="rounded-sm bg-surface-2 px-1.5 py-0.5 text-[10px] uppercase text-fg-muted">
              {t("campaigns.inactive")}
            </span>
          ) : null}
        </div>
        <p className="truncate font-numeric text-xs tabular-nums text-fg-muted">
          {PRIORITY_LABELS[policy.conversation_priority]
            ? t(PRIORITY_LABELS[policy.conversation_priority])
            : policy.conversation_priority}
          {" · "}
          {t("settingsAssign.perWindow", {
            limit: policy.fair_distribution_limit,
            secs: policy.fair_distribution_window,
          })}
        </p>
        {error ? (
          <p role="alert" className="text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
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
