import type { billing as es } from "../es/billing";
import type { Strings } from "../types";

export const billing: Strings<typeof es> = {
  title: "Billing",
  subtitle: "Your plan, payment status and invoices.",
  loadFailed: "Couldn't load billing.",
  adminOnly: "Only administrators can see billing.",
  plan: "Plan",
  noPlan: "No plan",
  renewsOn: "Renews on {date}",
  trialEndsOn: "Free trial ends on {date}",
  endsOn: "Ends on {date}",
  portal: "Manage payment and invoices",
  portalHint: "Your card, invoices, changing plan or cancelling are handled in Polar.",
  portalFailed: "Couldn't open the payment portal.",
  confirming: "We got the payment. It can take a few seconds to show up here.",
  choose: {
    title: "Choose a plan",
    subtitle: "To keep using AloStudio, choose a plan. Your conversations and data are kept.",
    notAdmin: "This account has no active plan. Ask an administrator to choose one in Settings → Billing.",
  },
  plans: {
    title: "Plans",
    loadFailed: "Couldn't load the plans.",
    empty: "There are no plans to choose from yet.",
    perMonth: "{price} per month",
    perYear: "{price} per year",
    trial: "{days}-day free trial",
    noTrial: "No free trial",
    choose: "Choose {name}",
    checkoutFailed: "Couldn't open the payment page.",
  },
  statuses: {
    none: "No plan",
    incomplete: "Payment not finished",
    trialing: "Free trial",
    active: "Active",
    past_due: "Payment due",
    canceled: "Cancelled",
    unpaid: "Unpaid",
  },
};
