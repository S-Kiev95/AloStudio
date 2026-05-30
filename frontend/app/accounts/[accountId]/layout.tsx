import { redirect } from "next/navigation";

import { DashboardShell } from "@/components/shell/dashboard-shell";
import { getProfile } from "@/lib/auth/profile";

/**
 * Authenticated dashboard layout. Loads the profile server-side, asserts
 * the user belongs to the routed account, and wraps every account page in
 * the shell (sidebar + topbar + account switcher).
 */
export default async function AccountLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  const profile = await getProfile();
  if (!profile) redirect("/login");

  const isMember = profile.accounts.some(
    (a) => String(a.id) === accountId,
  );
  if (!isMember) redirect("/accounts");

  return (
    <DashboardShell accountId={accountId} profile={profile}>
      {children}
    </DashboardShell>
  );
}
