"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { type MacroInput, useCreateMacro } from "@/lib/api/macros";

import { MacroForm } from "./macro-form";

export function MacroNewView({ accountId }: { accountId: string }) {
  const router = useRouter();
  const create = useCreateMacro(accountId);

  async function handleCreate(input: MacroInput) {
    const macro = await create.mutateAsync(input);
    router.push(`/accounts/${accountId}/settings/macros/${macro.id}`);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <Link
        href={`/accounts/${accountId}/settings/macros`}
        className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-fg"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Volver a macros
      </Link>
      <Card>
        <CardHeader>
          <CardTitle>Nuevo macro</CardTitle>
        </CardHeader>
        <CardContent>
          <MacroForm
            submitting={create.isPending}
            onSubmit={handleCreate}
            onCancel={() => router.push(`/accounts/${accountId}/settings/macros`)}
          />
        </CardContent>
      </Card>
    </div>
  );
}
