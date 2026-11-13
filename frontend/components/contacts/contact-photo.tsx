"use client";

import { Camera, X } from "lucide-react";
import { useRef, useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import {
  CONTACT_PHOTO_TYPES,
  type Contact,
  ContactPhotoRejected,
  useContactPhoto,
} from "@/lib/api/contacts";
import { useT } from "@/lib/i18n/provider";

/** The contact's picture on their page; click it to upload one. */
export function ContactPhoto({
  accountId,
  contact,
  name,
}: {
  accountId: string;
  contact: Contact;
  name: string;
}) {
  const t = useT();
  const input = useRef<HTMLInputElement>(null);
  const { upload, remove } = useContactPhoto(accountId, contact.id);
  const [error, setError] = useState<string | null>(null);
  const busy = upload.isPending || remove.isPending;

  async function pick(file: File | undefined) {
    if (!file) return;
    setError(null);
    try {
      await upload.mutateAsync(file);
    } catch (err) {
      setError(t(err instanceof ContactPhotoRejected ? "contacts.photo.invalid" : "contacts.photo.failed"));
    } finally {
      if (input.current) input.current.value = "";
    }
  }

  async function drop() {
    setError(null);
    try {
      await remove.mutateAsync();
    } catch {
      setError(t("contacts.photo.failed"));
    }
  }

  return (
    <div className="relative shrink-0">
      <button
        type="button"
        onClick={() => input.current?.click()}
        disabled={busy}
        aria-label={t("contacts.photo.change")}
        title={t("contacts.photo.change")}
        className="group relative block rounded-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon disabled:opacity-60"
      >
        <Avatar name={name} src={contact.thumbnail || undefined} size="xl" />
        <span className="absolute inset-0 grid place-items-center rounded-full bg-black/45 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
          <Camera className="h-5 w-5 text-white" aria-hidden />
        </span>
      </button>
      {contact.thumbnail ? (
        <button
          type="button"
          onClick={() => void drop()}
          disabled={busy}
          aria-label={t("contacts.photo.remove")}
          title={t("contacts.photo.remove")}
          className="absolute -right-1 -top-1 grid h-6 w-6 place-items-center rounded-full border border-glass bg-surface text-fg-muted hover:text-danger focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
        >
          <X className="h-3.5 w-3.5" aria-hidden />
        </button>
      ) : null}
      <input
        ref={input}
        type="file"
        accept={CONTACT_PHOTO_TYPES.join(",")}
        className="hidden"
        onChange={(e) => void pick(e.target.files?.[0])}
      />
      {error ? (
        <p role="alert" className="absolute left-0 top-full mt-1 w-56 text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
