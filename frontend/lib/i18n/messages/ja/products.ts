import type { products as es } from "../es/products";
import type { Strings } from "../types";

export const products: Strings<typeof es> = {
  form: {
    nameRequired: "名前を入力してください。",
    priceInvalid: "価格が正しくありません。",
    saveFailed: "商品を保存できませんでした。",
    description: "説明",
    price: "価格",
    currency: "通貨",
    productUrl: "商品 URL",
    imageUrl: "画像 URL",
    active: "有効 (カタログに表示)",
    create: "商品を作成",
  },
  filters: {
    all: "すべて",
    active: "有効",
    inactive: "無効",
  },
  title: "商品",
  new: "新しい商品",
  edit: "商品を編集",
  filterLabel: "商品を絞り込む",
  loadFailed: "商品を読み込めませんでした。",
  empty: "商品はまだありません。",
  active: "有効",
  inactive: "無効",
  deleteConfirm: "「{name}」を削除しますか？",
  description: "説明",
};
