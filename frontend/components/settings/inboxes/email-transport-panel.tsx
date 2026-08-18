"use client";

import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  type InboxDetail,
  type ProbeSide,
  useTestEmailConnection,
  useUpdateInbox,
} from "@/lib/api/inboxes";

/** IMAP and SMTP for one mailbox.
 *
 *  Creating an email inbox asks only for a name and an address, which
 *  leaves both sides switched off — the mailbox neither sends nor
 *  receives until this is filled in. That gap is why the panel exists.
 *
 *  Each side is switched on independently because receive-only and
 *  send-only are both real configurations, not half-finished ones. */
export function EmailTransportPanel({
  accountId,
  inbox,
}: {
  accountId: string;
  inbox: InboxDetail;
}) {
  const update = useUpdateInbox(accountId);
  const probe = useTestEmailConnection(accountId);
  const [form, setForm] = useState({
    imap_enabled: inbox.imap_enabled ?? false,
    imap_address: inbox.imap_address ?? "",
    imap_port: String(inbox.imap_port || 993),
    imap_login: inbox.imap_login ?? "",
    imap_password: "",
    smtp_enabled: inbox.smtp_enabled ?? false,
    smtp_address: inbox.smtp_address ?? "",
    smtp_port: String(inbox.smtp_port || 587),
    smtp_login: inbox.smtp_login ?? "",
    smtp_password: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((f) => ({ ...f, [key]: value }));
    setSaved(false);
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    try {
      await update.mutateAsync({
        id: inbox.id,
        patch: {
          channel: {
            ...form,
            imap_port: Number(form.imap_port) || 0,
            smtp_port: Number(form.smtp_port) || 0,
          },
        },
      });
      // Blank means "keep the stored one", so clearing the inputs after a
      // save leaves the form saying the same thing it did before.
      setForm((f) => ({ ...f, imap_password: "", smtp_password: "" }));
      setSaved(true);
    } catch (err) {
      setError((err as { message?: string })?.message ?? "No se pudo guardar.");
    }
  }

  return (
    <form onSubmit={save} className="space-y-5">
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      <Side
        legend="Recibir (IMAP)"
        hint="Sin esto, los correos que te escriban no entran a la bandeja."
        enabled={form.imap_enabled}
        onToggle={(v) => set("imap_enabled", v)}
        prefix="imap"
        address={form.imap_address}
        port={form.imap_port}
        login={form.imap_login}
        password={form.imap_password}
        passwordSet={inbox.imap_password_set ?? false}
        onChange={set}
      />

      <Side
        legend="Enviar (SMTP)"
        hint="Sin esto, las respuestas de los agentes no salen."
        enabled={form.smtp_enabled}
        onToggle={(v) => set("smtp_enabled", v)}
        prefix="smtp"
        address={form.smtp_address}
        port={form.smtp_port}
        login={form.smtp_login}
        password={form.smtp_password}
        passwordSet={inbox.smtp_password_set ?? false}
        onChange={set}
      />

      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" size="sm" loading={update.isPending}>
          Guardar
        </Button>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          loading={probe.isPending}
          onClick={() => probe.mutate(inbox.id)}
        >
          Probar conexión
        </Button>
        {saved ? (
          <span role="status" className="text-sm text-success">
            Guardado
          </span>
        ) : null}
      </div>

      {probe.data ? (
        <div className="space-y-2" role="status">
          <ProbeRow label="Recibir (IMAP)" side={probe.data.imap} />
          <ProbeRow label="Enviar (SMTP)" side={probe.data.smtp} />
          <p className="text-xs text-fg-muted">
            Se prueba lo guardado, no lo que hay en pantalla. Guardá primero
            si acabás de cambiar algo.
          </p>
        </div>
      ) : null}
    </form>
  );
}

function ProbeRow({ label, side }: { label: string; side: ProbeSide }) {
  if (!side.configured) {
    return (
      <p className="text-sm text-fg-muted">
        {label}: apagado.
      </p>
    );
  }
  if (side.ok) {
    return (
      <p className="text-sm text-success">{label}: conecta bien.</p>
    );
  }
  return (
    <div className="rounded-lg border border-danger/30 bg-danger/5 p-2.5">
      <p className="text-sm font-medium text-danger">{label}: no conecta</p>
      <p className="mt-0.5 text-sm text-fg-muted">{side.error}</p>
    </div>
  );
}

type SideProps = {
  legend: string;
  hint: string;
  enabled: boolean;
  onToggle: (v: boolean) => void;
  prefix: "imap" | "smtp";
  address: string;
  port: string;
  login: string;
  password: string;
  passwordSet: boolean;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onChange: (key: any, value: any) => void;
};

function Side(p: SideProps) {
  return (
    <fieldset className="space-y-3 rounded-lg border border-border p-3">
      <legend className="px-1 text-sm font-semibold text-fg">{p.legend}</legend>
      <label className="flex items-center gap-2 text-sm text-fg">
        <input
          type="checkbox"
          checked={p.enabled}
          onChange={(e) => p.onToggle(e.target.checked)}
          className="h-4 w-4 rounded border-border"
        />
        Activado
      </label>
      <p className="text-xs text-fg-muted">{p.hint}</p>

      <div className="grid gap-3 sm:grid-cols-[1fr_120px]">
        <div className="space-y-1.5">
          <Label htmlFor={`${p.prefix}-address`}>Servidor</Label>
          <Input
            id={`${p.prefix}-address`}
            value={p.address}
            onChange={(e) => p.onChange(`${p.prefix}_address`, e.target.value)}
            placeholder={
              p.prefix === "imap" ? "imap.gmail.com" : "smtp.gmail.com"
            }
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${p.prefix}-port`}>Puerto</Label>
          <Input
            id={`${p.prefix}-port`}
            inputMode="numeric"
            value={p.port}
            onChange={(e) => p.onChange(`${p.prefix}_port`, e.target.value)}
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor={`${p.prefix}-login`}>Usuario</Label>
        <Input
          id={`${p.prefix}-login`}
          value={p.login}
          onChange={(e) => p.onChange(`${p.prefix}_login`, e.target.value)}
          autoComplete="off"
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor={`${p.prefix}-password`}>Contraseña</Label>
        <Input
          id={`${p.prefix}-password`}
          type="password"
          value={p.password}
          onChange={(e) => p.onChange(`${p.prefix}_password`, e.target.value)}
          autoComplete="new-password"
          placeholder={p.passwordSet ? "Ya hay una guardada" : ""}
        />
        <p className="text-xs text-fg-muted">
          {p.passwordSet
            ? "Dejala vacía para conservar la que ya está."
            : "Si tu proveedor tiene verificación en dos pasos, usá una contraseña de aplicación."}
        </p>
      </div>
    </fieldset>
  );
}
