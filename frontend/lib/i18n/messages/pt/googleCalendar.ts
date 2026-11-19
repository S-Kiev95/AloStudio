import type { googleCalendar as es } from "../es/googleCalendar";
import type { Strings } from "../types";

export const googleCalendar: Strings<typeof es> = {
  title: "Google Calendar",
  intro: "Seus compromissos da Agenda e suas tarefas do CRM com data aparecem no seu Google Calendar e se atualizam sozinhos a cada 5 minutos. A edição é feita no AloStudio.",
  connect: "Conectar Google Calendar",
  reconnect: "Conectar de novo",
  disconnect: "Desconectar",
  connectedAs: "Conectado como {email}",
  lastSync: "última sincronização: {when}",
  waiting: "a primeira sincronização chega em alguns minutos",
  revoked: "O Google não dá mais acesso à sua agenda. Conecte de novo.",
  syncFailed: "A última sincronização falhou: {detail}",
  connecting: "Conectando sua agenda…",
  back: "Voltar ao AloStudio",
  problems: {
    unavailable: "Esta instalação não tem o Google configurado.",
    state: "O link expirou ou era de outra pessoa. Tente de novo.",
    exchange: "O Google não aceitou a conexão. Tente de novo.",
    no_refresh_token: "O Google não deu acesso permanente. Tente de novo.",
    cancelled: "A conexão com o Google foi cancelada.",
    failed: "Não foi possível conectar com o Google.",
  },
};
