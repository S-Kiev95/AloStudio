import type { settingsInstall as es } from "../es/settingsInstall";
import type { Strings } from "../types";

export const settingsInstall: Strings<typeof es> = {
  configuredCount: "{done}/{total}개 설정됨",
  netConfigured: "설정됨",
  netNotConfigured: "설정 안 됨",
  operatorOnly: "이 화면은 설치 운영자만 볼 수 있습니다. 배포한 사람에게 접근 권한을 요청하세요.",
  loadFailed: "설정을 불러오지 못했습니다.",
  intro: "계정 하나가 아니라 AloStudio 전체에 적용되는 설정입니다. 자격 증명이 준비될 때까지 비워 둬도 됩니다. 앱은 이것 없이도 작동하며, 각 기능이 무엇이 빠졌는지 알려 줍니다.",
  network: "네트워크",
  clearFailed: "지우지 못했습니다.",
  notConfigured: "설정 안 됨",
  configured: "설정됨",
  savedHere: "여기서 저장됨",
  resetToServer: "서버 값으로 되돌리기",
  fromEnv: "서버 파일(.env)에서 가져옴",
  groups: {
    meta: "Meta (Facebook 및 Instagram)",
    mail: "발신 메일",
    publishing: "게시용 네트워크",
    access: "접근",
    webhooks: "웹훅",
    brand: "브랜드",
    ai: "인공지능",
  },
  items: {
    META_APP_ID: {
      title: "Facebook 앱 ID",
      description: "Facebook 로그인 절차에서 Meta에 AloStudio를 식별시킵니다. 고객마다가 아니라 설치 전체에 하나입니다.",
    },
    META_APP_SECRET: {
      title: "Facebook 앱 시크릿",
      description: "같은 앱의 시크릿 키입니다. 토큰 교환에 사용됩니다.",
    },
    META_INSTAGRAM_APP_ID: {
      title: "Instagram 앱 ID",
      description: "Facebook 페이지가 필요 없는 Instagram 로그인 절차용입니다. Facebook 앱과는 다른 앱입니다.",
    },
    META_INSTAGRAM_APP_SECRET: {
      title: "Instagram 앱 시크릿",
      description: "Instagram 앱의 시크릿 키입니다.",
    },
    META_OAUTH_REDIRECT_URI: {
      title: "OAuth 리디렉션 URL",
      description: "승인 후 브라우저가 돌아오는 곳입니다. https와 마지막 슬래시까지 Meta 대시보드에 입력한 것과 *정확히* 일치해야 합니다.",
    },
    SMTP_HOST: {
      title: "SMTP 서버",
      description: "AloStudio 이메일(비밀번호 재설정, 확인, 초대, 알림)이 나가는 경로입니다. Gmail은 smtp.gmail.com.",
    },
    SMTP_PORT: {
      title: "SMTP 포트",
      description: "Gmail은 465 (TLS 사용).",
    },
    SMTP_TLS: {
      title: "암호화 연결 (TLS)",
      description: "465 포트(Gmail)에서는 켭니다.",
    },
    SMTP_USER: {
      title: "SMTP 사용자 이름",
      description: "Gmail은 발신 계정의 전체 주소.",
    },
    SMTP_PASSWORD: {
      title: "SMTP 비밀번호",
      description: "Gmail은 16자리 앱 비밀번호(Google 계정 → 보안 → 앱 비밀번호, 2단계 인증 필요). 계정 비밀번호가 아닙니다.",
    },
    MAIL_FROM: {
      title: "보내는 사람",
      description: "보내는 사람으로 표시되는 값입니다. 예: \"AloStudio <yourmail@gmail.com>\". Gmail은 같은 계정이어야 합니다.",
    },
    PUBLISHING_OAUTH_REDIRECT_URI: {
      title: "네트워크 연결 리디렉션 URL",
      description: "캘린더에서 연결하는 모든 네트워크(Threads, LinkedIn, TikTok, X 및 추가될 네트워크)에 공통인 URL로, 승인 후 브라우저가 돌아오는 곳입니다. https://<내 도메인>/api/v1/publishing/oauth/callback이며 각 네트워크의 개발자 앱에 똑같이 입력합니다.",
    },
    THREADS_APP_ID: {
      title: "Threads 앱 ID",
      description: "Meta 앱의 \"Threads App ID\"(기본 설정)로, Facebook 및 Instagram 앱 ID와 다릅니다.",
    },
    THREADS_APP_SECRET: {
      title: "Threads 앱 시크릿",
      description: "같은 앱의 Threads 시크릿 키입니다.",
    },
    LINKEDIN_CLIENT_ID: {
      title: "LinkedIn 클라이언트 ID",
      description: "linkedin.com/developers의 앱, Auth 탭에 있습니다.",
    },
    LINKEDIN_CLIENT_SECRET: {
      title: "LinkedIn 클라이언트 시크릿",
      description: "같은 Auth 탭의 Primary Client Secret입니다.",
    },
    TIKTOK_CLIENT_KEY: {
      title: "TikTok 클라이언트 키",
      description: "developers.tiktok.com의 앱, App details → Credentials에 있습니다.",
    },
    TIKTOK_CLIENT_SECRET: {
      title: "TikTok 클라이언트 시크릿",
      description: "같은 섹션의 Client secret입니다.",
    },
    TIKTOK_VERIFICATION_FILE: {
      title: "TikTok 인증 파일: 이름",
      description: "TikTok 앱(URL properties)에서 URL 접두사 https://<도메인>/을 인증하면 TikTok이 다운로드할 파일을 줍니다. 그 이름을 그대로 붙여 넣으세요. 예: tiktokAbC123.txt. 프로덕션과 샌드박스마다 다른 파일을 주니 쉼표로 구분하세요.",
    },
    TIKTOK_VERIFICATION_CONTENT: {
      title: "TikTok 인증 파일: 내용",
      description: "그 파일 안의 텍스트(메모장으로 여세요). 파일이 여러 개라면 각각의 텍스트를 쉼표로 구분해 붙여 넣으세요.",
    },
    X_CLIENT_ID: {
      title: "X 클라이언트 ID",
      description: "console.x.com의 앱, Keys and tokens → OAuth 2.0에 있습니다. 앱은 읽기 및 쓰기 권한이 있는 Web App 유형이어야 합니다.",
    },
    X_CLIENT_SECRET: {
      title: "X 클라이언트 시크릿",
      description: "같은 섹션의 OAuth 2.0 Client Secret입니다.",
    },
    ENABLE_ACCOUNT_SIGNUP: {
      title: "자유 계정 가입",
      description: "URL에 들어온 누구나 이메일 확인 없이 계정을 만들고 관리자로 들어올 수 있게 합니다. 끄면 운영자만 계정을 만듭니다. 셀프서비스 설치일 때만 켜세요.",
    },
    GOOGLE_CLIENT_ID: {
      title: "Google로 로그인: 클라이언트 ID",
      description: "console.cloud.google.com의 OAuth 클라이언트 ID(웹 애플리케이션)에서 가져옵니다. 이 값과 시크릿이 있으면 로그인 화면에 «Google로 로그인»이 표시됩니다. 이미 초대된 사용자만 들어올 수 있습니다. 승인된 리디렉션 URL: https://<도메인>/auth/google/callback.",
    },
    GOOGLE_CLIENT_SECRET: {
      title: "Google로 로그인: 클라이언트 시크릿",
      description: "같은 OAuth 클라이언트 ID의 시크릿입니다.",
    },
    GOOGLE_ALLOWED_DOMAIN: {
      title: "Google로 로그인: 허용 도메인",
      description: "선택 사항. Google Workspace 도메인(예: myschool.ac.kr)을 지정하면 그 도메인의 계정만 허용합니다. 비워 두면 초대된 사용자의 이메일을 가진 모든 Google 계정이 허용됩니다.",
    },
    META_VERIFY_WEBHOOK_SIGNATURE: {
      title: "웹훅 서명 확인",
      description: "서명이 유효하지 않은 Meta 웹훅을 거부합니다. 앱 시크릿이 필요합니다. 프로덕션에서는 켜 두세요.",
    },
    FB_VERIFY_TOKEN: {
      title: "Messenger 확인 토큰",
      description: "Messenger 웹훅을 등록할 때 Meta 대시보드에 입력한 텍스트입니다. Meta가 이를 되돌려 보내 URL이 당신의 것인지 확인합니다.",
    },
    IG_VERIFY_TOKEN: {
      title: "Instagram 확인 토큰",
      description: "Instagram 웹훅용으로 같은 것입니다.",
    },
    APP_BASE_URL: {
      title: "대시보드 공개 URL",
      description: "이메일, 첨부 파일, OAuth 복귀 링크를 만들 때 쓰는 주소입니다.",
    },
    OPENAI_API_KEY: {
      title: "OpenAI 키",
      description: "채팅 에이전트와 Help Center 검색에 사용됩니다. platform.openai.com에서 만들며, 그 계정에서 사용량에 따라 과금됩니다.",
    },
    OPENAI_AGENT_MODEL: {
      title: "에이전트 모델",
      description: "채팅 에이전트가 쓰는 OpenAI 모델입니다. 예: gpt-5.4-mini(빠르고 저렴) 또는 gpt-5.5(더 뛰어남).",
    },
  },
};
