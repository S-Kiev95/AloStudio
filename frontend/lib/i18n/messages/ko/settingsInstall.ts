import type { settingsInstall as es } from "../es/settingsInstall";
import type { Strings } from "../types";

export const settingsInstall: Strings<typeof es> = {
  configuredCount: "{done}/{total}개 설정됨",
  netConfigured: "설정됨",
  netNotConfigured: "설정 안 됨",
  operatorOnly: "이 화면은 설치 운영자만 볼 수 있습니다. 배포한 사람에게 접근 권한을 요청하세요.",
  loadFailed: "설정을 불러오지 못했습니다.",
  intro: "계정 하나가 아니라 AloStudio 전체에 적용되는 설정입니다. 자격 증명이 준비될 때까지 비워 둬도 됩니다. 앱은 이것 없이도 작동하며, 각 기능이 무엇이 빠졌는지 알려 줍니다.",
  network: "네트워크",
  clearFailed: "지우지 못했습니다.",
  notConfigured: "설정 안 됨",
  configured: "설정됨",
  savedHere: "여기서 저장됨",
  resetToServer: "서버 값으로 되돌리기",
  fromEnv: "서버 파일(.env)에서 가져옴",
};
