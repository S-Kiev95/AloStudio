# Plantilla de WhatsApp `aviso_derivacion` en cada idioma

Cuando el bot deriva una conversación a una persona, AloStudio le manda un
WhatsApp al agente que lo pidió (Ajustes → Notificaciones → Aviso por
WhatsApp). Ese mensaje es una **plantilla aprobada por Meta**, y sale en el
idioma que el agente eligió en su perfil **si existe la variante aprobada en
ese idioma**; si no, en español (`app/domains/notifications/whatsapp.py`).

Las plantillas no se crean desde AloStudio: se cargan en el **WhatsApp
Manager** de Meta (Administrador de WhatsApp → Plantillas de mensajes), en la
cuenta de WhatsApp Business del número que manda los avisos. Después, en
AloStudio, la bandeja de ese número trae las plantillas sola (o desde la API
de sincronización de plantillas).

## Cómo cargar cada idioma

En Meta, una plantilla tiene un **nombre** y una **variante por idioma**. Hay
que agregar idiomas a la plantilla que ya existe, no crear otra:

- **Nombre:** `aviso_derivacion` (el mismo, siempre).
- **Categoría:** Utilidad (`UTILITY`).
- **Idioma:** el código de la tabla de abajo.
- **Cuerpo:** el texto de abajo, con las tres variables en el mismo orden:
  `{{1}}` el nombre del contacto, `{{2}}` el nombre de la bandeja y `{{3}}`
  el número de la conversación.
- Sin encabezado, pie ni botones (el aviso no los manda).

Meta pide un ejemplo para cada variable: por ejemplo `Ana Pérez`,
`Instituto`, `128`.

| Idioma del perfil | Código en Meta |
|---|---|
| Español | `es` (la que ya está) |
| Inglés | `en` |
| Portugués | `pt_BR` |
| Francés | `fr` |
| Alemán | `de` |
| Japonés | `ja` |
| Coreano | `ko` |

Solo hace falta cargar los idiomas que de verdad usen los agentes. Mientras
una variante no esté aprobada, ese agente recibe la de español.

## Textos propuestos

La versión en español es la que ya está aprobada; si su texto es distinto,
conviene adaptar las demás para que digan lo mismo.

**Español (`es`)**
> {{1}} necesita hablar con una persona en {{2}}. El bot derivó la
> conversación #{{3}}: entrá a AloStudio para responderle.

**Inglés (`en`)**
> {{1}} needs to talk to a person in {{2}}. The bot handed off conversation
> #{{3}}: open AloStudio to reply.

**Portugués (`pt_BR`)**
> {{1}} precisa falar com uma pessoa em {{2}}. O bot transferiu a conversa
> #{{3}}: entre no AloStudio para responder.

**Francés (`fr`)**
> {{1}} a besoin de parler à une personne dans {{2}}. Le bot a transféré la
> conversation #{{3}} : ouvrez AloStudio pour répondre.

**Alemán (`de`)**
> {{1}} möchte mit einer Person in {{2}} sprechen. Der Bot hat die
> Konversation #{{3}} übergeben: Öffne AloStudio, um zu antworten.

**Japonés (`ja`)**
> {{1}} さんが {{2}} で担当者との会話を希望しています。ボットが会話 #{{3}}
> を引き継ぎました。AloStudio を開いて返信してください。

**Coreano (`ko`)**
> {{1}} 님이 {{2}}에서 상담원과의 대화를 원합니다. 봇이 대화 #{{3}}을(를)
> 넘겼습니다. AloStudio에서 답장하세요.

Cuando el contacto no tiene nombre, AloStudio pone en `{{1}}` "Un contacto"
en el idioma de la variante que se usa ("A contact", "Um contato"…).
