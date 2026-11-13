import type { metaCatalog as es } from "../es/metaCatalog";
import type { Strings } from "../types";

export const metaCatalog: Strings<typeof es> = {
  title: "Meta catalog",
  intro: "Connect a Commerce Manager catalog and active products are sent there, ready to show on WhatsApp, Instagram and Facebook.",
  howTo: "The ID is in Commerce Manager → your catalog → Settings. The token belongs to a system user (Business Settings → System users) with the catalog_management permission and access to the catalog.",
  catalogId: "Catalog ID",
  token: "Access token",
  tokenKeep: "Leave empty to keep the current one",
  connect: "Connect catalog",
  disconnect: "Disconnect",
  syncNow: "Sync now",
  disconnectConfirm: "Disconnect the catalog? Products already in Meta stay there.",
  unnamed: "Unnamed catalog",
  neverSynced: "Not synced yet.",
  lastSync: "Last sync: {date} · {sent} sent, {failed} with problems",
  stillChecking: "Meta was still checking the batch; anything that fails shows on the next sync.",
  autoSync: "Every product change is sent on its own, a few seconds later.",
  synced: "Done: {sent} sent, {removed} removed, {skipped} incomplete, {failed} refused by Meta.",
  state: {
    synced: "In Meta",
    pending: "Not sent to Meta",
    missing: "Not sent to Meta, missing: {fields}",
    refused: "Refused by Meta",
  },
  fields: {
    description: "description",
    price: "price and currency",
    url: "link",
    image_url: "image",
  },
  errors: {
    token: "Meta didn't accept the token: check it's valid and hasn't expired.",
    permission: "The token has no permission on that catalog (catalog_management).",
    catalog_id: "The catalog ID is numbers only.",
    refused: "Meta refused the request.",
    unreachable: "Couldn't reach Meta. Try again in a while.",
    not_connected: "Connect a catalog first.",
  },
};
