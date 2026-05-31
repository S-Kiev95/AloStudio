"use client";

import { ArrowLeft, Mail, Phone, User as UserIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type ContactInput,
  useContact,
  useUpdateContact,
} from "@/lib/api/contacts";
import { cn } from "@/lib/utils";

import { ContactForm } from "./contact-form";
import { ContactableInboxesPanel } from "./contactable-inboxes-panel";
import { NotesPanel } from "./notes-panel";

type Tab = "info" | "notes" | "inboxes";

const TABS: { value: Tab; label: string }[] = [
  { value: "info", label: "Información" },
  { value: "notes", label: "Notas" },
  { value: "inboxes", label: "Bandejas" },
];

export function ContactDetailView({
  accountId,
  contactId,
}: {
  accountId: string;
  contactId: number;
}) {
  const router = useRouter();
  const { data: contact, isLoading, isError } = useContact(
    accountId,
    contactId,
  );
  const update = useUpdateContact(accountId);
  const [tab, setTab] = useState<Tab>("info");

  async function handleUpdate(input: ContactInput) {
    await update.mutateAsync({ id: contactId, patch: input });
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <Link
        href={`/accounts/${accountId}/contacts`}
        className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-fg"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Volver a contactos
      </Link>

      {isLoading ? (
        <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
      ) : isError || !contact ? (
        <p role="alert" className="p-8 text-center text-sm text-danger">
          No se pudo cargar el contacto.
        </p>
      ) : (
        <>
          <div className="flex items-center gap-3">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
              <UserIcon className="h-5 w-5" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-xl font-semibold text-fg">
                {contact.name?.trim() ||
                  contact.email?.trim() ||
                  contact.phone_number?.trim() ||
                  `Contacto #${contact.id}`}
              </h2>
              <p className="flex flex-wrap items-center gap-3 text-xs text-fg-muted">
                {contact.email ? (
                  <span className="flex items-center gap-1">
                    <Mail className="h-3 w-3" aria-hidden />
                    {contact.email}
                  </span>
                ) : null}
                {contact.phone_number ? (
                  <span className="flex items-center gap-1">
                    <Phone className="h-3 w-3" aria-hidden />
                    {contact.phone_number}
                  </span>
                ) : null}
                {contact.identifier ? `id ${contact.identifier}` : null}
              </p>
            </div>
            {contact.blocked ? (
              <span className="rounded-full bg-danger/10 px-2 py-0.5 text-xs font-medium text-danger">
                Bloqueado
              </span>
            ) : null}
          </div>

          <div className="flex gap-1 border-b border-border">
            {TABS.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => setTab(t.value)}
                aria-pressed={tab === t.value}
                className={cn(
                  "-mb-px border-b-2 px-3 py-2 text-sm font-medium",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  tab === t.value
                    ? "border-primary text-fg"
                    : "border-transparent text-fg-muted hover:text-fg",
                )}
              >
                {t.label}
              </button>
            ))}
          </div>

          {tab === "info" ? (
            <Card>
              <CardHeader>
                <CardTitle>Datos del contacto</CardTitle>
              </CardHeader>
              <CardContent>
                <ContactForm
                  accountId={accountId}
                  initial={contact}
                  submitting={update.isPending}
                  onSubmit={handleUpdate}
                  onCancel={() =>
                    router.push(`/accounts/${accountId}/contacts`)
                  }
                />
              </CardContent>
            </Card>
          ) : tab === "notes" ? (
            <Card>
              <CardHeader>
                <CardTitle>Notas</CardTitle>
              </CardHeader>
              <CardContent>
                <NotesPanel accountId={accountId} contactId={contactId} />
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Bandejas accesibles</CardTitle>
              </CardHeader>
              <CardContent>
                <ContactableInboxesPanel
                  accountId={accountId}
                  contactId={contactId}
                />
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
