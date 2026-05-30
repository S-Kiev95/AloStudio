import { ArticleNewView } from "@/components/help-center/article-new-view";

export default async function HelpCenterArticleNewPage({
  params,
}: {
  params: Promise<{ accountId: string; slug: string }>;
}) {
  const { accountId, slug } = await params;
  return <ArticleNewView accountId={accountId} slug={slug} />;
}
