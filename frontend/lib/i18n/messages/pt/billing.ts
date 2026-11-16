import type { billing as es } from "../es/billing";
import type { Strings } from "../types";

export const billing: Strings<typeof es> = {
  title: "Faturamento",
  subtitle: "Seu plano, o status do pagamento e as faturas.",
  loadFailed: "Não foi possível carregar o faturamento.",
  adminOnly: "Só os administradores veem o faturamento.",
  plan: "Plano",
  noPlan: "Sem plano",
  renewsOn: "Renova em {date}",
  trialEndsOn: "O teste grátis termina em {date}",
  endsOn: "Termina em {date}",
  portal: "Gerenciar pagamento e faturas",
  portalHint: "O cartão, as faturas, trocar de plano ou cancelar ficam no Polar.",
  portalFailed: "Não foi possível abrir o portal de pagamentos.",
  confirming: "Recebemos o pagamento. Pode levar alguns segundos para aparecer aqui.",
  choose: {
    title: "Escolha um plano",
    subtitle: "Para continuar usando o AloStudio, escolha um plano. Suas conversas e dados ficam guardados.",
    notAdmin: "Esta conta não tem um plano ativo. Peça a um administrador que escolha um em Configurações → Faturamento.",
  },
  plans: {
    title: "Planos",
    loadFailed: "Não foi possível carregar os planos.",
    empty: "Ainda não há planos para escolher.",
    perMonth: "{price} por mês",
    perYear: "{price} por ano",
    trial: "{days} dias de teste grátis",
    noTrial: "Sem teste grátis",
    choose: "Escolher {name}",
    checkoutFailed: "Não foi possível abrir a página de pagamento.",
  },
  statuses: {
    none: "Sem plano",
    incomplete: "Pagamento não concluído",
    trialing: "Em teste grátis",
    active: "Ativo",
    past_due: "Pagamento pendente",
    canceled: "Cancelado",
    unpaid: "Não pago",
  },
};
