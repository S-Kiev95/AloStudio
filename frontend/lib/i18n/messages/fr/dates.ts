import type { dates as es } from "../es/dates";
import type { Strings } from "../types";

export const dates: Strings<typeof es> = {
  alreadyPassed: "Cette heure est déjà passée : {when}.",
  publishesAt: "Publication {when} ({rel}).",
};
