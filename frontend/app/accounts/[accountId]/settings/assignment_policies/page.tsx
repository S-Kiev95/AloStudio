import { AssignmentPoliciesView } from "@/components/settings/assignment-policies/assignment-policies-view";

export default async function SettingsAssignmentPoliciesPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <AssignmentPoliciesView accountId={accountId} />;
}
