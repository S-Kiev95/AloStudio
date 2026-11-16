import { TasksView } from "@/components/crm/tasks-view";

export default async function TasksPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <TasksView accountId={accountId} />;
}
