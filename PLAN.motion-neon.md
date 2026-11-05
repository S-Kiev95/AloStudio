# PLAN — Cartel de neón y movimiento

Pedido del dueño (2026-10-30): más vida en el frontend. La marca "AloStudio" brilla como un cartel de neón de verdad (letras que se encienden, alguna que titila, variaciones de brillo) y las páginas entran con una transición en vez de aparecer de golpe.

Rama `feat/motion-neon`, worktree `C:\Users\Zeek\Desktop\AloStudio-motion`, sale de `main` (`9f41162`). **Solo frontend.** Lo hace un agente (Argon) y lo revisa Claude contra este documento.

## Insumos

- `docs/design-neon/DESIGN.md` (sobre todo "The Ignition Rule" y la sección de movimiento) y `frontend/DESIGN-SYSTEM.md`.
- `frontend/app/globals.css`: `.neon-wordmark`, `.neon-sign`, `.lit-tube-ignite`, `@keyframes lit-ignite` y el bloque `@media (prefers-reduced-motion: reduce)`.
- La marca aparece en `components/shell/dashboard-shell.tsx` (menú lateral), `app/(auth)/layout.tsx` (login y demás) y `app/auth/sso/page.tsx`.

## Reglas para el agente

Las mismas de `PLAN.publishing-ui.md`: trabajá **solo** en `C:\Users\Zeek\Desktop\AloStudio-motion`; no leas `C:\Users\Zeek\Desktop\Postiz` ni los otros worktrees de AloStudio; **no toques el backend**; sin `git push`, sin `ssh`, sin `.env*`, sin bases, sin contenedores; **sin librerías nuevas** de npm (nada de Framer Motion: todo con CSS y React; si algo no se puede sin una librería, anotalo en **Estado** y no lo hagas). Commits chicos en `feat/motion-neon`, en español con el estilo del repo (`feat(diseño): ...`), cada uno con todo el cambio que describe su mensaje y terminado en `Co-Authored-By: Antigravity <noreply@google.com>`. Commiteá seguido. Al final completá **Estado** con la salida real y completa de `npm run typecheck`, `npm run lint` y `npm test` en `frontend/`.

## Notas de las revisiones anteriores (cumplilas)

- **Sin modificadores de opacidad sobre colores del tema** (`bg-primary/60`, `text-neon/50`…): Tailwind 3 no genera esas clases con nuestros colores. Usá los tokens (`var(--neon-core)`, `var(--neon-halo)`…) en CSS u `opacity-*`.
- Todo movimiento se apaga con `prefers-reduced-motion: reduce` (sumalo al bloque que ya existe en `globals.css`).
- Cada commit tiene que contener todo el cambio que describe su mensaje.

## 1. Excepción a la regla de encendido (decisión del dueño)

"The Ignition Rule" dice que nada titila ni se repite. El dueño pidió que la **marca** sí lo haga, así que es una excepción **solo** para el logo "AloStudio": botones, pestañas, campos y el resto de la interfaz siguen como están. Agregá a `docs/design-neon/DESIGN.md`, junto a esa regla, un párrafo "Excepción: el cartel de la marca" que diga qué se permite (lo de la sección 2) y que lo decidió el dueño el 2026-10-30.

## 2. El cartel "AloStudio"

- Un componente `components/brand/neon-wordmark.tsx` (`NeonWordmark`, con `className` y `as`/`href` opcionales si hace falta) que reemplace el texto suelto en los tres lugares. Cada letra en su `<span>` con `aria-hidden`, y el conjunto con `aria-label="AloStudio"` para que un lector de pantalla diga la palabra una vez.
- **Encendido** al montar (una vez): las letras se prenden de izquierda a derecha en ~900 ms en total, cada una con uno o dos parpadeos cortos antes de quedar firme (como un tubo que arranca).
- **Zumbido** después: cada 15–45 s (al azar), **una** letra al azar baja el brillo y vuelve en 150–400 ms, a veces con un parpadeo doble; muy de vez en cuando (≈ 1 de cada 4 veces) dos letras seguidas. Nunca más de 3 destellos por segundo (WCAG 2.3.1). La variación es de brillo y `text-shadow`, no de color ni de tamaño.
- **Solo en tema oscuro**: en el claro la marca es cobalto plano y se queda quieta (como hoy).
- Con `prefers-reduced-motion: reduce`: ni encendido ni zumbido, la marca aparece encendida y fija.
- Los temporizadores se limpian al desmontar; con la pestaña oculta (`document.hidden`) no se programa ningún zumbido.
- Que no cambie el tamaño ni el lugar del logo: no puede mover el layout al animar.

## 3. Entrada de las páginas

- `app/accounts/[accountId]/template.tsx` (el `template` de Next se vuelve a montar en cada navegación) que envuelva las páginas en un `div` con una entrada de 220 ms: de `opacity: 0; transform: translateY(6px)` a su lugar, curva `cubic-bezier(0.16, 1, 0.3, 1)` (la de la regla de encendido). Sin salida animada.
- Que no afecte el menú lateral ni la barra superior (están en el `layout`, que no se vuelve a montar).
- Con `prefers-reduced-motion`, sin animación.
- Las páginas de `(auth)` (login, etc.): la tarjeta entra con la misma curva al cargar (una vez).

## 4. Tests

Con Vitest como el resto: `NeonWordmark` expone "AloStudio" una sola vez a lectores de pantalla (`getByLabelText`/`getByRole`), tiene una letra por `span`, y con `matchMedia("(prefers-reduced-motion: reduce)")` en `true` no programa temporizadores (usá `vi.useFakeTimers()`); el `template` renderiza a sus hijos. Actualizá los tests existentes que busquen el texto "AloStudio" si dejan de encontrarlo. Para la sección 5: el encabezado muestra el saludo y los dos botones con sus `href`, y la órbita tiene `aria-hidden`.

## 5. Inicio: la órbita de redes

Pedido del dueño (2026-10-30): el Inicio (`components/overview/account-overview.tsx`, que ya tiene el saludo "Buenos días/tardes/noches") recupera el encabezado de la versión anterior. Referencia visual: `C:\Users\Zeek\Desktop\agy-refs\inicio-orbita.jpg`. Podés abrir esa imagen: es lo único fuera del worktree que podés leer.

- Arriba, en dos columnas desde `md`: a la izquierda el saludo que ya existe, la línea "Todos tus canales, conversaciones y turnos en un solo lugar. Así están las cosas ahora y en los últimos 7 días." y dos botones: **Abrir bandeja** (primario, a `/accounts/{accountId}/conversations`) e **Ir al calendario** (secundario, a `/accounts/{accountId}/publications`). A la derecha, la órbita. El resto de la página queda como está.
- La órbita, en `components/overview/network-orbit.tsx`: en el centro el monograma de la marca (`public/brand/alostudio-icon-512.png`) dentro de un círculo con borde y halo de neón (`--neon-core`, `--neon-halo`); alrededor, dos elipses finas (borde `--neon-glass`) y sobre ellas los íconos de las redes, cada uno en una burbuja redonda con su color de marca: WhatsApp, Instagram, Messenger, Facebook, Threads, TikTok, YouTube, X, Telegram y Gmail.
- Los íconos giran lento por las elipses (una vuelta cada 40–60 s, las dos órbitas a distinta velocidad o en sentidos opuestos), solo con CSS: `@keyframes` con `offset-path`, o un contenedor que rota y cada burbuja contra-rotada para que el ícono quede derecho.
- Íconos: usá `components/ui/brand-icons.tsx`, que ya tiene los logos reales (WhatsApp, Instagram, Messenger, Facebook, Threads, TikTok, X, Telegram y más). Si falta alguno, como YouTube o Gmail, sumá su trazado de Simple Icons (CC0) en ese mismo archivo, sin librerías ni archivos nuevos de íconos.
- Es decorativa: `aria-hidden` y sin foco. Con `prefers-reduced-motion` queda quieta. En pantallas angostas (< `md`) va debajo del texto y más chica, o se oculta si no entra sin romper el layout. En tema claro, la misma composición sin halo (como `.neon-wordmark` de día).

## Fuera de alcance

Librerías de animación, View Transitions experimentales de React/Next, animar listas o tarjetas, sonidos, y cualquier cambio de backend.

## Terminado cuando

Lo de las secciones 1 a 5 con typecheck, lint y tests en verde: la marca se enciende y zumba en tema oscuro sin mover el layout, y el Inicio tiene su encabezado con la órbita de redes.

## Estado

Completadas las secciones 1 a 5 en `feat/motion-neon` (solo CSS + React, sin librerías nuevas):

1. **Excepción a la regla de encendido:** documentada en `docs/design-neon/DESIGN.md` ("Excepción: el cartel de la marca", decisión del dueño del 2026-10-30) y reflejada en `frontend/DESIGN-SYSTEM.md`.
2. **Cartel "AloStudio" (`components/brand/neon-wordmark.tsx`):** `aria-label="AloStudio"` con una letra por `<span aria-hidden="true">`, encendido izquierda-a-derecha en ~900 ms y zumbido aleatorio cada 15–45 s (150–400 ms, simple o doble, 1 de cada 4 veces en dos letras seguidas, <= 3 destellos/s WCAG 2.3.1), activo solo en modo oscuro, detenido con `document.hidden` y con `prefers-reduced-motion: reduce`. Integrado en `dashboard-shell.tsx`, `app/(auth)/layout.tsx`, `app/auth/sso/page.tsx` y `app/auth/google/callback/page.tsx`.
3. **Entrada de páginas:** `app/accounts/[accountId]/template.tsx` con `.page-enter` (`220ms cubic-bezier(0.16, 1, 0.3, 1)`, `opacity: 0; transform: translateY(6px)`, sin salida animada, desactivado bajo `prefers-reduced-motion: reduce`), más entrada única de la tarjeta en `(auth)` y páginas públicas de acceso.
4. **Tests (Vitest):** `components/brand/neon-wordmark.test.tsx`, `app/accounts/[accountId]/template.test.tsx` y `components/overview/account-overview.test.tsx`.
5. **Inicio y órbita de redes:** `YouTube` y `Gmail` (Simple Icons CC0) en `components/ui/brand-icons.tsx`, `components/overview/network-orbit.tsx` con el monograma central y las 10 redes girando con `offset-path` en dos elipses inclinadas (`aria-hidden`, sin foco, sin halo en modo claro y quieta con `prefers-reduced-motion`), y encabezado en dos columnas en `components/overview/account-overview.tsx`.

### Salida real de `npm run typecheck` (`frontend/`)

```text
> alostudio-frontend@0.1.0 typecheck
> tsc --noEmit
```

### Salida real de `npm run lint` (`frontend/`)

```text
> alostudio-frontend@0.1.0 lint
> next lint

`next lint` is deprecated and will be removed in Next.js 16.
For new projects, use create-next-app to choose your preferred linter.
For existing projects, migrate to the ESLint CLI:
npx @next/codemod@canary next-lint-to-eslint-cli .

✔ No ESLint warnings or errors
```

### Salida real de `npm test` (`frontend/`)

```text
> alostudio-frontend@0.1.0 test
> vitest run


 RUN  v2.1.9 C:/Users/Zeek/Desktop/AloStudio-motion/frontend

 ✓ lib/inboxes/email-blocks.test.ts (15 tests) 18ms
 ✓ components/publications/network-rules.test.ts (7 tests) 23ms
 ✓ components/instagram/post-reply-picker.test.tsx (11 tests) 757ms
 ✓ components/publications/publication-detail-dialog.test.tsx (2 tests) 658ms
   ✓ PublicationDetailDialog > habilita Reintentar y Actualizar estadísticas para un administrador en partially_published y Borrar en failed 375ms
 ✓ components/publications/media-library-view.test.tsx (3 tests) 574ms
 ✓ components/oauth/oauth-consent.test.tsx (5 tests) 651ms
   ✓ Pantalla de consentimiento OAuth > muestra la app, el permiso y las cuentas, y al autorizar vuelve a la app con el código 304ms
 ✓ components/publications/analytics-view.test.tsx (3 tests) 596ms
 ✓ components/instagram/instagram-connection.test.tsx (8 tests) 657ms
 ✓ components/agenda/week-view.test.tsx (3 tests) 774ms
   ✓ WeekView > renders Monday-to-Sunday columns and groups appointments by local day in chronological order 329ms
   ✓ AgendaView > loads the current week in weekly view, navigates weeks, and filters by status 380ms
 ✓ components/settings/signatures/signatures-view.test.tsx (2 tests) 1058ms
   ✓ SignaturesView > lista firmas, crea (cuerpo correcto y conteo de puntos de código), edita y borra 770ms
 ✓ components/conversations/conversation-list.test.tsx (5 tests) 907ms
   ✓ ConversationList > offers one channel option per channel the account has 334ms
 ✓ components/settings/inboxes/email-transport-panel.test.tsx (13 tests) 1231ms
 ✓ components/settings/autoposts/autoposts-view.test.tsx (2 tests) 1318ms
   ✓ AutopostsView > lista feeds con revisado hace y último error, prueba el feed (entradas y error 422), crea, edita y borra 1254ms
 ✓ components/settings/sets/sets-view.test.tsx (2 tests) 1141ms
   ✓ SetsView > lista sets con canales y fecha, crea en modo set con el editor, edita y borra 1035ms
stderr | components/settings/inboxes/email-template-panel.test.tsx > EmailTemplatePanel, the visual designer > saves the generated HTML together with its settings
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\email-templates.ts:27:19) undefined

stderr | components/settings/inboxes/email-template-panel.test.tsx > EmailTemplatePanel, the visual designer > sends no design when the HTML was edited by hand
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\email-templates.ts:27:19) undefined

 ✓ components/settings/inboxes/email-template-panel.test.tsx (15 tests) 1413ms
   ✓ EmailTemplatePanel > saves the authored HTML 382ms
stderr | components/settings/inboxes/email-template-panel.test.tsx
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\email-templates.ts:27:19) undefined
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5)
    at queryFn (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\email-templates.ts:27:19) undefined

 ✓ components/settings/plugs/plugs-view.test.tsx (3 tests) 1622ms
   ✓ PlugsView > pide mensaje solo cuando la acción tiene message_max, cuenta UTF-8 de Threads y permite listar, crear, editar y borrar 1093ms
 ✓ components/instagram/post-autoreply-rules.test.tsx (17 tests) 2165ms
 ✓ components/settings/oauth-apps/oauth-apps-view.test.tsx (7 tests) 1594ms
   ✓ Ajustes → Apps OAuth > lista las apps de la cuenta con su client ID, tipo, autorizaciones y la guía de conexión 439ms
   ✓ Ajustes → Apps OAuth > crea una app y muestra el secreto una sola vez 353ms
 ✓ components/agent/agent-chat.test.tsx (14 tests) 2122ms
   ✓ Agente — lista de chats y navegación sin recarga > muestra los chats, la etiqueta 'Por confirmar', no recarga la lista al cambiar de chat y permite borrar con confirmación 553ms
 ✓ components/settings/email-templates/email-templates-view.test.tsx (15 tests) 2120ms
 ✓ components/conversations/inbox-three-column.test.tsx (4 tests) 1546ms
   ✓ Bandeja en tres columnas y pestañas > muestra lista y estado vacío juntos, y cambia entre conversaciones sin recargar la lista 1143ms
   ✓ Bandeja en tres columnas y pestañas > muestra el resumen de reportes de la bandeja y la lista de canales conectados 340ms
 ✓ components/publications/calendar-view.test.tsx (8 tests) 2605ms
   ✓ CalendarView — grilla, paginación y estados > ubica cada publicación en su día y hora local, pide todas las páginas del rango y pinta el estado 766ms
   ✓ CalendarView — grilla, paginación y estados > abre con la línea de ahora en el medio y respeta si el usuario se movió 432ms
   ✓ CalendarView — grilla, paginación y estados > deja crear otra publicación en una hora que ya tiene una 405ms
 ✓ components/publications/publication-editor-dialog.test.tsx (8 tests) 3728ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > arma el cuerpo de publicación programada con fecha ISO, media_id reordenados, post_type y content_override 1404ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > arma borrador (draft: true) y respeta post_type: 'reels' en Instagram 486ms
   ✓ PublicationEditorDialog — armado del cuerpo, reglas y 422 > muestra errores de la tabla de reglas antes de enviar y muestra el 422 del backend con message y errors[] 414ms
   ✓ PublicationEditorDialog — firmas y sets > 'Usar set' carga texto, medios y canales activos (ignorando channel: null) sin cambiar la fecha, y 'Guardar como set' envía el cuerpo esperado 375ms
   ✓ PublicationEditorDialog — TikTok > muestra la cuenta, exige elegir la visibilidad a mano y manda las elecciones 402ms
 ✓ components/settings/installation/installation-view.test.tsx (7 tests) 635ms
 ✓ lib/inboxes/email-template-design.test.ts (12 tests) 17ms
 ✓ components/contacts/contacts-view.test.tsx (4 tests) 780ms
 ✓ middleware.test.ts (7 tests) 32ms
 ✓ components/brand/neon-wordmark.test.tsx (4 tests) 188ms
 ✓ components/conversations/email-message.test.tsx (9 tests) 311ms
 ✓ lib/api/fetcher.test.ts (6 tests) 11ms
 ✓ components/reports/summary-table.test.tsx (3 tests) 364ms
 ✓ components/settings/inboxes/email-branding-panel.test.tsx (7 tests) 463ms
 ✓ components/conversations/email-composer.test.tsx (8 tests) 432ms
 ✓ components/conversations/conversation-filters.test.tsx (3 tests) 471ms
 ✓ components/settings/assignment-policies/assignment-policies-view.test.tsx (3 tests) 543ms
 ✓ components/instagram/connect-capabilities-dialog.test.tsx (6 tests) 308ms
 ✓ components/shell/nav.test.tsx (4 tests) 274ms
stderr | components/reports/reports-view.test.tsx > ReportsView > offers CSV + Excel export links for the current scope
Error: Not implemented: navigation (except hash changes)
    at module.exports (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\browser\not-implemented.js:9:17)
    at navigateFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:77:3)
    at exports.navigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\navigation.js:55:3)
    at LocationImpl._locationObjectNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:31:5)
    at LocationImpl._locationObjectSetterNavigate (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:25:17)
    at LocationImpl.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\window\Location-impl.js:47:10)
    at Location.set href [as href] (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\node_modules\jsdom\lib\jsdom\living\generated\Location.js:125:37)
    at Module.apiFetch (C:\Users\Zeek\Desktop\AloStudio-motion\frontend\lib\api\fetcher.ts:39:21)
    at processTicksAndRejections (node:internal/process/task_queues:105:5) undefined

 ✓ components/reports/reports-view.test.tsx (2 tests) 671ms
   ✓ ReportsView > renders live counters and summary metrics 425ms
 ✓ components/settings/inboxes/channel-form.test.tsx (4 tests) 567ms
 ✓ components/help-center/portal-detail-view.test.tsx (3 tests) 493ms
 ✓ lib/api/notifications.test.tsx (3 tests) 321ms
 ✓ components/overview/account-overview.test.tsx (2 tests) 470ms
   ✓ AccountOverview — encabezado con órbita de redes > muestra el saludo, la bajada y los botones hacia bandeja y calendario 377ms
 ✓ components/settings/integrations/integration-app-view.test.tsx (2 tests) 412ms
 ✓ components/settings/mcp-tokens/mcp-tokens-view.test.tsx (2 tests) 508ms
 ✓ components/instagram/autoreply-view.test.tsx (4 tests) 350ms
 ✓ components/conversations/ai-handoff.test.tsx (4 tests) 384ms
 ✓ components/reports/metric-chart.test.tsx (6 tests) 116ms
 ✓ lib/api/reports-gaps.test.ts (6 tests) 8ms
 ✓ components/settings/automation/automation-rules-view.test.tsx (3 tests) 180ms
 ✓ components/conversations/conversation-participants.test.tsx (3 tests) 386ms
 ✓ components/settings/profile/profile-view.test.tsx (1 test) 245ms
 ✓ lib/realtime/cable.test.ts (3 tests) 10ms
 ✓ components/settings/macros/macros-view.test.tsx (4 tests) 204ms
 ✓ components/ui/tabs.test.tsx (3 tests) 213ms
 ✓ app/(auth)/login/page.test.tsx (3 tests) 566ms
   ✓ LoginPage — a dónde va después de entrar > vuelve a la ruta interna de next con sus parámetros (el consentimiento OAuth) 311ms
 ✓ components/conversations/message-composer-canned.test.tsx (2 tests) 237ms
 ✓ components/settings/csat/csat-view.test.tsx (1 test) 301ms
 ✓ components/campaigns/campaigns-view.test.tsx (1 test) 211ms
 ✓ components/instagram/comments-panel.test.tsx (2 tests) 240ms
 ✓ components/settings/custom-attributes/custom-attributes-view.test.tsx (1 test) 182ms
 ✓ components/settings/agents/agents-view.test.tsx (1 test) 245ms
 ✓ components/campaigns/campaign-analytics-panel.test.tsx (1 test) 161ms
 ✓ components/settings/inboxes/facebook-page-connect.test.tsx (2 tests) 308ms
 ✓ components/conversations/conversation-actions.test.tsx (1 test) 290ms
 ✓ components/settings/canned-responses/canned-responses-view.test.tsx (2 tests) 699ms
   ✓ CannedResponsesView > sends the debounced search term to the backend 437ms
 ✓ components/settings/integrations/integrations-view.test.tsx (1 test) 198ms
 ✓ components/help-center/articles-panel.test.tsx (2 tests) 1279ms
   ✓ ArticlesPanel search > sends the debounced query to the articles endpoint 527ms
   ✓ ArticlesPanel search > clears the search with the reset button 716ms
 ✓ components/settings/webhooks/webhooks-view.test.tsx (1 test) 192ms
 ✓ lib/api/errors.test.ts (8 tests) 7ms
 ✓ components/help-center/portals-view.test.tsx (1 test) 196ms
 ✓ components/shell/page-header.test.tsx (2 tests) 165ms
 ✓ components/reports/traffic-heatmap.test.tsx (3 tests) 188ms
 ✓ components/products/products-view.test.tsx (1 test) 181ms
 ✓ lib/api/uploads.test.ts (3 tests) 63ms
 ✓ components/settings/agent-bots/agent-bots-view.test.tsx (1 test) 162ms
 ✓ components/settings/labels/labels-view.test.tsx (1 test) 249ms
 ✓ components/conversations/message-composer.test.tsx (1 test) 152ms
 ✓ components/conversations/channel-badge.test.tsx (5 tests) 137ms
 ✓ components/ui/button.test.tsx (3 tests) 169ms
 ✓ components/help-center/portal-form.test.tsx (1 test) 229ms
 ✓ components/settings/teams/teams-view.test.tsx (1 test) 164ms
 ✓ components/settings/notifications/push-toggle.test.tsx (1 test) 165ms
 ✓ components/agenda/week-utils.test.ts (4 tests) 34ms
 ✓ lib/api/instagram.test.tsx (1 test) 134ms
 ✓ app/privacidad/page.test.tsx (3 tests) 224ms
 ✓ components/crm/crm-tabs.test.tsx (1 test) 136ms
 ✓ lib/time.test.ts (4 tests) 6ms
 ✓ components/reports/bot-metrics-cards.test.tsx (1 test) 75ms
 ✓ app/terminos/page.test.tsx (2 tests) 151ms
 ✓ app/eliminacion-de-datos/page.test.tsx (2 tests) 121ms
 ✓ lib/auth/schemas.test.ts (3 tests) 4ms
 ✓ app/accounts/[accountId]/template.test.tsx (1 test) 25ms

 Test Files  92 passed (92)
      Tests  385 passed (385)
   Start at  17:36:37
   Duration  21.32s (transform 6.45s, setup 66.40s, collect 74.54s, tests 47.89s, environment 233.03s, prepare 23.15s)
```
