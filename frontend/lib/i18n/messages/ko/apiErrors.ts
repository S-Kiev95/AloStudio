import type { apiErrors as es } from "../es/apiErrors";
import type { Strings } from "../types";

export const apiErrors: Strings<typeof es> = {
  notAuthorized: "이 작업을 할 권한이 없습니다.",
  tooManyAttempts: "실패한 시도가 너무 많습니다. 몇 분 뒤 다시 시도하세요.",
  mediaUnsupported: "지원하지 않는 형식입니다. 이미지나 동영상을 올리세요.",
  imageTooBig: "이미지가 30MB 제한을 넘었습니다.",
  videoTooBig: "동영상이 200MB 제한을 넘었습니다.",
  uploadFailed: "파일을 업로드하지 못했습니다 ({status}).",
  pushDenied: "알림 권한이 거부되었습니다.",
  agentFailed: "에이전트와 통신하는 중 오류가 발생했습니다.",
  requestFailed: "요청을 처리하는 중 오류가 발생했습니다.",
  requestFailedStatus: "요청이 실패했습니다 ({status}).",
};
