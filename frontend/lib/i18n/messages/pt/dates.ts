import type { dates as es } from "../es/dates";
import type { Strings } from "../types";

export const dates: Strings<typeof es> = {
  alreadyPassed: "Esse horário já passou: {when}.",
  publishesAt: "Será publicado {when} ({rel}).",
};
