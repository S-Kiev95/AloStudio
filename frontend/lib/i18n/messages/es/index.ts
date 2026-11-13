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
import { activities } from "./activities";
import { opportunities } from "./opportunities";
import { igCapabilities } from "./igCapabilities";
import { channelCatalog } from "./channelCatalog";
import { apiErrors } from "./apiErrors";
import { settingsSignatures } from "./settingsSignatures";
import { settingsSets } from "./settingsSets";
import { settingsPlugs } from "./settingsPlugs";
import { settingsAutoposts } from "./settingsAutoposts";
import { settingsOauth } from "./settingsOauth";
import { settingsIntegrations } from "./settingsIntegrations";
import { settingsInstall } from "./settingsInstall";
import { settingsEmailTpl } from "./settingsEmailTpl";
import { settingsAutomation } from "./settingsAutomation";
import { settingsInboxes } from "./settingsInboxes";
import { settingsWebhooks } from "./settingsWebhooks";
import { settingsNotif } from "./settingsNotif";
import { settingsMcp } from "./settingsMcp";
import { settingsAssign } from "./settingsAssign";
import { settingsBots } from "./settingsBots";
import { settingsHours } from "./settingsHours";
import { settingsTeams } from "./settingsTeams";
import { settingsSecurity } from "./settingsSecurity";
import { settingsMacros } from "./settingsMacros";
import { settingsLabels } from "./settingsLabels";
import { settingsAttrs } from "./settingsAttrs";
import { settingsCsat } from "./settingsCsat";
import { settingsCanned } from "./settingsCanned";
import { settingsAgents } from "./settingsAgents";
import { helpCenter } from "./helpCenter";
import { hc } from "./hc";
import { authCallback } from "./authCallback";
import { errors } from "./errors";
import { placeholder } from "./placeholder";
import { notificationsPage } from "./notificationsPage";
import { oauth } from "./oauth";
import { campaigns } from "./campaigns";
import { agent } from "./agent";
import { instagram } from "./instagram";
import { publications } from "./publications";
import { reports } from "./reports";
import { products } from "./products";
import { overview } from "./overview";
import { crm } from "./crm";
import { contacts } from "./contacts";
import { agenda } from "./agenda";
import { dates } from "./dates";
import { actions } from "./actions";
import { conversations } from "./conversations";

export const es = {
  ...core,
  activities,
  opportunities,
  igCapabilities,
  channelCatalog,
  apiErrors,
  settingsSignatures,
  settingsSets,
  settingsPlugs,
  settingsAutoposts,
  settingsOauth,
  settingsIntegrations,
  settingsInstall,
  settingsEmailTpl,
  settingsAutomation,
  settingsInboxes,
  settingsWebhooks,
  settingsNotif,
  settingsMcp,
  settingsAssign,
  settingsBots,
  settingsHours,
  settingsTeams,
  settingsSecurity,
  settingsMacros,
  settingsLabels,
  settingsAttrs,
  settingsCsat,
  settingsCanned,
  settingsAgents,
  helpCenter,
  hc,
  authCallback,
  errors,
  placeholder,
  notificationsPage,
  oauth,
  campaigns,
  agent,
  instagram,
  publications,
  reports,
  products,
  overview,
  crm,
  contacts,
  agenda,
  dates,
  actions,
  conversations,
};

export type Messages = Strings<typeof es>;
