import type { settingsPlugs as es } from "../es/settingsPlugs";
import type { Strings } from "../types";

export const settingsPlugs: Strings<typeof es> = {
  messageTooLong: "The message exceeds the maximum of {max} characters ({count}/{max}).",
  channelPlugs: "{name} plugs",
  whenLikes: "When it reaches {n} likes",
  channelRequired: "Choose a channel to set up the plug.",
  actionRequired: "Choose an action from the catalog.",
  thresholdMin: "The threshold must be at least 1 like.",
  messageRequired: "Write the message for this action.",
  saveFailed: "Couldn't save the plug.",
  updateFailed: "Couldn't update the plug.",
  deleteFailed: "Couldn't delete the plug.",
  title: "Plugs",
  intro: "Run automatic actions on your posts when they reach a like threshold.",
  loadFailed: "Couldn't load the plugs.",
  connectThreads: "Connect Threads to use automatic actions",
  noChannels: "No connected channels have actions available in the catalog.",
  goToCalendar: "Go to the calendar to connect channels",
  add: "Add plug",
  noneInChannel: "No automatic actions set up on this channel.",
  edit: "Edit plug",
  delete: "Delete plug",
  lastRuns: "Latest runs",
  runOk: "OK",
  runFailed: "Failed",
  channel: "Channel",
  thresholdLabel: "When it reaches N likes",
  message: "Message",
  messagePlaceholder: "Write the automatic reply…",
  save: "Save plug",
  kinds: {
    reply_after_likes: {
      label: "Reply when it reaches N likes",
      description: "When a post reaches that many likes, it publishes your message as a reply to that same post (for example, a link or an offer).",
    },
    repost_after_likes: {
      label: "Repost when it reaches N likes",
      description: "When a post reaches that many likes, it reposts it on your profile so your followers see it again.",
    },
  },
};
