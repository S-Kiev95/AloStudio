import type { Messages } from "../es";

import { core } from "./core";
import { instagram } from "./instagram";
import { publications } from "./publications";
import { dates } from "./dates";
import { crm } from "./crm";
import { overview } from "./overview";
import { reports } from "./reports";
import { products } from "./products";
import { contacts } from "./contacts";
import { agenda } from "./agenda";
import { conversations } from "./conversations";
import { actions } from "./actions";

export const fr: Messages = {
  ...core,
  instagram,
  publications,
  dates,
  crm,
  overview,
  reports,
  products,
  contacts,
  agenda,
  conversations,
  actions,
};
