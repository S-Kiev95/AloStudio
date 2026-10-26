"use client";

import { ArrowLeft, GitMerge, Mail, Phone, User as UserIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ContactAppointmentsCard } from "@/components/agenda/contact-appointments-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  type ContactInput,
  useContact,
  useUpdateContact,
} from "@/lib/api/contacts";

import { ContactForm } from "./contact-form";
import { ContactableInboxesPanel } from "./contactable-inboxes-panel";
import { MergeDialog } from "./merge-dialog";
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
  const [mergeOpen, setMergeOpen] = useState(false);

  async function handleUpdate(input: ContactInput) {
    await update.mutateAsync({ id: contactId, patch: input });
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
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
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-focused text-lit">
              <UserIcon className="h-5 w-5" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-xl font-medium text-fg">
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
                  <span className="flex items-center gap-1 font-numeric tabular-nums">
                    <Phone className="h-3 w-3" aria-hidden />
                    {contact.phone_number}
                  </span>
                ) : null}
                {contact.identifier ? `id ${contact.identifier}` : null}
              </p>
            </div>
            {contact.blocked ? (
              <span className="rounded-pill bg-danger/10 px-2 py-0.5 text-xs font-medium text-danger">
                Bloqueado
              </span>
            ) : null}
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setMergeOpen(true)}
            >
              <GitMerge className="h-4 w-4" aria-hidden />
              Combinar
            </Button>
          </div>

          <MergeDialog
            accountId={accountId}
            base={contact}
            open={mergeOpen}
            onClose={() => setMergeOpen(false)}
            onMerged={() => {
              // Post-merge the base contact stays put — just bounce back
              // to the list since the form state is stale by then.
              router.push(`/accounts/${accountId}/contacts`);
            }}
          />

          <ContactAppointmentsCard accountId={accountId} contact={contact} />

          <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
            <TabsList>
              {TABS.map((t) => (
                <TabsTrigger key={t.value} value={t.value}>
                  {t.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

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
