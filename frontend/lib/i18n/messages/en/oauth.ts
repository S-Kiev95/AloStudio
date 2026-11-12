import type { oauth as es } from "../es/oauth";
import type { Strings } from "../types";

export const oauth: Strings<typeof es> = {
  scope: {
    readPosts: "See your posts, channels and analytics",
    readConversations: "See conversations and contacts",
    writePosts: "Schedule and delete posts",
    writeConversations: "Reply to and organize conversations",
  },
  cannotAuthorize: "Can't authorize",
  invalidRequest: "The app's request isn't valid.",
  backToApp: "Back to AloStudio",
  createdBy: "Created by",
  willBeAbleTo: "It will be able to:",
  whichAccount: "Which account?",
  roleNotAllowed: "Your role in this account doesn't allow granting this access",
  sendFailed: "Couldn't send your answer.",
  authorize: "Authorize",
  wantsAccess: "{app} wants to access your AloStudio account",
  redirectNote: "It will take you to {host}. You can revoke access anytime in Settings → OAuth apps.",
};
