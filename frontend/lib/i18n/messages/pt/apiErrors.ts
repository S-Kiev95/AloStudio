import type { apiErrors as es } from "../es/apiErrors";
import type { Strings } from "../types";

export const apiErrors: Strings<typeof es> = {
  notAuthorized: "Você não tem permissão para fazer isso.",
  tooManyAttempts: "Muitas tentativas falhas. Espere alguns minutos e tente de novo.",
  mediaUnsupported: "Formato não suportado. Envie uma imagem ou um vídeo.",
  imageTooBig: "A imagem passa do limite de 30 MB.",
  videoTooBig: "O vídeo passa do limite de 200 MB.",
  uploadFailed: "Não foi possível enviar o arquivo ({status}).",
  pushDenied: "Permissão de notificações negada.",
  agentFailed: "Ocorreu um erro ao falar com o agente.",
  requestFailed: "Ocorreu um erro ao processar a solicitação.",
  requestFailedStatus: "A solicitação falhou ({status}).",
};
