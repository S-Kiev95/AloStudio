import { PostDetail } from "@/components/instagram/post-detail";

export default async function InstagramPostDetailPage({
  params,
}: {
  params: Promise<{ accountId: string; id: string }>;
}) {
  const { accountId, id } = await params;
  return <PostDetail accountId={accountId} postId={Number(id)} />;
}
