"use client";

import { Plus } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { type Activity, useActivities } from "@/lib/api/crm";
import { useProfile } from "@/lib/api/profile";
import { useT } from "@/lib/i18n/provider";

import { ActivityDialog } from "./activity-dialog";
import { ActivityList } from "./activity-list";

type Show = "pending" | "done";
type Scope = "mine" | "all";

/** CRM → Tareas: what's due, for me or for everyone. */
export function TasksView({ accountId }: { accountId: string }) {
  const t = useT();
  const profile = useProfile();
  const [show, setShow] = useState<Show>("pending");
  const [scope, setScope] = useState<Scope>("mine");
  const [editing, setEditing] = useState<Activity | null>(null);
  const [creating, setCreating] = useState(false);
  const { data, isLoading, isError } = useActivities(accountId, {
    status: show === "done" ? "done" : undefined,
    owner_id: scope === "mine" ? profile.data?.id : undefined,
  });

  return (
    <div className="space-y-4">
      <PageHeader
        title={t("activities.pageTitle")}
        actions={
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            {t("activities.new")}
          </Button>
        }
      />
      <div className="flex flex-wrap items-center gap-3">
        <SegmentedControl
          ariaLabel={t("activities.show")}
          size="sm"
          value={show}
          onValueChange={setShow}
          options={[
            { value: "pending", label: t("activities.pending") },
            { value: "done", label: t("activities.groups.done") },
          ]}
        />
        <SegmentedControl
          ariaLabel={t("opportunities.scope")}
          size="sm"
          value={scope}
          onValueChange={setScope}
          options={[
            { value: "mine", label: t("activities.mine") },
            { value: "all", label: t("opportunities.all") },
          ]}
        />
      </div>

      {isLoading ? (
        <p className="p-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>
      ) : isError ? (
        <p role="alert" className="p-8 text-center text-sm text-danger">
          {t("activities.loadFailed")}
        </p>
      ) : (data?.length ?? 0) === 0 ? (
        <p className="p-8 text-center text-sm text-fg-muted">
          {show === "done" ? t("activities.noneDone") : t("activities.nonePending")}
        </p>
      ) : (
        <ActivityList accountId={accountId} items={data ?? []} onOpen={setEditing} />
      )}

      <ActivityDialog
        accountId={accountId}
        open={creating || editing !== null}
        initial={editing}
        onClose={() => {
          setCreating(false);
          setEditing(null);
        }}
      />
    </div>
  );
}
