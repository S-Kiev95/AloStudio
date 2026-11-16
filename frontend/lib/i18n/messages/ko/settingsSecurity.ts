import type { settingsSecurity as es } from "../es/settingsSecurity";
import type { Strings } from "../types";

export const settingsSecurity: Strings<typeof es> = {
  fillAll: "세 칸을 모두 입력하세요.",
  min8: "새 비밀번호는 8자 이상이어야 합니다.",
  mismatch: "확인 비밀번호가 새 비밀번호와 일치하지 않습니다.",
  changeFailed: "비밀번호를 변경하지 못했습니다.",
  changePassword: "비밀번호 변경",
  updated: "비밀번호가 변경되었습니다.",
  current: "현재 비밀번호",
  new: "새 비밀번호",
  min8Short: "최소 8자.",
  repeat: "새 비밀번호 확인",
  update: "비밀번호 업데이트",
};
