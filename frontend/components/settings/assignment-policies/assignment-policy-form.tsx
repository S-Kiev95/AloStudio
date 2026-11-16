"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClassName } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type {
  AssignmentPolicy,
  AssignmentPolicyInput,
  ConversationPriority,
} from "@/lib/api/assignment-policies";
import { useT } from "@/lib/i18n/provider";
import { rich } from "@/lib/i18n/rich";
import type { MessageKey } from "@/lib/i18n/translate";

const PRIORITY_LABELS: Record<ConversationPriority, MessageKey> = {
  earliest_created: "settingsAssign.priority.earliest_created",
  longest_waiting: "settingsAssign.priority.longest_waiting",
};

export function AssignmentPolicyForm({
  initial,
  submitting,
  onSubmit,
  onCancel,
}: {
  initial?: AssignmentPolicy;
  submitting?: boolean;
  onSubmit: (input: AssignmentPolicyInput) => Promise<void> | void;
  onCancel: () => void;
}) {
  const t = useT();
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [enabled, setEnabled] = useState(initial?.enabled ?? true);
  const [priority, setPriority] = useState<ConversationPriority>(
    initial?.conversation_priority ?? "earliest_created",
  );
  const [limit, setLimit] = useState(
    String(initial?.fair_distribution_limit ?? 100),
  );
  const [windowSecs, setWindowSecs] = useState(
    String(initial?.fair_distribution_window ?? 3600),
  );
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    if (!name.trim()) return setError(t("profile.nameRequired"));
    const limitNum = Number(limit);
    const windowNum = Number(windowSecs);
    if (!Number.isInteger(limitNum) || limitNum <= 0) {
      return setError(t("settingsAssign.limitInvalid"));
    }
    if (!Number.isInteger(windowNum) || windowNum <= 0) {
      return setError(t("settingsAssign.windowInvalid"));
    }
    try {
      await onSubmit({
        name: name.trim(),
        description: description.trim() || null,
        enabled,
        conversation_priority: priority,
        fair_distribution_limit: limitNum,
        fair_distribution_window: windowNum,
      });
    } catch (e) {
      setError(
        (e as { message?: string })?.message ??
          t("settingsAssign.saveFailed"),
      );
    }
  }

  return (
    <div className="space-y-4">
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className="space-y-1.5">
        <Label htmlFor="ap-name" required>
          {t("profile.name")}
        </Label>
        <Input
          id="ap-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("settingsAssign.fairDistribution")}
          maxLength={255}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="ap-description">{t("products.description")}</Label>
        <Textarea
          id="ap-description"
          rows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder={t("settingsAssign.optional")}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="ap-priority">{t("settingsAssign.priorityLabel")}</Label>
        <select
          id="ap-priority"
          className={selectClassName()}
          value={priority}
          onChange={(e) =>
            setPriority(e.target.value as ConversationPriority)
          }
        >
          <option value="earliest_created">
            {t(PRIORITY_LABELS.earliest_created)}
          </option>
          <option value="longest_waiting">
            {t(PRIORITY_LABELS.longest_waiting)}
          </option>
        </select>
        <p className="text-xs text-fg-muted">
          {t("settingsAssign.priorityHint")}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="ap-limit" required>
            {t("settingsAssign.limitPerAgent")}
          </Label>
          <Input
            id="ap-limit"
            type="number"
            min={1}
            value={limit}
            onChange={(e) => setLimit(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="ap-window" required>
            {t("settingsAssign.windowSeconds")}
          </Label>
          <Input
            id="ap-window"
            type="number"
            min={1}
            value={windowSecs}
            onChange={(e) => setWindowSecs(e.target.value)}
          />
        </div>
      </div>
      <p className="text-xs text-fg-muted">
        {rich(t("settingsAssign.limitSentence"), {
          limit: <strong>{limit || "?"}</strong>,
          window: <strong>{windowSecs || "?"}</strong>,
        })}
      </p>

      <label className="flex items-center gap-2 text-sm text-fg">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
          className="h-4 w-4 rounded border-glass accent-neon focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        {t("settingsAssign.active")}
      </label>

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {initial ? t("common.saveChanges") : t("settingsAssign.create")}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          {t("actions.cancel")}
        </Button>
      </div>
    </div>
  );
}
