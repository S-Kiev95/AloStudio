import type { settingsTeams as es } from "../es/settingsTeams";
import type { Strings } from "../types";

export const settingsTeams: Strings<typeof es> = {
  back: "Back to teams",
  loadFailed: "Couldn't load the team.",
  saveFailed: "Couldn't save the team.",
  autoAssign: "Allow automatic assignment",
  create: "Create team",
  addMemberFailed: "Couldn't add the member.",
  removeMemberFailed: "Couldn't remove the member.",
  members: "Members",
  addMember: "Add member",
  availableAgents: "Available agents",
  allMembers: "All agents are already members of this team.",
  loadingMembers: "Loading members…",
  membersLoadFailed: "Couldn't load the members.",
  noMembers: "The team has no members.",
  removeFromTeam: "Remove from team",
  new: "New team",
  listLoadFailed: "Couldn't load the teams.",
  empty: "No teams yet.",
  youAreMember: "You're a member",
  noAutoAssign: "No automatic assignment",
  deleteConfirm: "Delete the team \"{name}\"?",
  removeConfirm: "Remove {name} from the team?",
};
