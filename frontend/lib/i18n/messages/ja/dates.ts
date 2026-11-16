import type { dates as es } from "../es/dates";
import type { Strings } from "../types";

export const dates: Strings<typeof es> = {
  alreadyPassed: "その時刻はすでに過ぎています: {when}。",
  publishesAt: "{when} に公開 ({rel})。",
};
