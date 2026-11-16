import type { billing as es } from "../es/billing";
import type { Strings } from "../types";

export const billing: Strings<typeof es> = {
  title: "Abrechnung",
  subtitle: "Dein Tarif, der Zahlungsstatus und die Rechnungen.",
  loadFailed: "Die Abrechnung konnte nicht geladen werden.",
  adminOnly: "Nur Administratoren sehen die Abrechnung.",
  plan: "Tarif",
  noPlan: "Kein Tarif",
  renewsOn: "Verlängert sich am {date}",
  trialEndsOn: "Die kostenlose Testphase endet am {date}",
  endsOn: "Endet am {date}",
  portal: "Zahlung und Rechnungen verwalten",
  portalHint: "Karte, Rechnungen, Tarifwechsel oder Kündigung laufen über Polar.",
  portalFailed: "Das Zahlungsportal konnte nicht geöffnet werden.",
  confirming: "Wir haben die Zahlung erhalten. Es kann ein paar Sekunden dauern, bis sie hier erscheint.",
  choose: {
    title: "Wähle einen Tarif",
    subtitle: "Um AloStudio weiter zu nutzen, wähle einen Tarif. Deine Unterhaltungen und Daten bleiben erhalten.",
    notAdmin: "Dieses Konto hat keinen aktiven Tarif. Bitte einen Administrator, unter Einstellungen → Abrechnung einen zu wählen.",
  },
  plans: {
    title: "Tarife",
    loadFailed: "Die Tarife konnten nicht geladen werden.",
    empty: "Es gibt noch keine Tarife zur Auswahl.",
    perMonth: "{price} pro Monat",
    perYear: "{price} pro Jahr",
    trial: "{days} Tage kostenlos testen",
    noTrial: "Keine kostenlose Testphase",
    choose: "{name} wählen",
    checkoutFailed: "Die Zahlungsseite konnte nicht geöffnet werden.",
  },
  statuses: {
    none: "Kein Tarif",
    incomplete: "Zahlung nicht abgeschlossen",
    trialing: "Kostenlose Testphase",
    active: "Aktiv",
    past_due: "Zahlung fällig",
    canceled: "Gekündigt",
    unpaid: "Unbezahlt",
  },
};
