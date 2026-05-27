"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  MCP_SCOPES,
  type MCPScope,
  type MCPTokenInfo,
  type MCPTokenUpdateInput,
} from "@/lib/api/mcp-tokens";

const selectClass =
  "h-11 w-full rounded-md border border-border bg-surface px-3 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

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
  const [name, setName] = useState(initial?.name ?? "");
  const [scope, setScope] = useState<MCPScope>(initial?.scope ?? "read");
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    if (!name.trim()) return setError("El nombre es obligatorio.");
    try {
      await onSubmit({ name: name.trim(), scope });
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? "No se pudo guardar el token.",
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
          Nombre
        </Label>
        <Input
          id="mt-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Ej. agente-soporte"
          maxLength={255}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="mt-scope">Permisos</Label>
        <select
          id="mt-scope"
          className={selectClass}
          value={scope}
          onChange={(e) => setScope(e.target.value as MCPScope)}
        >
          {MCP_SCOPES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
        <p className="text-xs text-fg-muted">
          {MCP_SCOPES.find((s) => s.value === scope)?.hint}
        </p>
      </div>

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {initial ? "Guardar cambios" : "Generar token"}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancelar
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
