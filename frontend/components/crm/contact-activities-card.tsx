"use client";

import { ListTodo, Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { type Activity, useActivities } from "@/lib/api/crm";
import { useT } from "@/lib/i18n/provider";

import { ActivityDialog } from "./activity-dialog";
import { ActivityList } from "./activity-list";

/** A contact's pending activities and tasks, on their page. */
export function ContactActivitiesCard({
  accountId,
  contact,
}: {
  accountId: string;
  contact: { id: number; name: string | null };
}) {
  const t = useT();
  const { data, isLoading, isError } = useActivities(accountId, { contact_id: contact.id });
  const [editing, setEditing] = useState<Activity | null>(null);
  const [creating, setCreating] = useState(false);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <ListTodo className="h-4 w-4 text-fg-muted" aria-hidden />
          {t("activities.pageTitle")}
        </CardTitle>
        <Button size="sm" variant="secondary" onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" aria-hidden />
          {t("activities.new")}
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-fg-muted">{t("common.loading")}</p>
        ) : isError ? (
          <p role="alert" className="text-sm text-danger">
            {t("activities.loadFailed")}
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="text-sm text-fg-muted">{t("activities.noneForContact")}</p>
        ) : (
          <ActivityList
            accountId={accountId}
            items={data ?? []}
            onOpen={setEditing}
            showContact={false}
          />
        )}
      </CardContent>
      <ActivityDialog
        accountId={accountId}
        open={creating || editing !== null}
        initial={editing}
        presetContact={contact}
        onClose={() => {
          setCreating(false);
          setEditing(null);
        }}
      />
    </Card>
  );
}
