"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type {
  CannedResponse,
  CannedResponseInput,
} from "@/lib/api/canned-responses";
import { useT } from "@/lib/i18n/provider";
import { rich } from "@/lib/i18n/rich";

export function CannedResponseForm({
  initial,
  submitting,
  onSubmit,
  onCancel,
}: {
  initial?: CannedResponse;
  submitting?: boolean;
  onSubmit: (input: CannedResponseInput) => Promise<void> | void;
  onCancel: () => void;
}) {
  const t = useT();
  const [shortCode, setShortCode] = useState(initial?.short_code ?? "");
  const [content, setContent] = useState(initial?.content ?? "");
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    if (!shortCode.trim()) return setError(t("settingsCanned.shortCodeRequired"));
    if (!content.trim()) return setError(t("settingsCanned.contentRequired"));
    try {
      await onSubmit({
        short_code: shortCode.trim(),
        content: content.trim(),
      });
    } catch (e) {
      setError(
        (e as { message?: string })?.message ??
          t("settingsCanned.saveFailed"),
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
        <Label htmlFor="cr-code" required>
          {t("settingsCanned.shortCode")}
        </Label>
        <Input
          id="cr-code"
          value={shortCode}
          onChange={(e) => setShortCode(e.target.value)}
          placeholder="saludo"
          maxLength={255}
        />
        <p className="text-xs text-fg-muted">
          {rich(t("settingsCanned.shortCodeHint"), {
            code: <code>/{shortCode.trim() || t("settingsCanned.shortCodeExample")}</code>,
          })}
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="cr-content" required>
          {t("settingsCanned.content")}
        </Label>
        <Textarea
          id="cr-content"
          rows={4}
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
      </div>

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {initial ? t("common.saveChanges") : t("settingsCanned.create")}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          {t("actions.cancel")}
        </Button>
      </div>
    </div>
  );
}
