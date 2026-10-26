import { Card, CardContent } from "@/components/ui/card";

import { PageHeader } from "./page-header";

/** Temporary placeholder for nav sections not yet built. */
export function SectionPlaceholder({
  title,
  milestone,
}: {
  title: string;
  milestone: string;
}) {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader title={title} />
      <Card>
        <CardContent className="py-10 text-center text-sm text-fg-muted">
          Próximamente — llega en el hito {milestone}.
        </CardContent>
      </Card>
    </div>
  );
}
