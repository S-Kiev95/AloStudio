"use client";

import { Check, Copy, Download, Pencil, Plus, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useIsAccountAdmin } from "@/lib/api/profile";
import {
  type WhatsappQrCode,
  useCreateWhatsappQr,
  useDeleteWhatsappQr,
  useUpdateWhatsappQr,
  useWhatsappQrCodes,
} from "@/lib/api/whatsapp-business";

const MESSAGE_MAX = 140;

/** `wa.me` link for a number, with the first message already written. */
export function waMeLink(phone: string | null | undefined, text: string): string {
  const digits = (phone ?? "").replace(/\D/g, "");
  const query = text.trim() ? `?text=${encodeURIComponent(text.trim())}` : "";
  return `https://wa.me/${digits}${query}`;
}

function CopyButton({ value, label = "Copiar" }: { value: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <Button
      type="button"
      variant="secondary"
      size="sm"
      onClick={() => {
        void navigator.clipboard?.writeText(value);
        setDone(true);
        window.setTimeout(() => setDone(false), 1500);
      }}
    >
      {done ? <Check className="h-3.5 w-3.5" aria-hidden /> : <Copy className="h-3.5 w-3.5" aria-hidden />}
      {done ? "Copiado" : label}
    </Button>
  );
}

function QrCard({
  qr,
  isAdmin,
  onSave,
  onDelete,
  busy,
}: {
  qr: WhatsappQrCode;
  isAdmin: boolean;
  onSave: (message: string) => Promise<void>;
  onDelete: () => Promise<void>;
  busy: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [message, setMessage] = useState(qr.prefilled_message ?? "");
  return (
    <li className="flex flex-col gap-4 rounded-xl border border-glass bg-surface p-4 sm:flex-row">
      {qr.qr_image_url ? (
        // eslint-disable-next-line @next/next/no-img-element -- Meta's CDN, no next/image loader
        <img
          src={qr.qr_image_url}
          alt={`Código QR: ${qr.prefilled_message ?? ""}`}
          className="h-36 w-36 shrink-0 rounded-lg bg-white p-1"
        />
      ) : null}
      <div className="min-w-0 flex-1 space-y-3">
        {editing ? (
          <div className="space-y-2">
            <Textarea
              aria-label="Mensaje inicial"
              rows={2}
              maxLength={MESSAGE_MAX}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
            />
            <div className="flex gap-2">
              <Button
                type="button"
                size="sm"
                loading={busy}
                onClick={() => void onSave(message).then(() => setEditing(false))}
              >
                Guardar
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(false)}>
                Cancelar
              </Button>
            </div>
          </div>
        ) : (
          <p className="whitespace-pre-wrap text-sm text-fg">“{qr.prefilled_message}”</p>
        )}
        {qr.deep_link_url ? (
          <p className="break-all font-mono text-xs text-fg-muted">{qr.deep_link_url}</p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          {qr.deep_link_url ? <CopyButton value={qr.deep_link_url} label="Copiar link" /> : null}
          {qr.qr_image_url ? (
            <a
              href={qr.qr_image_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-9 items-center gap-2 rounded-control border border-glass bg-surface-2 px-3.5 text-sm font-medium text-fg hover:bg-hover-glass"
            >
              <Download className="h-3.5 w-3.5" aria-hidden />
              Descargar QR
            </a>
          ) : null}
          {isAdmin && !editing ? (
            <>
              <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(true)}>
                <Pencil className="h-3.5 w-3.5" aria-hidden />
                Editar
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="text-danger hover:text-danger"
                loading={busy}
                onClick={() => void onDelete()}
              >
                <Trash2 className="h-3.5 w-3.5" aria-hidden />
                Borrar
              </Button>
            </>
          ) : null}
        </div>
      </div>
    </li>
  );
}

/** Ways into the chat from outside: a plain wa.me link and Meta's QR codes
 *  (image + short link, with the first message already written). */
export function LinkQrPanel({
  accountId,
  inboxId,
  phoneNumber,
}: {
  accountId: string;
  inboxId: number;
  phoneNumber: string | null;
}) {
  const isAdmin = useIsAccountAdmin(accountId);
  const qrQ = useWhatsappQrCodes(accountId, inboxId);
  const create = useCreateWhatsappQr(accountId, inboxId);
  const update = useUpdateWhatsappQr(accountId, inboxId);
  const remove = useDeleteWhatsappQr(accountId, inboxId);
  const [linkText, setLinkText] = useState("Hola, quiero más información");
  const [newMessage, setNewMessage] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
    } catch (err) {
      setError((err as Error).message || "Meta rechazó el pedido.");
    }
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    await run(async () => {
      await create.mutateAsync(newMessage);
      setNewMessage("");
    });
  }

  const link = waMeLink(phoneNumber, linkText);

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-fg">Link directo</h3>
        <p className="text-sm text-fg-muted">
          Para la web, la firma del correo o la bio de Instagram: abre el chat con
          este número y el mensaje ya escrito.
        </p>
        <div className="space-y-1.5">
          <Label htmlFor="wa-link-text">Mensaje inicial</Label>
          <Input
            id="wa-link-text"
            value={linkText}
            onChange={(e) => setLinkText(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <code className="min-w-0 flex-1 break-all rounded-lg border border-glass bg-surface-2 px-3 py-2 text-xs text-fg">
            {link}
          </code>
          <CopyButton value={link} />
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-fg">Códigos QR</h3>
        <p className="text-sm text-fg-muted">
          Para carteles, folletos o la puerta: al escanearlo se abre el chat con el
          mensaje escrito. Meta guarda la imagen y un link corto.
        </p>
        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}
        {isAdmin ? (
          <form onSubmit={(e) => void onCreate(e)} className="flex flex-wrap items-end gap-2">
            <div className="min-w-[240px] flex-1 space-y-1.5">
              <Label htmlFor="wa-qr-new">Mensaje del QR nuevo</Label>
              <Input
                id="wa-qr-new"
                value={newMessage}
                maxLength={MESSAGE_MAX}
                onChange={(e) => setNewMessage(e.target.value)}
                placeholder="Ej.: Hola, vi el cartel de los cursos"
              />
            </div>
            <Button type="submit" size="sm" loading={create.isPending} disabled={!newMessage.trim()}>
              <Plus className="h-4 w-4" aria-hidden />
              Crear QR
            </Button>
          </form>
        ) : null}
        {qrQ.isLoading ? (
          <p className="text-sm text-fg-muted">Consultando a Meta…</p>
        ) : qrQ.isError ? (
          <p role="alert" className="text-sm text-danger">
            {(qrQ.error as Error | null)?.message ?? "No se pudieron leer los QR."}
          </p>
        ) : (qrQ.data ?? []).length === 0 ? (
          <p className="text-sm text-fg-muted">Todavía no hay códigos QR.</p>
        ) : (
          <ul className="grid gap-3 xl:grid-cols-2">
            {(qrQ.data ?? []).map((qr) => (
              <QrCard
                key={qr.code}
                qr={qr}
                isAdmin={isAdmin}
                busy={update.isPending || remove.isPending}
                onSave={(message) =>
                  run(() => update.mutateAsync({ code: qr.code, message }))
                }
                onDelete={() =>
                  window.confirm("¿Borrar este QR? Los carteles impresos dejan de funcionar.")
                    ? run(() => remove.mutateAsync(qr.code))
                    : Promise.resolve()
                }
              />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
