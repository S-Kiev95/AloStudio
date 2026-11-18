"use client";

import { Select, type SelectProps } from "@/components/ui/select";
import { useAgents } from "@/lib/api/account";
import { TARGET_AI } from "@/lib/api/handoff";
import { useT } from "@/lib/i18n/provider";

/** Pick who takes a handoff: nobody, a person of the account, or
 *  AloStudio's AI when the account has it. Values per `targetValue`. */
export function HandoffTargetSelect({
  accountId,
  aiAvailable,
  emptyLabel,
  value,
  ...props
}: Omit<SelectProps, "children"> & {
  accountId: string;
  aiAvailable: boolean;
  emptyLabel: string;
  value: string;
}) {
  const t = useT();
  const agents = useAgents(accountId);
  return (
    <Select {...props} value={value} disabled={agents.isLoading || props.disabled}>
      <option value="">{emptyLabel}</option>
      {aiAvailable || value === TARGET_AI ? (
        <option value={TARGET_AI}>{t("handoff.ai")}</option>
      ) : null}
      {(agents.data ?? []).map((a) => (
        <option key={a.id} value={String(a.id)}>
          {a.available_name || a.name}
        </option>
      ))}
    </Select>
  );
}
