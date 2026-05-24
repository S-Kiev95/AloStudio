import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Account overview (Inicio). Rendered inside the dashboard shell (F.2).
 * Real overview widgets land alongside conversations/reports (F.3+).
 */
export default async function AccountHome({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-fg">Inicio</h1>
        <p className="mt-1 text-sm text-fg-muted">
          Cuenta <span className="tabular-nums">{accountId}</span>
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Bienvenido a AloStudio</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-fg-muted">
          Usá el menú lateral para navegar. Conversaciones (F.3) e Instagram
          (F.5/6) llegan en los próximos hitos.
        </CardContent>
      </Card>
    </div>
  );
}
