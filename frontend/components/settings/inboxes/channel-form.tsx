"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, type ReactNode, useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/errors";
import { type ChannelPayload, useCreateInbox } from "@/lib/api/inboxes";
import { channelDef, type ChannelDef } from "@/lib/inboxes/channel-catalog";

export function ChannelForm({
  accountId,
  channel,
}: {
  accountId: string;
  channel: string;
}) {
  const def = channelDef(channel);
  const router = useRouter();
  const create = useCreateInbox(accountId);
  const [name, setName] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const inboxesHref = `/accounts/${accountId}/settings/inboxes`;

  if (!def) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-danger">Canal desconocido: {channel}</p>
        <Link href={`${inboxesHref}/new`} className={buttonVariants({ size: "sm" })}>
          Elegir un canal
        </Link>
      </div>
    );
  }

  function setField(n: string, v: string) {
    setValues((prev) => ({ ...prev, [n]: v }));
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError("El nombre de la bandeja es obligatorio.");
      return;
    }
    for (const f of def!.fields) {
      if (f.required && !values[f.name]?.trim()) {
        setError(`Falta el campo: ${f.label}`);
        return;
      }
    }
    try {
      await create.mutateAsync({
        name: name.trim(),
        channel: buildChannel(def!, values),
      });
      router.push(inboxesHref);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "No se pudo crear el canal.",
      );
    }
  }

  return (
    <div className="max-w-lg space-y-4">
      <div>
        <Link
          href={`${inboxesHref}/new`}
          className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-fg"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          Cambiar canal
        </Link>
        <h2 className="mt-2 text-xl font-semibold text-fg">{def.label}</h2>
        <p className="text-sm text-fg-muted">{def.blurb}</p>
      </div>

      <form
        onSubmit={submit}
        className="space-y-4 rounded-lg border border-border bg-surface p-4"
      >
        <Field label="Nombre de la bandeja" required>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Mi canal"
          />
        </Field>

        {def.fields.map((f) => (
          <Field key={f.name} label={f.label} required={f.required} help={f.help}>
            {f.type === "select" ? (
              <select
                value={values[f.name] ?? f.options?.[0]?.value ?? ""}
                onChange={(e) => setField(f.name, e.target.value)}
                className="h-11 w-full rounded-md border border-border bg-surface px-3 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
              >
                {f.options?.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            ) : (
              <Input
                type={f.type === "password" ? "password" : "text"}
                value={values[f.name] ?? ""}
                onChange={(e) => setField(f.name, e.target.value)}
                placeholder={f.placeholder}
              />
            )}
          </Field>
        ))}

        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}

        <div className="flex justify-end gap-2">
          <Link
            href={inboxesHref}
            className={buttonVariants({ variant: "secondary", size: "sm" })}
          >
            Cancelar
          </Link>
          <Button type="submit" size="sm" loading={create.isPending}>
            Crear canal
          </Button>
        </div>
      </form>
    </div>
  );
}

function Field({
  label,
  required,
  help,
  children,
}: {
  label: string;
  required?: boolean;
  help?: string;
  children: ReactNode;
}) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium text-fg">
        {label}
        {required ? <span className="text-danger"> *</span> : null}
      </span>
      {children}
      {help ? <span className="block text-xs text-fg-muted">{help}</span> : null}
    </label>
  );
}

/** Assemble the `channel` sub-hash from flat field values, nesting dotted
 *  paths (`provider_config.api_key`) and injecting the channel's `fixed`
 *  constants. */
function buildChannel(
  def: ChannelDef,
  values: Record<string, string>,
): ChannelPayload {
  const channel: Record<string, unknown> = {
    type: def.type,
    ...(def.fixed ?? {}),
  };
  for (const f of def.fields) {
    let val: string | undefined = values[f.name];
    if ((val === undefined || val === "") && f.type === "select") {
      val = f.options?.[0]?.value;
    }
    if (val === undefined || val === "") continue;
    const parts = f.name.split(".");
    let cur = channel;
    for (let i = 0; i < parts.length - 1; i++) {
      const key = parts[i];
      if (typeof cur[key] !== "object" || cur[key] === null) cur[key] = {};
      cur = cur[key] as Record<string, unknown>;
    }
    cur[parts[parts.length - 1]] = val;
  }
  return channel as ChannelPayload;
}
