import type { dates as es } from "../es/dates";
import type { Strings } from "../types";

export const dates: Strings<typeof es> = {
  alreadyPassed: "이미 지난 시간입니다: {when}.",
  publishesAt: "{when} 게시 ({rel}).",
};
