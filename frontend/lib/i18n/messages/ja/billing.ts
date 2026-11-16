import type { billing as es } from "../es/billing";
import type { Strings } from "../types";

export const billing: Strings<typeof es> = {
  title: "請求",
  subtitle: "プラン、支払い状況、請求書。",
  loadFailed: "請求情報を読み込めませんでした。",
  adminOnly: "請求情報は管理者のみ表示できます。",
  plan: "プラン",
  noPlan: "プランなし",
  renewsOn: "{date}に更新されます",
  trialEndsOn: "無料トライアルは{date}に終了します",
  endsOn: "{date}に終了します",
  portal: "支払いと請求書を管理",
  portalHint: "カード、請求書、プランの変更や解約はPolarで行います。",
  portalFailed: "支払いポータルを開けませんでした。",
  confirming: "お支払いを受け付けました。ここに表示されるまで数秒かかることがあります。",
  choose: {
    title: "プランを選択",
    subtitle: "AloStudioを引き続き使うにはプランを選んでください。会話とデータは保存されたままです。",
    notAdmin: "このアカウントには有効なプランがありません。管理者に「設定 → 請求」でプランを選んでもらってください。",
  },
  plans: {
    title: "プラン",
    loadFailed: "プランを読み込めませんでした。",
    empty: "選択できるプランはまだありません。",
    perMonth: "月額 {price}",
    perYear: "年額 {price}",
    trial: "{days}日間の無料トライアル",
    noTrial: "無料トライアルなし",
    choose: "{name}を選択",
    checkoutFailed: "支払いページを開けませんでした。",
  },
  statuses: {
    none: "プランなし",
    incomplete: "支払い未完了",
    trialing: "無料トライアル中",
    active: "有効",
    past_due: "支払い期限切れ",
    canceled: "解約済み",
    unpaid: "未払い",
  },
};
