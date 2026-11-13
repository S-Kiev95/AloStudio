"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClassName } from "@/components/ui/select";
import {
  MCP_SCOPES,
  type MCPScope,
  type MCPTokenInfo,
  type MCPTokenUpdateInput,
} from "@/lib/api/mcp-tokens";
import { useT } from "@/lib/i18n/provider";

export function TokenForm({
  initial,
  submitting,
  onSubmit,
  onCancel,
}: {
  initial?: MCPTokenInfo;
  submitting?: boolean;
  onSubmit: (input: { name: string; scope: MCPScope }) => Promise<void> | void;
  onCancel: () => void;
}) {
  const t = useT();
  const [name, setName] = useState(initial?.name ?? "");
  const [scope, setScope] = useState<MCPScope>(initial?.scope ?? "read");
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    if (!name.trim()) return setError(t("profile.nameRequired"));
    try {
      await onSubmit({ name: name.trim(), scope });
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? t("settingsMcp.saveFailed"),
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
        <Label htmlFor="mt-name" required>
          {t("profile.name")}
        </Label>
        <Input
          id="mt-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("settingsMcp.namePlaceholder")}
          maxLength={255}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="mt-scope">{t("settingsMcp.permissions")}</Label>
        <select
          id="mt-scope"
          className={selectClassName()}
          value={scope}
          onChange={(e) => setScope(e.target.value as MCPScope)}
        >
          {MCP_SCOPES.map((s) => (
            <option key={s.value} value={s.value}>
              {t(s.label)}
            </option>
          ))}
        </select>
        <p className="text-xs text-fg-muted">
          {t(MCP_SCOPES.find((s) => s.value === scope)?.hint ?? MCP_SCOPES[0].hint)}
        </p>
      </div>

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {initial ? t("common.saveChanges") : t("settingsMcp.generate")}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          {t("actions.cancel")}
        </Button>
      </div>
    </div>
  );
}

export function TokenInputAdapter({
  initial,
  submitting,
  onUpdate,
  onCancel,
}: {
  initial: MCPTokenInfo;
  submitting?: boolean;
  onUpdate: (patch: MCPTokenUpdateInput) => Promise<void>;
  onCancel: () => void;
}) {
  return (
    <TokenForm
      initial={initial}
      submitting={submitting}
      onSubmit={async ({ name, scope }) =>
        onUpdate({
          ...(name !== initial.name ? { name } : {}),
          ...(scope !== initial.scope ? { scope } : {}),
        })
      }
      onCancel={onCancel}
    />
  );
}
