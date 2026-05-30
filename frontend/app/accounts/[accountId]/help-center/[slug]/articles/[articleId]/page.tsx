import { ArticleDetailView } from "@/components/help-center/article-detail-view";

export default async function HelpCenterArticleDetailPage({
  params,
}: {
  params: Promise<{ accountId: string; slug: string; articleId: string }>;
}) {
  const { accountId, slug, articleId } = await params;
  return (
    <ArticleDetailView
      accountId={accountId}
      slug={slug}
      articleId={Number(articleId)}
    />
  );
}
