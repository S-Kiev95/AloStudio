import type { actions as es } from "../es/actions";
import type { Strings } from "../types";

export const actions: Strings<typeof es> = {
  apply: "Aplicar",
  cancel: "Cancelar",
  selectPlaceholder: "Selecionar…",
  edit: "Editar",
  clear: "Limpar",
  previous: "Anterior",
  next: "Próxima",
  addPlaceholder: "Adicionar…",
  back: "Voltar",
  send: "Enviar",
  close: "Fechar",
  retry: "Tentar de novo",
  discard: "Descartar",
  yes: "Sim",
  no: "Não",
  page: "Página {n}",
};
