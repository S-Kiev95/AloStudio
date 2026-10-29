import { ContactsView } from "@/components/contacts/contacts-view";

export default async function ContactsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <ContactsView accountId={accountId} />;
}
