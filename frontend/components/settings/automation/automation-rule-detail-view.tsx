"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type AutomationRuleInput,
  useAutomationRule,
  useUpdateAutomationRule,
} from "@/lib/api/automation-rules";

import { AutomationRuleForm } from "./automation-rule-form";

export function AutomationRuleDetailView({
  accountId,
  ruleId,
}: {
  accountId: string;
  ruleId: number;
}) {
  const router = useRouter();
  const { data: rule, isLoading, isError } = useAutomationRule(accountId, ruleId);
  const update = useUpdateAutomationRule(accountId);

  async function handleUpdate(input: AutomationRuleInput) {
    await update.mutateAsync({ id: ruleId, patch: input });
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <Link
        href={`/accounts/${accountId}/settings/automation`}
        className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-fg"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Volver a reglas
      </Link>
      {isLoading ? (
        <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
      ) : isError || !rule ? (
        <p role="alert" className="p-8 text-center text-sm text-danger">
          No se pudo cargar la regla.
        </p>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>{rule.name}</CardTitle>
          </CardHeader>
          <CardContent>
            <AutomationRuleForm
              initial={rule}
              submitting={update.isPending}
              onSubmit={handleUpdate}
              onCancel={() =>
                router.push(`/accounts/${accountId}/settings/automation`)
              }
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
