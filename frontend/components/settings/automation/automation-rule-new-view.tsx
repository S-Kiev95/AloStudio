"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type AutomationRuleInput,
  useCreateAutomationRule,
} from "@/lib/api/automation-rules";

import { AutomationRuleForm } from "./automation-rule-form";

export function AutomationRuleNewView({ accountId }: { accountId: string }) {
  const router = useRouter();
  const create = useCreateAutomationRule(accountId);

  async function handleCreate(input: AutomationRuleInput) {
    const rule = await create.mutateAsync(input);
    router.push(`/accounts/${accountId}/settings/automation/${rule.id}`);
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
      <Card>
        <CardHeader>
          <CardTitle>Nueva regla</CardTitle>
        </CardHeader>
        <CardContent>
          <AutomationRuleForm
            submitting={create.isPending}
            onSubmit={handleCreate}
            onCancel={() =>
              router.push(`/accounts/${accountId}/settings/automation`)
            }
          />
        </CardContent>
      </Card>
    </div>
  );
}
