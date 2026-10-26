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

_(lo completa el agente al terminar)_
