import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { LogoutButton } from "./logout-button";

/**
 * Placeholder dashboard (F.1). Proves the auth round-trip: this route is
 * behind the middleware guard, so reaching it means the session cookie is
 * set. The real app shell (sidebar, nav) lands in F.2.
 */
export default async function AccountHome({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return (
    <main className="mx-auto max-w-3xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-fg">AloStudio</h1>
        <LogoutButton />
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Sesión iniciada ✓</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-fg-muted">
          Cuenta activa: <span className="tabular-nums text-fg">{accountId}</span>.
          El shell del dashboard (sidebar, conversaciones) llega en F.2/F.3.
        </CardContent>
      </Card>
    </main>
  );
}
