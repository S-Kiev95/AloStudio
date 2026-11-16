"use client";

import { Card, CardContent } from "@/components/ui/card";
import { useT } from "@/lib/i18n/provider";

import { PageHeader } from "./page-header";

/** Temporary placeholder for nav sections not yet built. */
export function SectionPlaceholder({
  title,
  milestone,
}: {
  title: string;
  milestone: string;
}) {
  const t = useT();
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader title={title} />
      <Card>
        <CardContent className="py-10 text-center text-sm text-fg-muted">
          {t("placeholder.comingSoon", { milestone })}
        </CardContent>
      </Card>
    </div>
  );
}
