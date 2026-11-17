import { LifecycleSettingsView } from "@/components/lifecycle/lifecycle-settings-view";

export default async function SettingsLifecyclePage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <LifecycleSettingsView accountId={accountId} />;
}
