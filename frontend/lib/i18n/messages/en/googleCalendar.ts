import type { googleCalendar as es } from "../es/googleCalendar";
import type { Strings } from "../types";

export const googleCalendar: Strings<typeof es> = {
  title: "Google Calendar",
  intro: "Your Agenda appointments and dated CRM tasks show up in your Google Calendar and update on their own every 5 minutes. You edit them in AloStudio.",
  connect: "Connect Google Calendar",
  reconnect: "Connect again",
  disconnect: "Disconnect",
  connectedAs: "Connected as {email}",
  lastSync: "last sync: {when}",
  waiting: "the first sync arrives in a few minutes",
  revoked: "Google no longer gives access to your calendar. Connect it again.",
  syncFailed: "The last sync failed: {detail}",
  connecting: "Connecting your calendar…",
  back: "Back to AloStudio",
  problems: {
    unavailable: "Google isn't set up on this installation.",
    state: "The link expired or belonged to someone else. Try again.",
    exchange: "Google didn't accept the connection. Try again.",
    no_refresh_token: "Google didn't give lasting access. Try again.",
    cancelled: "The connection with Google was cancelled.",
    failed: "Couldn't connect with Google.",
  },
};
