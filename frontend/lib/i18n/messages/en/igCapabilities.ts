import type { igCapabilities as es } from "../es/igCapabilities";
import type { Strings } from "../types";

export const igCapabilities: Strings<typeof es> = {
  publish: "Publish photos, carousels, reels and stories",
  comments: "Read and reply to comments, with automatic rules",
  insights: "Post metrics",
  facebook: {
    summary: "The complete path. It's the one to choose if you'll handle messages.",
    requirement: "Needs a Facebook Page linked to the Instagram account.",
    dmsNote: "Messages arrive with their text and attachments.",
  },
  dms: "Receive and reply to direct messages",
  deletePosts: "Delete posts from AloStudio",
  instagram: {
    summary: "Simpler to connect, but leaves messages out of service.",
    requirement: "Doesn't need a Facebook Page.",
    dmsNote: "Meta reports that a message arrived but doesn't send the text, so the conversation can't be rebuilt. It's their limitation, not AloStudio's.",
    deleteNote: "Meta doesn't offer deletion in this API. You have to delete from the Instagram app.",
  },
};
