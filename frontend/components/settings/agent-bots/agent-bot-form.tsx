"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { AgentBot, AgentBotInput } from "@/lib/api/agent-bots";

export function AgentBotForm({
  initial,
  submitting,
  onSubmit,
  onCancel,
}: {
  initial?: AgentBot;
  submitting?: boolean;
  onSubmit: (input: AgentBotInput) => Promise<void> | void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [outgoingUrl, setOutgoingUrl] = useState(initial?.outgoing_url ?? "");
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    if (!name.trim()) return setError("El nombre es obligatorio.");
    try {
      await onSubmit({
        name: name.trim(),
        description: description.trim() || null,
        outgoing_url: outgoingUrl.trim() || null,
      });
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? "No se pudo guardar el bot.",
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
        <Label htmlFor="ab-name" required>
          Nombre
        </Label>
        <Input
          id="ab-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="ab-desc">Descripción</Label>
        <Textarea
          id="ab-desc"
          rows={2}
          value={description ?? ""}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="ab-url">URL de salida</Label>
        <Input
          id="ab-url"
          type="url"
          value={outgoingUrl ?? ""}
          onChange={(e) => setOutgoingUrl(e.target.value)}
          placeholder="https://…"
        />
        <p className="text-xs text-fg-muted">
          El backend enviará los eventos de mensaje a esta URL.
        </p>
      </div>

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {initial ? "Guardar cambios" : "Crear bot"}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
