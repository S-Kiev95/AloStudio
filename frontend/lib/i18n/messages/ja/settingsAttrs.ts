import type { settingsAttrs as es } from "../es/settingsAttrs";
import type { Strings } from "../types";

export const settingsAttrs: Strings<typeof es> = {
  displayNameRequired: "表示名は必須です。",
  saveFailed: "属性を保存できませんでした。",
  displayName: "表示名",
  appliesTo: "適用先",
  regex: "パターン (正規表現)",
  regexHint: "ユーザー向けのヒント",
  regexHintPlaceholder: "例: ABC-1234",
  values: "値",
  noValues: "リストにはまだ値がありません。",
  newValue: "新しい値",
  create: "属性を作成",
  new: "新しい属性",
  edit: "属性を編集",
  model: "モデル",
  loadFailed: "属性を読み込めませんでした。",
  empty: "定義済みの属性はまだありません。",
  deleteConfirm: "「{name}」を削除しますか？",
  keyReadonly: "キー: {key} (編集不可)",
};
