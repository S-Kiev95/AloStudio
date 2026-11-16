import type { settingsSets as es } from "../es/settingsSets";
import type { Strings } from "../types";

export const settingsSets: Strings<typeof es> = {
  title: "세트 ({count})",
  channelsLabel: "채널: {names}",
  deleteFailed: "세트를 삭제하지 못했습니다.",
  intro: "콘텐츠 세트를 관리해 게시물에서 쉽게 재사용하세요.",
  add: "세트 추가",
  loadFailed: "세트를 불러오지 못했습니다.",
  empty: "아직 저장된 세트가 없습니다.",
  noChannels: "채널 없음",
  edit: "세트 편집",
  delete: "세트 삭제",
};
