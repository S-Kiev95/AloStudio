# PLAN — Multi-idioma (F13)

Fase F13 de `PLAN.fases-futuras.md`. Agente B. Rama base `feat/f13-idiomas`.
Español es el idioma fuente; inglés y portugués (de Brasil) primero.

## Estado

**Hecho (2026-11-12): la estructura y el primer tramo.**

- `frontend/lib/i18n/`: idiomas (`config.ts`), diccionarios
  (`messages/es.ts`, `en.ts`, `pt.ts`), `t()` (`translate.ts`), el provider
  y los hooks para componentes cliente (`provider.tsx`) y `getT()` para
  componentes de servidor (`server.ts`). Sin librerías nuevas.
- Idioma de cada persona: lo elige en **Ajustes → Mi perfil → Idioma**, se
  guarda en `ui_settings.locale` del usuario y lo sigue a cualquier
  dispositivo. Sin sesión (login, recuperar contraseña) se elige con el
  selector de arriba a la derecha y queda solo en ese navegador. Sin
  elección, el del navegador (`Accept-Language`); si no es uno de los tres,
  español.
- Cómo viaja: la cookie `alo_locale` sirve para el primer render del
  servidor (`<html lang>`, componentes de servidor). Al entrar al panel, si
  el perfil dice otro idioma que la cookie, gana el perfil.
- Traducido: menú lateral, barra de arriba (cuenta, usuario, tema,
  notificaciones), menú de Ajustes, Mi perfil, y las pantallas de acceso
  (iniciar sesión, recuperar y cambiar contraseña, confirmar email) con sus
  validaciones. `relativeTime` ("hace 5m") ya recibe el idioma.
- Para medir lo que falta: `node scripts/i18n-pendientes.mjs` en
  `frontend/` (con `--files`, archivo por archivo). Cuenta líneas con
  letras del español (á, ñ, ¿…), así que se le escapan los textos sin
  tildes ("Guardar", "Cancelar"): sirve para ver la tendencia, no como
  lista completa. Al empezar el barrido: **848 líneas en 173 archivos**.

**Falta:** el barrido del resto de las pantallas (abajo, para Argon), los
textos del backend y el idioma del bot.

---

## Cómo se traduce un componente (convenciones)

1. **El texto va primero a `messages/es.ts`**, en la sección de su pantalla
   (`conversations`, `contacts`, `settings.labels`…). Después la misma clave
   en `en.ts` y `pt.ts`: el typecheck falla si falta una, y un test compara
   que los tres tengan las mismas claves y los mismos `{valores}`.
2. **Componente cliente:** `const t = useT();` y `{t("seccion.clave")}`.
   **Componente de servidor:** `const t = await getT();`.
3. **Valores dentro del texto** con llaves: `"hace {n}m"` →
   `t("time.minutesAgo", { n: 5 })`. Nunca armar frases pegando pedazos
   traducidos: el orden de las palabras cambia entre idiomas.
4. **Plurales:** dos claves (`oneItem` / `manyItems`) y elegir con el número.
   No hace falta nada más para estos tres idiomas.
5. **Listas fijas fuera de un componente** (menús, opciones de un select,
   mapas de estados): guardan la **clave**, no el texto, y el componente
   hace `t(item.label)`. Ejemplos: `components/shell/nav.ts`,
   `components/settings/settings-sidebar.tsx`. Tipo: `MessageKey`.
6. **Validaciones de zod:** el mensaje del esquema es una clave
   (`lib/auth/schemas.ts`) y el formulario la muestra con
   `t(errorKey(error.message))`.
7. **Fechas, horas, números y monedas:** con `Intl` y la etiqueta del
   idioma, nunca con formato a mano: `useIntlTag()` da `"es-UY"`,
   `"en-US"` o `"pt-BR"`. Funciones de `lib/time.ts` reciben `locale`
   (`useLocale()`) como último argumento.
8. **No se traduce:** nombres de redes y marcas (Instagram, WhatsApp, CRM,
   CSAT, MCP), datos del usuario (nombres de contactos, mensajes, etiquetas
   que creó), y los textos legales de `lib/legal` (términos, privacidad,
   eliminación de datos), que quedan en español hasta tener una traducción
   revisada por alguien.
9. **Tests:** los existentes buscan textos en español y siguen andando,
   porque sin provider `t()` responde en español. No cambiar textos en los
   tests salvo que el texto en español haya cambiado.
10. **Tono:** español rioplatense con vos, como el resto de la app; inglés
    neutro; portugués de Brasil con "você".

## Barrido de pantallas (para Argon)

Worktree propio desde `feat/f13-idiomas`; **solo frontend**, sin librerías
nuevas, sin tocar backend, rutas, datos ni llamadas a la API. Un commit por
tanda, en español (`feat(idiomas): ...`), terminado en
`Co-Authored-By: Antigravity <noreply@google.com>`. Al final de cada tanda:
`npm run typecheck`, `npm run lint`, `npm test` en verde y la salida de
`node scripts/i18n-pendientes.mjs`.

Orden (de lo que más se ve a lo que menos), con su sección del diccionario:

1. **Bandeja** (`components/conversations`, `conversations.*`): lista,
   filtros, conversación, compositor, panel del contacto, acciones.
2. **Inicio y estadísticas** (`components/overview`, `components/reports`,
   `overview.*`, `reports.*`).
3. **CRM** (`components/contacts`, `components/products`,
   `components/agenda`, `components/crm`).
4. **Calendario y publicaciones** (`components/publications`): el más
   grande; partirlo en editor, calendario, medios y estadísticas.
5. **Instagram** (`components/instagram`).
6. **Campañas, agente y Help Center** (`components/campaigns`,
   `components/agent`, `components/help-center`).
7. **Ajustes** (`components/settings/*`), una pantalla por commit.
8. **Lo que queda:** notificaciones, `lib/api` (etiquetas de estados y
   tipos), `lib/inboxes`, páginas de error y 404, centro de ayuda público
   (`app/hc`).

Cada pantalla terminada se revisa en el navegador en los tres idiomas
(Ajustes → Mi perfil → Idioma), en claro y oscuro, buscando textos que
quedaron en español y textos que no entran en su lugar (el alemán no está,
pero el portugués suele ser más largo).

## Backend y bot (agente B, después del barrido)

1. **Correos** (confirmación de cuenta, recuperar contraseña, avisos por
   mail): plantillas por idioma, con el `ui_settings.locale` del
   destinatario y español si no tiene.
2. **Avisos push y por WhatsApp** a los agentes: mismo criterio.
3. **Errores de la API** que se muestran tal cual en pantalla: hoy en
   español o en inglés según el caso. Pasar a códigos que el frontend
   traduce, empezando por los más vistos (login, permisos, validaciones).
4. **El bot y el agente responden en el idioma del cliente:** detectar el
   idioma del mensaje entrante y pedírselo explícito al modelo en el prompt
   ("respondé en el idioma del cliente"), sin cambiar las instrucciones de
   cada bandeja. Probar con mensajes en portugués en una bandeja de prueba
   antes de llevarlo a CTC.
5. **Idioma de la cuenta** (`accounts.locale`, ya existe por herencia de
   Chatwoot): por defecto para usuarios nuevos y para el centro de ayuda
   público. Decidir con el dueño si hace falta.

## Criterios de terminado

- `node scripts/i18n-pendientes.mjs` en 0, salvo `lib/legal` y falsos
  positivos anotados acá.
- Las pantallas principales revisadas en los tres idiomas en el navegador.
- Correos y avisos en el idioma del destinatario.
- El bot contesta en portugués a un mensaje en portugués.
