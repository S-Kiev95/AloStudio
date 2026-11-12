# PLAN — Multi-idioma (F13)

Fase F13 de `PLAN.fases-futuras.md`. Agente B. Rama `feat/f13-idiomas`.
Español es el idioma fuente. Idiomas: **español, inglés, portugués (de
Brasil), francés, alemán, japonés y coreano**.

## Estado

**Hecho (2026-11-12): toda la interfaz del panel, en los siete idiomas.**

- `frontend/lib/i18n/`: idiomas y su etiqueta para `Intl` (`config.ts`),
  `t()` con claves tipadas (`translate.ts`), provider y hooks para
  componentes cliente (`provider.tsx`: `useT`, `useLocale`, `useIntlTag`),
  `getT()` para componentes de servidor (`server.ts`), `rich()` para frases
  con elementos adentro (`rich.tsx`) y `clientT()` para textos que se arman
  fuera de React (`client-t.ts`). Sin librerías.
- Diccionarios: `messages/<idioma>/`, un archivo por sección (`core.ts`
  con lo común, y `conversations.ts`, `settingsInboxes.ts`…), reunidos en
  `messages/<idioma>/index.ts`. El tipo `Strings<T>` obliga a que cada idioma
  tenga exactamente las claves del español: si falta una, no compila.
- Idioma de cada persona: **Ajustes → Mi perfil → Idioma**, guardado en
  `ui_settings.locale` del usuario. Sin sesión (login, recuperar
  contraseña), selector arriba a la derecha. Sin elección, el del navegador
  (`Accept-Language`); si no es uno de los siete, español.
- Cómo viaja: la cookie `alo_locale` sirve para el primer render del
  servidor; al entrar al panel, si el perfil dice otro idioma, gana el
  perfil.
- Barrido terminado: bandeja, inicio, reportes, CRM, agenda, calendario y
  publicaciones, Instagram, campañas, agente, Help Center (panel y sitio
  público), notificaciones, páginas de error, todo Ajustes, y los mapas y
  mensajes de `lib/api` y `lib/inboxes`.
- `node scripts/i18n-pendientes.mjs` (en `frontend/`) da **58 textos**, todos
  nombres de marca o términos técnicos que no se traducen (Instagram,
  Telegram, Slug, SKU, CSV, Client ID…). Empezó en 1254.

**Backend (2026-11-12):** correos, avisos push y por WhatsApp en el idioma de
cada destinatario, e Instalación y Plugs traducidos en el panel (detalle
abajo). **Falta:** el bot externo, los errores de la API y la revisión en el
navegador.

---

## Herramientas (`frontend/scripts/`)

- `i18n-pendientes.mjs [carpetas…]`: lista los textos de interfaz que
  siguen fijos en el código (lee el árbol de TypeScript; no necesita tildes
  para encontrarlos). Se saltea una línea con `// i18n-ignore` y un tramo
  entre `i18n-ignore-start` / `i18n-ignore-end`. Excluye `lib/legal`,
  `components/legal` y `app/api`.
- `i18n-tool.mjs`:
  - `apply <mapeo>`: cada línea `ruta:línea seccion.clave` reemplaza el
    texto de esa línea por `t("seccion.clave")` y agrega el español al
    diccionario. `~fragmento` elige entre dos textos de la misma línea; `!`
    deja la clave como texto (para listas fuera de un componente, que
    después se muestran con `t(item.label)`). `= x:1 seccion.clave Texto`
    solo agrega el español. Valida todo antes de escribir nada. No escribe
    en las secciones de `core.ts`: las claves nuevas van en otra sección.
  - `ensure <archivos>`: agrega `const t = useT()` (o `await getT()` en
    componentes de servidor de `app/`) y los imports.
  - `dump <seccion>`: el español de una sección, `clave=texto`.
  - `putall <idioma> <archivo>`: bloques `### seccion` con `clave=texto`;
    solo completa claves que ya existen en español.

Ojo con `!` en entradas de una sola línea (`{ value: "x", label: "Y" }`):
toma el primer texto de la línea. Esos casos se hacen a mano.

## Cómo se traduce un componente (convenciones)

1. **El texto va primero al español**, en la sección de su pantalla. Después
   la misma clave en los otros seis idiomas: el typecheck falla si falta.
2. **Componente cliente:** `const t = useT();` y `{t("seccion.clave")}`.
   **Componente de servidor:** `const t = await getT();`. **Fuera de React**
   (validaciones de `lib/api`, valores por defecto): `clientT()`, que lee el
   idioma de la cookie.
3. **Valores dentro del texto** con llaves: `t("time.minutesAgo", { n: 5 })`.
   Nunca armar frases pegando pedazos traducidos: el orden cambia entre
   idiomas. Si la frase lleva un enlace, negrita o `<code>`, `rich()`:
   `rich(t("x.frase"), { nombre: <strong>…</strong> })`.
4. **Plurales:** dos claves (`fooOne` / `fooMany`) y elegir con el número.
   En japonés y coreano suelen tener el mismo texto.
5. **Listas fijas fuera de un componente** (opciones, mapas de estados,
   catálogos): guardan la **clave** (tipo `MessageKey`) y el componente hace
   `t(item.label)`. El catálogo de canales mezcla claves y nombres técnicos
   en inglés ("Bot token"): se muestra con `t(texto as MessageKey)`, que
   devuelve tal cual lo que no conoce.
6. **Fechas, horas y números:** con `Intl` y `useIntlTag()`; las funciones
   de fechas (`lib/time.ts`, `week-utils.ts`, `calendar-utils.ts`,
   `agent-time.ts`) reciben el idioma como último argumento.
7. **No se traduce:** nombres de redes y marcas, datos del usuario, términos
   de protocolo (OAuth, PKCE, IMAP…), y los textos legales de `lib/legal`,
   que quedan en español hasta tener una traducción revisada.
8. **Tests:** buscan textos en español y siguen andando, porque sin
   provider `t()` responde en español y `clientT()` sin cookie también.
9. **Tono:** español rioplatense con vos; inglés neutro; portugués de Brasil
   con "você"; francés con "vous"; alemán con "du", como las apps de
   consumo; japonés en です/ます; coreano en 합니다/해요 según el caso.
10. **Una variable `t` por alcance:** no usar `t` como nombre en
    `.map((t) => …)`, tapa el traductor.

## Lo que falta

### Revisión en el navegador
Recorrer bandeja, calendario, Ajustes y el login en cada idioma, en claro y
oscuro, buscando textos que no entran (botones y pestañas en alemán y
francés) y frases que quedaron raras.

### Pendiente del backend y el bot
1. **El bot que atiende clientes:** en este repo no hay un modelo que le
   conteste al cliente; el bot entra de afuera (webhooks de AgentBot o MCP)
   y deriva con `bot_handoff`. Falta confirmar con el dueño cuál es ese bot
   en CTC. La regla para que conteste en el idioma del cliente quedó en
   `INTEGRATIONS.md` ("Replying in the customer's language"), para aplicarla
   en ese bot y probarla con un mensaje en portugués en una bandeja de
   prueba.
2. **Errores de la API:** pasar a códigos que el frontend traduce (ya hay
   dos: `not_authorized` y `too_many_attempts`, en `lib/api/errors.ts`).
3. **Plantilla de WhatsApp en otros idiomas:** cargar y aprobar en Meta la
   variante de `aviso_derivacion` en cada idioma que se use; hasta entonces
   el aviso sale en español.
4. **Idioma de la cuenta** (`accounts.locale`): por defecto para usuarios
   nuevos y el centro de ayuda público. Decidir con el dueño.

## Backend (hecho el 2026-11-12)

- **`app/core/i18n/`**: catálogos por idioma (`es.py`, `en.py`…),
  `t(locale, clave, **valores)`, `user_locale(user)` (lee
  `ui_settings.locale`; español si no eligió) y `mail_text()` (saludo,
  cuerpo y firma). `tests/unit/test_i18n_catalogs.py` compara las claves y
  los `{valores}` de los siete idiomas con el español.
- **Correos en el idioma del destinatario:** confirmar email, recuperar
  contraseña, avisos por mail, e invitaciones (en el idioma del invitado si
  ya eligió uno; si no, en el de quien invita).
- **Avisos push** en el idioma del destinatario.
- **Aviso por WhatsApp:** usa la variante de la plantilla en el idioma del
  destinatario si Meta la tiene aprobada; si no, la de español, como antes.
- **Quien nunca eligió idioma en el perfil:** al entrar al panel se guarda
  el que está viendo (el del selector del login o el del navegador), para
  que los correos le lleguen en ese idioma.
- **Ajustes → Instalación y Plugs:** el backend sigue mandando sus textos en
  español; el panel los traduce por el nombre del ajuste o el id de la
  acción (`translateOr`) y muestra el del backend si no conoce la clave.
  Un ajuste nuevo en `registry.py` necesita sus claves en
  `settingsInstall.items.<NOMBRE>`.
- **Agente del panel:** ya respondía en el idioma del usuario; ahora además
  sabe en qué idioma tiene la app, para cuando el mensaje no lo deja claro.

## Criterios de terminado

- `i18n-pendientes.mjs` solo con marcas y términos técnicos. **Cumplido.**
- Pantallas principales revisadas en el navegador en cada idioma.
- Correos y avisos en el idioma del destinatario. **Cumplido.**
- El bot contesta en portugués a un mensaje en portugués.
