import type { actions as es } from "../es/actions";
import type { Strings } from "../types";

export const actions: Strings<typeof es> = {
  apply: "適用",
  cancel: "キャンセル",
  selectPlaceholder: "選択…",
  edit: "編集",
  clear: "クリア",
  previous: "前へ",
  next: "次へ",
  addPlaceholder: "追加…",
  back: "戻る",
  send: "送信",
  close: "閉じる",
  retry: "再試行",
  discard: "破棄",
  yes: "はい",
  no: "いいえ",
  page: "{n} ページ",
};
