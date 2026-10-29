import { Suspense } from "react";

import { CalendarView } from "@/components/publications/calendar-view";

export default async function PublicationsCalendarPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return (
    <Suspense
      fallback={
        <div className="rounded-md border border-glass bg-surface p-10 text-center text-sm text-fg-muted">
          Cargando calendario…
        </div>
      }
    >
      <CalendarView accountId={accountId} />
    </Suspense>
  );
}
