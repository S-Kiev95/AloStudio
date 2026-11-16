import type { dates as es } from "../es/dates";
import type { Strings } from "../types";

export const dates: Strings<typeof es> = {
  alreadyPassed: "That time has passed: {when}.",
  publishesAt: "Publishes {when} ({rel}).",
};
