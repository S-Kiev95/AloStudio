import { AgendaView } from "@/components/agenda/agenda-view";

export default async function AgendaPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <AgendaView accountId={accountId} />;
}
