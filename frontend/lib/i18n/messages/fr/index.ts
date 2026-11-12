import type { Messages } from "../es";

import { core } from "./core";
import { conversations } from "./conversations";
import { actions } from "./actions";

export const fr: Messages = {
  ...core,
  conversations,
  actions,
};
