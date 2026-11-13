import type { authCallback as es } from "../es/authCallback";
import type { Strings } from "../types";

export const authCallback: Strings<typeof es> = {
  googleCancelled: "Google 로그인이 취소되었습니다.",
  googleFailed: "Google로 로그인하지 못했습니다.",
  googleTitle: "Google로 로그인",
  signingIn: "로그인하는 중…",
  ssoNoToken: "접속 링크에 토큰이 없습니다.",
  ssoFailed: "로그인하지 못했습니다. 링크가 만료되었을 수 있습니다.",
  ssoTitle: "Postiz에서 접속",
};
