import { Suspense } from "react";

import { CalendarView } from "@/components/publications/calendar-view";
import { getT } from "@/lib/i18n/server";

export default async function PublicationsCalendarPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const t = await getT();
  const { accountId } = await params;
  return (
    <Suspense
      fallback={
        <div className="rounded-md border border-glass bg-surface p-10 text-center text-sm text-fg-muted">
          {t("publications.loadingCalendar")}
        </div>
      }
    >
      <CalendarView accountId={accountId} />
    </Suspense>
  );
}
