import { SettingsSidebar } from "@/components/settings/settings-sidebar";

export default async function SettingsLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return (
    <div className="flex flex-col gap-0 md:flex-row md:gap-6">
      <SettingsSidebar accountId={accountId} />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
