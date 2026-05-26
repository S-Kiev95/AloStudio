"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type MacroInput,
  useMacro,
  useUpdateMacro,
} from "@/lib/api/macros";

import { MacroForm } from "./macro-form";

export function MacroDetailView({
  accountId,
  macroId,
}: {
  accountId: string;
  macroId: number;
}) {
  const router = useRouter();
  const { data: macro, isLoading, isError } = useMacro(accountId, macroId);
  const update = useUpdateMacro(accountId);

  async function handleUpdate(input: MacroInput) {
    await update.mutateAsync({ id: macroId, patch: input });
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
      {isLoading ? (
        <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
      ) : isError || !macro ? (
        <p role="alert" className="p-8 text-center text-sm text-danger">
          No se pudo cargar el macro.
        </p>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>{macro.name}</CardTitle>
          </CardHeader>
          <CardContent>
            <MacroForm
              initial={macro}
              submitting={update.isPending}
              onSubmit={handleUpdate}
              onCancel={() =>
                router.push(`/accounts/${accountId}/settings/macros`)
              }
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
