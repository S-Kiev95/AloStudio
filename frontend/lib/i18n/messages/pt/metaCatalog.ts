import type { metaCatalog as es } from "../es/metaCatalog";
import type { Strings } from "../types";

export const metaCatalog: Strings<typeof es> = {
  title: "Catálogo da Meta",
  intro: "Conecte um catálogo do Commerce Manager e os produtos ativos são enviados para lá, prontos para aparecer no WhatsApp, Instagram e Facebook.",
  howTo: "O ID está no Commerce Manager → seu catálogo → Configurações. O token é de um usuário do sistema (Configurações do negócio → Usuários do sistema) com a permissão catalog_management e acesso ao catálogo.",
  catalogId: "ID do catálogo",
  token: "Token de acesso",
  tokenKeep: "Deixe vazio para manter o atual",
  connect: "Conectar catálogo",
  disconnect: "Desconectar",
  syncNow: "Sincronizar agora",
  disconnectConfirm: "Desconectar o catálogo? Os produtos que já estão na Meta continuam lá.",
  unnamed: "Catálogo sem nome",
  neverSynced: "Ainda não foi sincronizado.",
  lastSync: "Última sincronização: {date} · {sent} enviados, {failed} com problemas",
  stillChecking: "A Meta ainda estava revisando o envio; se algo falhar, você verá na próxima sincronização.",
  autoSync: "Cada alteração num produto é enviada sozinha, poucos segundos depois.",
  synced: "Pronto: {sent} enviados, {removed} removidos, {skipped} incompletos, {failed} recusados pela Meta.",
  state: {
    synced: "Na Meta",
    pending: "Não enviado à Meta",
    missing: "Não é enviado à Meta, falta: {fields}",
    refused: "Recusado pela Meta",
  },
  fields: {
    description: "descrição",
    price: "preço e moeda",
    url: "link",
    image_url: "imagem",
  },
  errors: {
    token: "A Meta não aceitou o token: confira se é válido e não expirou.",
    permission: "O token não tem permissão sobre esse catálogo (catalog_management).",
    catalog_id: "O ID do catálogo tem apenas números.",
    refused: "A Meta recusou o pedido.",
    unreachable: "Não foi possível conectar com a Meta. Tente de novo daqui a pouco.",
    not_connected: "Primeiro conecte um catálogo.",
  },
};
