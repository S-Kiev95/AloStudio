import type { apiErrors as es } from "../es/apiErrors";
import type { Strings } from "../types";

export const apiErrors: Strings<typeof es> = {
  notAuthorized: "この操作を行う権限がありません。",
  tooManyAttempts: "失敗した試行が多すぎます。数分待ってから再度お試しください。",
  mediaUnsupported: "対応していない形式です。画像か動画をアップロードしてください。",
  imageTooBig: "画像が上限の 30 MB を超えています。",
  videoTooBig: "動画が上限の 200 MB を超えています。",
  uploadFailed: "ファイルをアップロードできませんでした ({status})。",
  pushDenied: "通知の許可が拒否されました。",
  agentFailed: "エージェントとの通信中にエラーが発生しました。",
  requestFailed: "リクエストの処理中にエラーが発生しました。",
  requestFailedStatus: "リクエストに失敗しました ({status})。",
};
