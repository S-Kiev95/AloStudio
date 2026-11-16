import type { dates as es } from "../es/dates";
import type { Strings } from "../types";

export const dates: Strings<typeof es> = {
  alreadyPassed: "Diese Zeit ist schon vorbei: {when}.",
  publishesAt: "Wird veröffentlicht: {when} ({rel}).",
};
