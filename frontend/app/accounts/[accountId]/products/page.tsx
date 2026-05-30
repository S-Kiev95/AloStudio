import { ProductsView } from "@/components/products/products-view";

export default async function ProductsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <ProductsView accountId={accountId} />;
}
