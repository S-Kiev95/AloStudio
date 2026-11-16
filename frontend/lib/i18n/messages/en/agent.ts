import type { agent as es } from "../es/agent";
import type { Strings } from "../types";

export const agent: Strings<typeof es> = {
  suggestions: {
    write: "Put together a post for tomorrow at 10 on all my channels",
    week: "What do I have scheduled this week?",
    lastMonth: "How did my posts do last month?",
  },
  unconfigured: "The agent isn't set up yet. An installation operator has to add the OpenAI key in Settings → Installation → Artificial intelligence.",
  readOnly: "You can look up posts and analytics. Creating or deleting posts is done by an administrator.",
  greeting: "Hi, I'm the AloStudio agent. I can put together and schedule posts on your channels, check your calendar and tell you how your posts did.",
  seeInCalendar: "See in calendar",
  newChat: "New chat",
  chat: "Chat",
  chats: "Chats",
  statusFailed: "Couldn't check the agent's status.",
  chatNotFound: "This chat wasn't found.",
  chatLoadFailed: "Couldn't load the chat.",
  thinking: "Thinking…",
  composer: {
    label: "Message for the agent",
    unavailable: "The agent isn't available",
    placeholder: "Write a message…",
    send: "Send message",
  },
  deleteFailed: "Couldn't delete the chat.",
  closeList: "Close chat list",
  chatsLoadFailed: "Couldn't load the chats.",
  noChats: "You don't have any chats yet.",
  toConfirm: "To confirm",
  deleteChat: "Delete chat",
  pending: {
    seeLess: "See less",
    seeMore: "See more",
    changeHint: "If you want to change something, write it and the agent will make a new proposal.",
    willDelete: "This post will be deleted",
    soon: "Goes out in the next few minutes",
    at: "Goes out {when}",
  },
  deleteConfirm: "Delete the chat “{title}”?",
  deleteChatNamed: "Delete chat {title}",
};
