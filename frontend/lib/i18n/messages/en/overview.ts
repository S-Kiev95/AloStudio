import type { overview as es } from "../es/overview";
import type { Strings } from "../types";

export const overview: Strings<typeof es> = {
  live: {
    open: "Open",
    unattended: "Unattended",
    unassigned: "Unassigned",
    pending: "Pending",
  },
  shortcut: {
    conversations: "Conversations",
    conversationsDesc: "Inbox",
    instagramDesc: "DMs, posts and comments",
    campaigns: "Campaigns",
    campaignsDesc: "Broadcasts and templates",
    reports: "Reports",
    reportsDesc: "Metrics and exports",
  },
  welcome: "Welcome",
  intro: "All your channels, conversations and appointments in one place. Here's how things stand now and over the last 7 days.",
  openInbox: "Open inbox",
  goCalendar: "Go to calendar",
  rightNow: "Right now",
  last7: "Last 7 days",
  metricsFailed: "We couldn't load the period's metrics.",
  conversations: "Conversations",
  shortcuts: "Shortcuts",
};
