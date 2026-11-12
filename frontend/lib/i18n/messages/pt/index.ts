import type { Messages } from "../es";

import { core } from "./core";
import { placeholder } from "./placeholder";
import { notificationsPage } from "./notificationsPage";
import { oauth } from "./oauth";
import { campaigns } from "./campaigns";
import { agent } from "./agent";
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

export const pt: Messages = {
  ...core,
  placeholder,
  notificationsPage,
  oauth,
  campaigns,
  agent,
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
