import type { channelCatalog as es } from "../es/channelCatalog";
import type { Strings } from "../types";

export const channelCatalog: Strings<typeof es> = {
  telegram: {
    blurb: "BotFather의 토큰으로 Telegram 봇을 연결하세요.",
    tokenHelp: "봇을 만들 때 @BotFather가 준 토큰입니다.",
    botName: "봇 이름",
    botNameHelp: "선택 — 봇의 @username.",
  },
  whatsapp: {
    blurb: "Meta Cloud API를 통한 WhatsApp Business 번호.",
  },
  phoneNumber: "전화번호",
  sms: {
    blurb: "Bandwidth를 통한 SMS 번호.",
  },
  twilio: {
    blurb: "SMS 또는 WhatsApp용 Twilio 번호.",
    medium: "수단",
  },
  email: {
    blurb: "고객 지원 채널로 쓰는 메일함.",
    address: "이메일 주소",
    imapEnabled: "이메일 받기 (IMAP)",
    imapHelp: "이것이 없으면 받은 메일이 받은편지함에 들어오지 않습니다.",
    imapServer: "IMAP 서버",
    imapPort: "IMAP 포트",
    imapUser: "IMAP 사용자 이름",
    imapPassword: "IMAP 비밀번호",
    appPasswordHelp: "2단계 인증을 사용한다면 앱 비밀번호를 사용하세요.",
    imapSsl: "보안 IMAP 연결 (SSL)",
    smtpEnabled: "이메일 보내기 (SMTP)",
    smtpServer: "SMTP 서버",
    smtpPort: "SMTP 포트",
    smtpUser: "SMTP 사용자 이름",
    smtpPassword: "SMTP 비밀번호",
    smtpStarttls: "보안 SMTP 연결 (STARTTLS)",
  },
  web: {
    blurb: "웹사이트에 넣는 채팅.",
    siteUrl: "사이트 URL",
    welcomeTitle: "환영 제목",
    welcomePlaceholder: "안녕하세요! 👋",
    tagline: "부제목",
  },
  api: {
    blurb: "HTTP API를 통한 범용 채널 (발신 웹훅은 선택).",
    webhookHelp: "선택 — 받은 메시지를 전달할 곳.",
  },
  facebook: {
    blurb: "Facebook 페이지의 메시지와 게시물.",
    userTokenHelp: "선택 — 페이지 토큰이 만료되면 갱신하기 위해.",
    instagramIdHelp: "선택 — 페이지가 IG 계정에 연결되어 있다면.",
  },
  instagram: {
    blurb: "토큰 방식의 IG 비즈니스. 게시와 댓글 관리는 메뉴의 Instagram 섹션을 사용하세요.",
  },
};
