# PLAN — Sistema de diseño neón en el frontend de AloStudio

Paso 0 de la salida de Postiz (Fase 7): el frontend de AloStudio pasa a ser el producto final, con el estilo del rediseño que ya tiene el fork de Postiz ("The Hand-Bent Neon Room"). Se hace **antes** de migrar más pantallas, para que todo lo nuevo nazca con el estilo final.

Rama `feat/design-neon`, worktree `C:\Users\Zeek\Desktop\AloStudio-design`. Lo implementa un agente y lo revisa Claude contra este documento.

## Insumos (todo está en este worktree)

| Archivo | Qué es |
|---|---|
| `docs/design-neon/DESIGN.md` | **La fuente de verdad.** Paleta (noche y día), tipografías, radios, sombras, reglas con nombre y especificación de cada componente. |
| `docs/design-neon/PRODUCT.md` | Para quién es el producto y su tono. Algunas líneas hablan del monorepo de Postiz: ignoralas. |
| `docs/design-neon/neon-tokens.reference.scss` | Los valores exactos de los tokens `--neon-*` en noche y día, como se implementaron en el fork. |
| `docs/design-neon/neon-surfaces.reference.scss` | Las superficies ya resueltas (tubo encendido, panel de vidrio, cartel, pestaña, campo, ignición, `prefers-reduced-motion`). Los selectores son de otra app: tomá los valores y las técnicas, no los nombres de clase. Ignorá lo que sea del login o del carrusel. |
| `docs/design-neon/screens/*.png` | Capturas del rediseño a 1440×900 (y `crm-mobile.png` a 390 px): `home`, `calendar`, `inbox`, `crm`, `analytics`, `settings`, `login`. Es el resultado al que hay que llegar. |
| `frontend/public/brand/alostudio-icon-{180,192,512,1024}.png` | Ícono de la app (la "A" neón). |

## Reglas para el agente

1. Trabajá **solo** dentro de `C:\Users\Zeek\Desktop\AloStudio-design`. No abras ni leas `C:\Users\Zeek\Desktop\Postiz` ni `C:\Users\Zeek\Desktop\AloStudio` (salvo usar su `.venv` si te hiciera falta, que no debería). Todo lo que necesitás está en los insumos.
2. Solo frontend (`frontend/`) y documentación. No toques el backend, las migraciones, `scripts/` ni `tests/` de Python.
3. Sin librerías nuevas de npm. Las fuentes van con `next/font/google`, que ya viene con Next.
4. Prohibido: `git push`, `ssh`, tocar archivos `.env*`, `docker compose down`, borrar volúmenes o contenedores.
5. Commits chicos en `feat/design-neon`, en español con el estilo del repo (`feat(design): ...`, `refactor(ui): ...`, `test(ui): ...`), terminados con `Co-Authored-By: Antigravity <noreply@google.com>`.
6. Al terminar, completá **Estado** al final de este archivo: qué se hizo, qué quedó y la salida real de cada verificación. Si una verificación la corriste sobre una parte del código, decilo.

## Entorno

- `cd frontend && npm ci` una vez.
- Verificaciones: `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`.
- Para mirar tu trabajo: `npm run dev -- -p 3200`. Sin backend solo cargan las páginas públicas (`/login`, `/forgot-password`). Podés sacar capturas con el Playwright que ya está instalado (`node_modules/playwright`, Chromium ya descargado), en noche y en día. Guardalas en `docs/design-neon/after/` y commitealas. El resto de las pantallas las revisa Claude con el backend.

## Cómo está hoy el frontend

- Tokens semánticos en `frontend/app/globals.css` (`--bg`, `--surface`, `--surface-2`, `--surface-3`, `--fg`, `--fg-muted`, `--border`, `--border-strong`, `--primary`, `--primary-active`, `--primary-fg`, `--success`, `--warning`, `--danger`, `--info`, `--ring`, sombras, `--gradient-primary`, `--canvas-accent`, `--edge-highlight`, `--glow-primary`), mapeados en `frontend/tailwind.config.ts`. Hoy tienen un estilo "Binance" (amarillo `#fcd535` sobre casi negro). Tema con `next-themes` y la clase `.dark`.
- Fuentes: `Inter` y `JetBrains_Mono` en `frontend/app/layout.tsx`.
- Componentes base en `frontend/components/ui/` (`button`, `card`, `input`, `textarea`, `label`, `avatar`).
- Shell en `frontend/components/shell/` (`dashboard-shell.tsx` con la barra lateral de 256 px y la barra superior, `sidebar-nav.tsx`, `nav.ts`, `theme-toggle.tsx`, `account-switcher.tsx`, `notification-bell.tsx`).
- Cada página arma su propio encabezado (título `h1` + descripción + acciones); no hay un componente compartido.
- `frontend/DESIGN-SYSTEM.md` describe el estilo Binance.
- Los colores fijos que quedan en componentes son de marcas de canales (WhatsApp, Instagram, etc.) y colores que elige el usuario en el Help Center: **esos se quedan como están**.

## 1. Tokens y fuentes

- Reescribí los **valores** de los tokens semánticos con la paleta de `DESIGN.md`, en `:root` (día) y `.dark` (noche). Los nombres se quedan: así las 200 pantallas cambian solas. Guía de equivalencias (ajustala si `DESIGN.md` lo pide):
  - `--bg` → night-ground / daylight-ground; `--surface` → panel / daylight-panel; `--surface-2` → panel-raised; `--surface-3` → focused-glass; `--border` → unlit-glass / daylight-border; `--border-strong` → separator; `--fg` → text-primary; `--fg-muted` → text-secondary; `--primary` → cobalt-core; `--primary-active` → cobalt-core-hover; `--primary-fg` → blanco; `--ring` → cobalt-core.
  - `--success`, `--warning`, `--danger`, `--info`: elegí valores que convivan con la paleta y cumplan contraste AA en los dos temas. **Nunca** naranja electrodo para advertencias.
- Agregá los tokens propios del mundo neón (`--neon-core`, `--neon-halo`, `--neon-halo-far`, `--neon-edge`, `--neon-lit-text`, `--neon-unlit-text`, `--neon-hum`, `--neon-glass`, `--neon-glass-highlight`, `--neon-field`, `--neon-hover-glass`, `--neon-focused-glass`, `--neon-electrode`, ambient spill) con los valores de `neon-tokens.reference.scss`, y exponelos en Tailwind (por ejemplo `bg-field`, `text-lit`, `bg-focused`, `bg-hover-glass`, `text-electrode`, `border-glass`).
- `--canvas-accent` pasa a ser el ambient spill arriba a la izquierda. `--gradient-primary` deja de ser un degradé amarillo: cobalto sólido o eliminarlo y reemplazar sus 15 usos.
- Radios: agregá `control` (10px) y `panel` (16px); cards y tablas 8px, chips 4px, toggles pill.
- Fuentes con `next/font/google`: **Geologica** (texto, `font-sans`, 300–700, `latin` y `latin-ext`), **Tilt Neon** (`font-display`: carteles, navegación, pestañas) y **Neonderthaw** (`font-script`: solo la marca). Sacá `Inter`. Los números en tablas con `tabular-nums` (podés dejar `font-numeric` apuntando a Geologica con `tnum`).
- `prefers-reduced-motion`: sin ignición ni transiciones de luz.

## 2. Componentes base (`components/ui/`)

Según la sección **Components** de `DESIGN.md`:

- **Button:** `primary` = tubo encendido (cobalto, texto blanco, halo; hover más brillante); `secondary` = panel elevado sin luz; variante tranquila = vidrio translúcido con borde; `destructive`/`ghost` sin tubo cobalto; agregá una variante `ai` en naranja electrodo para acciones de IA. 40 px de alto, radio 10px. Mantené las variantes y props que ya usan las pantallas (buscá todos los usos) y el área táctil de 44 px.
- **Input / Textarea:** campo hundido (`--neon-field`), borde de vidrio de 1px, radio 10px, 44 px de alto en inputs; con foco, borde cobalto y anillo de 3px (180 ms).
- **Card:** radio 8px, borde de vidrio, sin sombra ni brillo.
- **Label, Avatar:** ajustá colores y tipografía.
- Agregá lo que hoy se repite a mano y el sistema necesita como pieza compartida: **`Tabs`** (riel con el tubo de 2px bajo la pestaña activa, Tilt Neon 17px) y un **`SegmentedControl`** o equivalente si hay patrones tipo "Semana / Lista". Usalos donde hoy hay pestañas o segmentos armados a mano (buscalos: settings, agenda, conversaciones, Instagram, reportes…).
- Actualizá `button.test.tsx` y cualquier test que dependa de clases viejas.

## 3. Shell

Con las capturas como referencia:

- Marco de 12px (8px en móvil) con dos paneles de vidrio redondeados (16px): **barra lateral de 236 px** y **panel de trabajo**. Borde de panel = hairline de vidrio + reflejo de 1px arriba, sin sombra.
- **Marca:** "AloStudio" en Neonderthaw 36px con brillo cobalto arriba de la barra lateral (reemplaza el cuadradito amarillo con "A").
- **Filas de navegación:** ícono + etiqueta en Tilt Neon 16px, 44px de alto, radio 10px. En noche: filas apagadas con el "zumbido" tenue, hover enciende el texto, la fila actual con el contorno de tubo encendido e ignición al llegar (*Humming Sidebar Exception*). En día, sin brillos. Mantené los grupos y entradas de `nav.ts` como están (incluida "Agenda").
- **Barra superior** dentro del panel de trabajo: el **cartel** de la página (Tilt Neon 34px, 24px en móvil, con su brillo; en día, cobalto plano) a la izquierda; a la derecha tema, notificaciones, selector de cuenta y menú de usuario.
- **Título de página:** creá `components/shell/page-header.tsx` (cartel + descripción opcional + acciones) y pasá a usarlo en las páginas que hoy arman su `h1` a mano, para que el título de cada sección sea el cartel. Hacelo de forma mecánica, sin rediseñar el contenido de cada página.
- **Móvil:** la barra lateral como cajón de altura completa que se abre desde la barra superior, como hoy.

## 4. Marca e íconos

- `app/icon.png` y `app/apple-icon.png` (convención de archivos de Next) desde `public/brand/`, más los íconos del manifest/PWA si los hay (hay un `public/sw.js`: revisá si existe un manifest).
- Ningún resto del amarillo: buscá `#fcd535`, `#f0b90b`, `252 213 53`, `240 185 11`, "Binance", "yellow" en `frontend/` y resolvé cada uno.

## 5. Barrido de pantallas

- Recorré las pantallas buscando estilos propios que choquen con el sistema (fondos o sombras fijas, brillos en cards, filas o modales, `text-white`/`bg-black` sueltos, tablas sin encabezado en mayúsculas de 11px). Ajustalas al sistema sin cambiar su estructura ni su comportamiento.
- Tablas: encabezado en el panel elevado, etiquetas de columna de 11px en mayúsculas con tracking, líneas de vidrio, `tabular-nums`.
- No toques los colores de marca de canales ni los colores que define el usuario en el Help Center.

## 6. Documentación

- Reescribí `frontend/DESIGN-SYSTEM.md` para el sistema neón: qué tokens y clases existen en este frontend, qué componentes usar y las reglas con nombre (*Lit-Means-Current*, *Electrode*, *Three Faces*, *Light-Not-Lift*, *Ignition*), apuntando a `docs/design-neon/DESIGN.md` como fuente. Que no quede ninguna mención al estilo Binance.

## Fuera de alcance

Recomponer el layout de pantallas (por ejemplo el Home con la órbita de canales, el calendario de publicaciones), pantallas nuevas, cambios de backend, textos o traducciones. Si algo de esto parece necesario, anotalo en **Estado**.

## Terminado cuando

- `npm run typecheck`, `npm run lint`, `npm test` y `npm run build` pasan.
- No queda amarillo ni "Binance" en `frontend/`.
- Noche y día siguen el `DESIGN.md`; la luz aparece solo en la marca, el cartel, la fila actual, la pestaña activa, la acción principal y el campo con foco.
- Capturas de `/login` en noche y día en `docs/design-neon/after/`.
- **Estado** completo.

## Estado

### Qué se hizo

1. **Tokens, superficies, radios y fuentes (`7287619`)**
   - Reescritos los tokens semánticos en `frontend/app/globals.css` para `:root` (día) y `.dark` (noche) siguiendo `docs/design-neon/DESIGN.md` y `docs/design-neon/neon-tokens.reference.scss`, más todos los tokens `--neon-*` (`--neon-core`, `--neon-core-hover`, `--neon-halo`, `--neon-halo-far`, `--neon-edge`, `--neon-lit-text`, `--neon-unlit-text`, `--neon-hum`, `--neon-glass`, `--neon-glass-highlight`, `--neon-field`, `--neon-hover-glass`, `--neon-focused-glass`, `--neon-electrode`, `--neon-ambient-spill`, `--neon-settings`).
   - Clases de superficie neón (`.glass-panel`, `.neon-wordmark`, `.neon-sign`, `.neon-nav-row`, `.neon-tab`, `.neon-btn-primary`, `.neon-btn-simple`, `.neon-btn-ai`, `.neon-field-input`, `.neon-toggle`, `.neon-table`, `@keyframes neon-ignite`) con soporte completo de día y `@media (prefers-reduced-motion: reduce)`.
   - Mapeo en `frontend/tailwind.config.ts`: colores neón (`bg-field`, `text-lit`, `text-unlit`, `bg-focused`, `bg-hover-glass`, `text-electrode`, `border-glass`, `bg-settings`), radios (`panel: 16px`, `control: 10px`, `lg: 8px`, `sm: 4px`), sombra `menu` para menús flotantes y tipografías `Geologica` (`font-sans`, `font-numeric` con `tabular-nums`), `Tilt_Neon` (`font-display`) y `Neonderthaw` (`font-script`) cargadas con `next/font/google` en `frontend/app/layout.tsx` (eliminado `Inter`).

2. **Componentes base en `frontend/components/ui/` (`d481340`)**
   - `Button` (`primary` tubo cobalto encendido, `secondary` panel elevado sin luz, `simple` vidrio translúcido, `ai` naranja electrodo `--neon-electrode`, `destructive`, `ghost`; 40px / radio 10px y área táctil mínima de 44px en móvil) + tests en `button.test.tsx`.
   - `Input`, `Textarea` y nuevo `Select` compartido sobre campo hundido (`--neon-field`, borde de vidrio de 1px, radio 10px, 44px de alto en inputs/selects, foco cobalto + anillo de 3px en 180ms).
   - `Card` (radio 8px, borde de vidrio, cero sombras/halos), `Label`, `Avatar`.
   - `Tabs` / `NavTabs` (riel de 1px con tubo cobalto de 2px bajo la pestaña activa, `Tilt Neon` 17px) + tests en `tabs.test.tsx`, y `SegmentedControl` compartido para selectores de vista/estado.

3. **Shell y `PageHeader` (`cc23a9d`)**
   - `DashboardShell` con marco de 12px (`8px` en móvil) y dos paneles `.glass-panel` redondeados (`16px`, sin sombras): barra lateral de `236px` (y cajón de altura completa en móvil) + panel de trabajo.
   - Wordmark `AloStudio` en `Neonderthaw` 36px (`.neon-wordmark`) arriba de la barra lateral; filas de navegación en `SidebarNav` con `Tilt Neon` 16px, 44px de alto, radio 10px y *Humming Sidebar Exception* en noche (en día sin brillo), manteniendo intactas todas las rutas y grupos de `nav.ts`.
   - Barra superior del panel de trabajo con el cartel de la sección (`.neon-sign`, `Tilt Neon` 34px / 24px móvil) a la izquierda y `ThemeToggle`, `NotificationBell`, `AccountSwitcher` y `AgentMenu` a la derecha.
   - Nuevo `PageHeader` (`frontend/components/shell/page-header.tsx` + `page-header.test.tsx`) sincronizado con el cartel de `DashboardShell` sin duplicar `<h1>`.

4. **Marca, íconos PWA y pantallas públicas de autenticación (`c9d6e47`)**
   - `frontend/app/icon.png` (512×512) y `frontend/app/apple-icon.png` (180×180) desde `frontend/public/brand/`, `frontend/app/manifest.ts` apuntando a `/brand/alostudio-icon-{192,512}.png` con colores `#060912` / `#4d7cff`, y actualización del ícono por defecto en `frontend/public/sw.js`.
   - Rediseño neón de `frontend/app/(auth)/layout.tsx`, `/login`, `/forgot-password`, `/reset-password`, `/confirm` y `/auth/sso`.
   - Eliminación total de referencias a `#fcd535`, `#f0b90b`, `252 213 53`, `240 185 11`, `"Binance"` y `"yellow"` en `frontend/`.

5. **Barrido completo de pantallas y ajustes (`f078bbc`, `bd6a4aa`)**
   - Aplicados `PageHeader`, `Tabs` / `NavTabs`, `SegmentedControl`, `Select`, `.neon-table` (encabezados en panel elevado de 11px uppercase con tracking, divisores de vidrio y `tabular-nums`) y `.neon-toggle` en `overview`, `agenda`, `conversations`, `contacts`, `products`, `campaigns`, `reports`, `instagram`, `help-center`, `notifications`, `accounts`, `system` y las 20 subpantallas de `/accounts/[accountId]/settings/*`.
   - Eliminados `rounded-xl`, `rounded-2xl`, `shadow-sm/md/lg/xl`, `shadow-glow`, `bg-gradient-*`, `text-black` y `bg-black` residuales en componentes, preservando los colores de marca de canales externos y los colores configurables por el usuario en Help Center / plantillas de email.

6. **Documentación y capturas (`f7a1562`)**
   - Reescrito `frontend/DESIGN-SYSTEM.md` documentando el sistema "The Hand-Bent Neon Room", tokens, superficies, componentes y reglas con nombre, apuntando a `docs/design-neon/DESIGN.md`.
   - Capturas de `/login` a `1440×900` en noche y día guardadas en `docs/design-neon/after/login-night.png` y `docs/design-neon/after/login-day.png`.

### Qué quedó pendiente / fuera de alcance

- **Recomposición de layouts (fuera de alcance según el plan):**
  - El Home actual conserva las métricas y accesos operativos de AloStudio (no la órbita de canales sociales de `screens/home.png`).
  - La sección `/agenda` mantiene su calendario semanal/lista de turnos (no el calendario mensual de publicaciones sociales de `screens/calendar.png`, que vendrá al migrar publicación).
  - `/accounts/[accountId]/settings/*` conserva su subnavegación lateral de 20 secciones (estilizada con `bg-focused text-lit` sin halos según *Don't add halos to the settings sub-nav*), ya que no entra en una barra horizontal única de 6 pestañas como en `screens/settings.png`.
- **Revisión con backend activo:**
  - Las pantallas autenticadas bajo `/accounts/[accountId]/*` y la suite E2E (`npm run test:e2e`) requieren el backend Python y PostgreSQL corriendo; tal como indica la sección *Entorno*, quedan listas para revisión con el backend levantado.

### Verificaciones ejecutadas (todas sobre `frontend/` completo)

#### 1. `npm run typecheck` (ejecutado sobre todo `frontend/`)

```text
> alostudio-frontend@0.1.0 typecheck
> tsc --noEmit
```
*(Código de salida: `0`)*

#### 2. `npm run lint` (ejecutado sobre todo `frontend/`)

```text
> alostudio-frontend@0.1.0 lint
> next lint

`next lint` is deprecated and will be removed in Next.js 16.
For new projects, use create-next-app to choose your preferred linter.
For existing projects, migrate to the ESLint CLI:
npx @next/codemod@canary next-lint-to-eslint-cli .

✔ No ESLint warnings or errors
```
*(Código de salida: `0`)*

#### 3. `npm test` (ejecutado sobre todo `frontend/`)

```text
> alostudio-frontend@0.1.0 test
> vitest run

 RUN  v2.1.9 C:/Users/Zeek/Desktop/AloStudio-design/frontend
 ...
 Test Files  70 passed (70)
      Tests  290 passed (290)
   Start at  02:17:09
   Duration  12.31s (transform 5.77s, setup 16.72s, collect 54.96s, tests 25.21s, environment 124.37s, prepare 18.81s)
```
*(Código de salida: `0` — las 70 suites y 290 pruebas unitarias/componentes de `frontend/` pasaron completas)*

#### 4. `npm run build` (ejecutado sobre todo `frontend/`)

```text
> alostudio-frontend@0.1.0 build
> next build

   ▲ Next.js 15.5.18

   Creating an optimized production build ...
 ✓ Compiled successfully in 13.4s
   Linting and checking validity of types ...
   Collecting page data ...
   Generating static pages (0/24) ...
 ✓ Generating static pages (24/24)
   Finalizing page optimization ...
   Collecting build traces ...

Route (app)                                                           Size  First Load JS
┌ ƒ /                                                                175 B         102 kB
├ ○ /_not-found                                                      175 B         102 kB
├ ƒ /accounts                                                        175 B         102 kB
├ ƒ /accounts/[accountId]                                          2.89 kB         129 kB
...
├ ○ /apple-icon.png                                                    0 B            0 B
├ ○ /auth/sso                                                      3.94 kB         116 kB
├ ƒ /confirm                                                       2.39 kB         115 kB
├ ○ /eliminacion-de-datos                                            197 B         106 kB
├ ○ /forgot-password                                               2.55 kB         138 kB
├ ○ /icon.png                                                          0 B            0 B
├ ○ /login                                                            3 kB         138 kB
├ ○ /manifest.webmanifest                                            175 B         102 kB
├ ○ /privacidad                                                      197 B         106 kB
├ ƒ /reset-password                                                2.59 kB         138 kB
├ ○ /robots.txt                                                      175 B         102 kB
└ ○ /terminos                                                        197 B         106 kB
+ First Load JS shared by all                                       102 kB

ƒ Middleware                                                       34.3 kB
```
*(Código de salida: `0`)*

#### 5. Búsqueda de restos amarillos / Binance en `frontend/`

```text
$ git grep -i -E "fcd535|f0b90b|252[ _]213[ _]53|240[ _]185[ _]11|binance|yellow" -- frontend/
(sin coincidencias — código de salida: 1)
```
