import type { settingsAgents as es } from "../es/settingsAgents";
import type { Strings } from "../types";

export const settingsAgents: Strings<typeof es> = {
  nameEmailRequired: "Name and email are required.",
  inviteFailed: "Couldn't send the invitation.",
  invite: "Invite agent",
  role: "Role",
  roles: {
    agent: "Agent",
    administrator: "Administrator",
  },
  inviteNote: "They'll get an email with a link to set their password.",
  sendInvite: "Send invitation",
  loadFailed: "Couldn't load the agents.",
  empty: "There are no agents in this account yet.",
  roleFailed: "Couldn't change the role.",
  removeFromAccount: "Remove from account",
  removeConfirm: "Remove {name} from the account?",
  removeNamed: "Remove {name}",
  invited: "We sent an invitation to {email}. The link expires once they set their password.",
};
