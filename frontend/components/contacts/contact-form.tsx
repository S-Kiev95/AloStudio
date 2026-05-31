"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Contact, ContactInput } from "@/lib/api/contacts";
import { useCustomAttributes } from "@/lib/api/custom-attributes";

import { CustomAttributeInput } from "./custom-attribute-input";

export function ContactForm({
  accountId,
  initial,
  submitting,
  onSubmit,
  onCancel,
}: {
  accountId: string;
  initial?: Contact;
  submitting?: boolean;
  onSubmit: (input: ContactInput) => Promise<void> | void;
  onCancel: () => void;
}) {
  const customAttrs = useCustomAttributes(accountId, "contact_attribute");

  const [name, setName] = useState(initial?.name ?? "");
  const [email, setEmail] = useState(initial?.email ?? "");
  const [phone, setPhone] = useState(initial?.phone_number ?? "");
  const [identifier, setIdentifier] = useState(initial?.identifier ?? "");
  const [blocked, setBlocked] = useState(initial?.blocked ?? false);
  const [customValues, setCustomValues] = useState<Record<string, unknown>>(
    initial?.custom_attributes ?? {},
  );
  const [error, setError] = useState<string | null>(null);

  function setCustom(key: string, value: unknown) {
    setCustomValues((prev) => {
      if (value === null || value === undefined || value === "") {
        // Drop the key; rebuild without it.
        const next: Record<string, unknown> = {};
        for (const k of Object.keys(prev)) {
          if (k !== key) next[k] = prev[k];
        }
        return next;
      }
      return { ...prev, [key]: value };
    });
  }

  async function submit() {
    setError(null);
    if (!name.trim() && !email.trim() && !phone.trim()) {
      return setError(
        "Necesitamos al menos un nombre, email o teléfono para identificar al contacto.",
      );
    }
    try {
      await onSubmit({
        name: name.trim() || undefined,
        email: email.trim() || null,
        phone_number: phone.trim() || null,
        identifier: identifier.trim() || null,
        blocked,
        custom_attributes: customValues,
      });
    } catch (e) {
      setError(
        (e as { message?: string })?.message ??
          "No se pudo guardar el contacto.",
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

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="c-name">Nombre</Label>
          <Input
            id="c-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={255}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="c-email">Email</Label>
          <Input
            id="c-email"
            type="email"
            value={email ?? ""}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="c-phone">Teléfono</Label>
          <Input
            id="c-phone"
            type="tel"
            value={phone ?? ""}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+598…"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="c-id">Identificador externo</Label>
          <Input
            id="c-id"
            value={identifier ?? ""}
            onChange={(e) => setIdentifier(e.target.value)}
            placeholder="ID en tu CRM"
          />
        </div>
      </div>

      <label className="flex items-center gap-2 text-sm text-fg">
        <input
          type="checkbox"
          checked={blocked}
          onChange={(e) => setBlocked(e.target.checked)}
        />
        Contacto bloqueado
      </label>

      {customAttrs.data?.length ? (
        <div className="space-y-3 rounded-md border border-border bg-surface p-3">
          <p className="text-xs font-medium uppercase text-fg-muted">
            Atributos personalizados
          </p>
          {customAttrs.data.map((attr) => (
            <div key={attr.id} className="space-y-1.5">
              <Label htmlFor={`ca-${attr.attribute_key}`}>
                {attr.attribute_display_name}
              </Label>
              <CustomAttributeInput
                attribute={attr}
                value={customValues[attr.attribute_key]}
                onChange={(v) => setCustom(attr.attribute_key, v)}
              />
              {attr.attribute_description ? (
                <p className="text-xs text-fg-muted">
                  {attr.attribute_description}
                </p>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {initial ? "Guardar cambios" : "Crear contacto"}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
