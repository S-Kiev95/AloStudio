"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { type ContactInput, useCreateContact } from "@/lib/api/contacts";

import { ContactForm } from "./contact-form";

export function ContactNewView({ accountId }: { accountId: string }) {
  const router = useRouter();
  const create = useCreateContact(accountId);

  async function handleCreate(input: ContactInput) {
    const contact = await create.mutateAsync(input);
    router.push(`/accounts/${accountId}/contacts/${contact.id}`);
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
      <Card>
        <CardHeader>
          <CardTitle>Nuevo contacto</CardTitle>
        </CardHeader>
        <CardContent>
          <ContactForm
            accountId={accountId}
            submitting={create.isPending}
            onSubmit={handleCreate}
            onCancel={() => router.push(`/accounts/${accountId}/contacts`)}
          />
        </CardContent>
      </Card>
    </div>
  );
}
