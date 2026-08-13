import { AutoreplyView } from "@/components/instagram/autoreply-view";

export default async function InstagramAutoreplyPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <AutoreplyView accountId={accountId} />;
}
