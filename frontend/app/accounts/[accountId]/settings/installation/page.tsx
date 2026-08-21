import { InstallationView } from "@/components/settings/installation/installation-view";

export default function SettingsInstallationPage() {
  // Installation settings are not account-scoped — the same values serve
  // every account on this deployment.
  return <InstallationView />;
}
