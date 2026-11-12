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

**Falta:** revisar en el navegador las pantallas principales en cada idioma
(textos que no entran, sobre todo alemán y francés), los textos que manda
el backend, y el idioma del bot (abajo).

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

### Textos que vienen del backend
Hoy llegan en español y se muestran tal cual: los grupos y nombres de
**Ajustes → Instalación**, el **catálogo de Plugs** (nombre y descripción de
cada acción) y los mensajes de error de la API.

### Backend y bot
1. **Correos** (confirmación de cuenta, recuperar contraseña, avisos):
   plantillas por idioma con el `ui_settings.locale` del destinatario.
2. **Avisos push y por WhatsApp** a los agentes: mismo criterio.
3. **Errores de la API:** pasar a códigos que el frontend traduce (ya hay
   dos: `not_authorized` y `too_many_attempts`, en `lib/api/errors.ts`).
4. **El bot responde en el idioma del cliente:** pedírselo explícito al
   modelo en el prompt, sin cambiar las instrucciones de cada bandeja.
   Probar con mensajes en portugués en una bandeja de prueba antes de
   llevarlo a CTC.
5. **Idioma de la cuenta** (`accounts.locale`): por defecto para usuarios
   nuevos y el centro de ayuda público. Decidir con el dueño.

## Criterios de terminado

- `i18n-pendientes.mjs` solo con marcas y términos técnicos. **Cumplido.**
- Pantallas principales revisadas en el navegador en cada idioma.
- Correos y avisos en el idioma del destinatario.
- El bot contesta en portugués a un mensaje en portugués.
