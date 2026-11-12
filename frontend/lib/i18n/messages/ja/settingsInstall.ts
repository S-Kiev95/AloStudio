import type { settingsInstall as es } from "../es/settingsInstall";
import type { Strings } from "../types";

export const settingsInstall: Strings<typeof es> = {
  configuredCount: "{done}/{total} 件設定済み",
  netConfigured: "設定済み",
  netNotConfigured: "未設定",
  operatorOnly: "この画面はインストールの運用者だけが見られます。デプロイした人にアクセスを依頼してください。",
  loadFailed: "設定を読み込めませんでした。",
  intro: "アカウント単位ではなく、AloStudio 全体に適用される設定です。認証情報がそろうまで空欄のままでかまいません。アプリはなくても動作し、各機能が何が足りないかを知らせます。",
  network: "ネットワーク",
  clearFailed: "削除できませんでした。",
  notConfigured: "未設定",
  configured: "設定済み",
  savedHere: "ここで保存",
  resetToServer: "サーバーの値に戻す",
  fromEnv: "サーバーのファイル (.env) から読み込み",
  groups: {
    meta: "Meta (Facebook と Instagram)",
    mail: "送信メール",
    publishing: "投稿先ネットワーク",
    access: "アクセス",
    webhooks: "Webhook",
    brand: "ブランド",
    ai: "人工知能",
  },
  items: {
    META_APP_ID: {
      title: "Facebook アプリ ID",
      description: "Facebook ログインのフローで AloStudio を Meta に識別させます。クライアントごとではなく、インストール全体で 1 つです。",
    },
    META_APP_SECRET: {
      title: "Facebook アプリシークレット",
      description: "同じアプリのシークレットキー。トークンの交換に使います。",
    },
    META_INSTAGRAM_APP_ID: {
      title: "Instagram アプリ ID",
      description: "Facebook ページが不要な Instagram ログインのフロー用です。Facebook のアプリとは別のアプリです。",
    },
    META_INSTAGRAM_APP_SECRET: {
      title: "Instagram アプリシークレット",
      description: "Instagram アプリのシークレットキー。",
    },
    META_OAUTH_REDIRECT_URI: {
      title: "OAuth リダイレクト URL",
      description: "認可後にブラウザーが戻る先です。https や末尾のスラッシュも含め、Meta の管理画面に登録したものと *完全に* 一致する必要があります。",
    },
    SMTP_HOST: {
      title: "SMTP サーバー",
      description: "AloStudio のメール (パスワード再設定、確認、招待、通知) の送信経路です。Gmail の場合: smtp.gmail.com。",
    },
    SMTP_PORT: {
      title: "SMTP ポート",
      description: "Gmail の場合: 465 (TLS を有効にして)。",
    },
    SMTP_TLS: {
      title: "暗号化接続 (TLS)",
      description: "ポート 465 (Gmail) では有効にします。",
    },
    SMTP_USER: {
      title: "SMTP ユーザー名",
      description: "Gmail の場合: 送信するアカウントの完全なアドレス。",
    },
    SMTP_PASSWORD: {
      title: "SMTP パスワード",
      description: "Gmail の場合: 16 文字のアプリ パスワード (Google アカウント → セキュリティ → アプリ パスワード。2 段階認証が必要)。アカウントのパスワードではありません。",
    },
    MAIL_FROM: {
      title: "差出人",
      description: "差出人として表示される名前。例: \"AloStudio <yourmail@gmail.com>\"。Gmail の場合は同じアカウントである必要があります。",
    },
    PUBLISHING_OAUTH_REDIRECT_URI: {
      title: "ネットワーク接続時のリダイレクト URL",
      description: "カレンダーから接続するすべてのネットワーク (Threads、LinkedIn、TikTok、X、今後追加されるもの) で共通の URL で、認可後にブラウザーが戻る先です。https://<あなたのドメイン>/api/v1/publishing/oauth/callback を、各ネットワークの開発者アプリに同じように登録します。",
    },
    THREADS_APP_ID: {
      title: "Threads アプリ ID",
      description: "Meta アプリの \"Threads App ID\" (基本設定)。Facebook や Instagram のアプリ ID とは別です。",
    },
    THREADS_APP_SECRET: {
      title: "Threads アプリシークレット",
      description: "同じアプリの Threads シークレットキー。",
    },
    LINKEDIN_CLIENT_ID: {
      title: "LinkedIn クライアント ID",
      description: "linkedin.com/developers のアプリの Auth タブにあります。",
    },
    LINKEDIN_CLIENT_SECRET: {
      title: "LinkedIn クライアントシークレット",
      description: "同じ Auth タブの Primary Client Secret。",
    },
    TIKTOK_CLIENT_KEY: {
      title: "TikTok クライアントキー",
      description: "developers.tiktok.com のアプリの App details → Credentials にあります。",
    },
    TIKTOK_CLIENT_SECRET: {
      title: "TikTok クライアントシークレット",
      description: "同じセクションの Client secret。",
    },
    TIKTOK_VERIFICATION_FILE: {
      title: "TikTok 確認ファイル: 名前",
      description: "TikTok アプリ (URL properties) で URL プレフィックス https://<ドメイン>/ を確認すると、ダウンロード用のファイルが渡されます。その名前をそのまま貼り付けてください (例: tiktokAbC123.txt)。本番とサンドボックスごとに別のファイルになるので、カンマで区切ってください。",
    },
    TIKTOK_VERIFICATION_CONTENT: {
      title: "TikTok 確認ファイル: 内容",
      description: "そのファイルの中のテキスト (メモ帳で開いてください)。複数ある場合は、それぞれのテキストをカンマで区切って貼り付けてください。",
    },
    X_CLIENT_ID: {
      title: "X クライアント ID",
      description: "console.x.com のアプリの Keys and tokens → OAuth 2.0 にあります。アプリは Web App で、読み取りと書き込みの権限が必要です。",
    },
    X_CLIENT_SECRET: {
      title: "X クライアントシークレット",
      description: "同じセクションの OAuth 2.0 Client Secret。",
    },
    ENABLE_ACCOUNT_SIGNUP: {
      title: "アカウントの自由登録",
      description: "URL にアクセスした誰でもアカウントを作成し、メール確認なしで管理者として入れるようにします。オフの場合は運用者だけがアカウントを作成します。セルフサービス型のインストールの場合のみ有効にしてください。",
    },
    GOOGLE_CLIENT_ID: {
      title: "Google でログイン: クライアント ID",
      description: "console.cloud.google.com の OAuth クライアント ID (ウェブ アプリケーション) から取得します。これとシークレットがあると、ログイン画面に「Google でログイン」が表示されます。招待済みのユーザーだけが入れます。承認済みのリダイレクト URL: https://<ドメイン>/auth/google/callback。",
    },
    GOOGLE_CLIENT_SECRET: {
      title: "Google でログイン: クライアントシークレット",
      description: "同じ OAuth クライアント ID のシークレット。",
    },
    GOOGLE_ALLOWED_DOMAIN: {
      title: "Google でログイン: 許可するドメイン",
      description: "任意。Google Workspace のドメイン (例: myschool.ac.jp) を指定すると、そのドメインのアカウントだけを受け付けます。空欄の場合は、招待済みユーザーのメールを持つ任意の Google アカウント。",
    },
    META_VERIFY_WEBHOOK_SIGNATURE: {
      title: "Webhook の署名を検証",
      description: "署名が検証できない Meta の Webhook を拒否します。アプリシークレットが必要です。本番では有効にしておいてください。",
    },
    FB_VERIFY_TOKEN: {
      title: "Messenger の確認トークン",
      description: "Messenger の Webhook を登録するときに Meta の管理画面に入力した文字列。Meta はそれを返して URL があなたのものか確認します。",
    },
    IG_VERIFY_TOKEN: {
      title: "Instagram の確認トークン",
      description: "Instagram の Webhook 用の同じもの。",
    },
    APP_BASE_URL: {
      title: "管理画面の公開 URL",
      description: "メール、添付ファイル、OAuth の戻り先のリンクを作るのに使うアドレス。",
    },
    OPENAI_API_KEY: {
      title: "OpenAI キー",
      description: "チャットエージェントと Help Center の検索で使います。platform.openai.com で作成し、そのアカウントで使用量に応じて課金されます。",
    },
    OPENAI_AGENT_MODEL: {
      title: "エージェントのモデル",
      description: "チャットエージェントが使う OpenAI のモデル。例: gpt-5.4-mini (高速で安価) や gpt-5.5 (より高性能)。",
    },
  },
};
