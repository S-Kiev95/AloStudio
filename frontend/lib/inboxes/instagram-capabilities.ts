/**
 * What each way of connecting an Instagram account actually gets you.
 *
 * This exists because none of it was visible before connecting. The
 * differences are not cosmetic — one flow delivers DMs with their text
 * and the other delivers empty events, one can delete a post and the
 * other cannot — and every one of these was learned by connecting an
 * account and watching something fail silently days later.
 *
 * Every entry below was verified live against Meta on 2026-08-22, on a
 * real account, not read off a table.
 */

export type CapabilityLevel = "yes" | "partial" | "no";

export type Capability = {
  label: string;
  level: CapabilityLevel;
  /** Shown when the answer is not a plain yes. */
  note?: string;
};

export type ConnectFlow = {
  id: "facebook" | "instagram";
  title: string;
  /** One line on who this flow is for. */
  summary: string;
  requirement: string;
  capabilities: Capability[];
};

const PUBLISH: Capability = {
  label: "Publicar fotos, carruseles, reels e historias",
  level: "yes",
};
const COMMENTS: Capability = {
  label: "Leer y responder comentarios, con reglas automáticas",
  level: "yes",
};
const INSIGHTS: Capability = { label: "Métricas de las publicaciones", level: "yes" };

export const CONNECT_FLOWS: ConnectFlow[] = [
  {
    id: "facebook",
    title: "Facebook Login",
    summary:
      "El camino completo. Es el que conviene si vas a atender mensajes.",
    requirement:
      "Necesita una Página de Facebook vinculada a la cuenta de Instagram.",
    capabilities: [
      PUBLISH,
      COMMENTS,
      INSIGHTS,
      {
        label: "Recibir y responder mensajes directos",
        level: "yes",
        note: "Los mensajes llegan con su texto y sus adjuntos.",
      },
      {
        label: "Borrar publicaciones desde AloStudio",
        level: "yes",
      },
    ],
  },
  {
    id: "instagram",
    title: "Instagram Login",
    summary:
      "Más simple de conectar, pero deja los mensajes fuera de servicio.",
    requirement: "No necesita Página de Facebook.",
    capabilities: [
      PUBLISH,
      COMMENTS,
      INSIGHTS,
      {
        label: "Recibir y responder mensajes directos",
        level: "partial",
        note: "Meta avisa que llegó un mensaje pero no manda el texto, así que la conversación no se puede reconstruir. Es una limitación suya, no de AloStudio.",
      },
      {
        label: "Borrar publicaciones desde AloStudio",
        level: "no",
        note: "Meta no ofrece el borrado en esta API. Hay que borrar desde la app de Instagram.",
      },
    ],
  },
];

export function flowById(id: ConnectFlow["id"]): ConnectFlow {
  const found = CONNECT_FLOWS.find((f) => f.id === id);
  if (!found) throw new Error(`flujo desconocido: ${id}`);
  return found;
}
