/**
 * Spanish, the source language. Every text starts here, in the file of its
 * screen; the other languages must have exactly the same keys, or the type
 * check fails.
 *
 * `{name}` marks a value filled in at runtime. Rioplatense voice (vos), as
 * in the rest of the app.
 */
import type { Strings } from "../types";

import { core } from "./core";
import { actions } from "./actions";
import { conversations } from "./conversations";

export const es = {
  ...core,
  actions,
  conversations,
};

export type Messages = Strings<typeof es>;
