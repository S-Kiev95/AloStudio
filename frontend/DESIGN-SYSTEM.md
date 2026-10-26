# AloStudio — Sistema de Diseño ("The Hand-Bent Neon Room")

Guía de implementación del sistema de diseño de AloStudio en `frontend/`.
La fuente de verdad normativa es [`docs/design-neon/DESIGN.md`](../docs/design-neon/DESIGN.md).

---

## 1. Concepto y dirección visual

El espacio de trabajo es una sala oscura de vidrio cobalto curvado a mano (*The Hand-Bent Neon Room*).
Todas las superficies son paneles de vidrio apagado (tonos azul marino escalonados con borde hairline de `1px` y reflejo superior, nunca levantados con sombras). La corriente eléctrica solo circula por aquello que orienta o recibe acción directa:

- La marca `AloStudio` arriba de la barra lateral.
- El cartel de la página en la barra superior.
- La fila activa de la navegación principal.
- El tubo de `2px` bajo la pestaña abierta.
- El botón de acción principal (`primary`).
- El campo con foco mientras se escribe en él.

Existe una versión diurna (`:root`, modo claro) sobre fondo blanco frío donde los paneles mantienen su geometría de vidrio sin brillo exterior y el cartel pasa a cobalto plano. El modo nocturno (`.dark`, tema por defecto mediante `next-themes`) enciende los halos sobre el fondo marino con derrame ambiental arriba a la izquierda.

---

## 2. Reglas con nombre

1. **The Lit-Means-Current Rule:** la luz indica únicamente dónde estás, sobre qué actuás o dónde estás escribiendo (marca, cartel, fila activa del menú principal, tubo de pestaña activa, botón primario y campo con foco). Filas seleccionadas, conmutadores (`SegmentedControl`), toggles, filtros y la subnavegación de Ajustes expresan selección con `bg-focused` y `text-lit`, nunca con halo.
2. **The Humming Sidebar Exception:** solo en la barra lateral principal (`.neon-nav`, `.neon-nav-lit`) y en modo noche, las filas apagadas mantienen un zumbido tenue (`--neon-unlit-text` + `--neon-hum`), el hover sube a `--neon-lit-text` con halo y la fila activa queda incandescente dentro de su contorno `.lit-tube` con ignición al llegar. En modo día desaparece todo brillo.
3. **The Electrode Rule:** el naranja electrodo (`--neon-electrode`, `text-electrode`, `<Button variant="ai">`) está reservado exclusivamente para acciones de inteligencia artificial o agentes autónomos. Nunca se usa para advertencias (`--warning`), insignias decorativas ni estados generales.
4. **The Token-First Rule:** el color llega a los componentes mediante variables CSS (`--neon-*` y tokens semánticos) mapeadas en `tailwind.config.ts` y las clases de superficie en `app/globals.css`. Se preservan únicamente los colores de marca de canales externos (WhatsApp, Instagram, Telegram, etc.) y los colores configurables por el usuario en el Help Center o plantillas de correo.
5. **The Three Faces Rule:**
   - **Tilt Neon** (`--font-display`, `font-display`): nombra lugares — carteles de página (`34px` desktop / `24px` móvil), filas de navegación (`16px`) y pestañas (`17px`). Nunca en cuerpo de texto, botones ni celdas de datos.
   - **Geologica** (`--font-sans`, `font-sans`, pesos `300–700`, `latin` + `latin-ext`): todo lo que se lee o se ingresa (títulos internos, formularios, tablas, botones, etiquetas).
   - **Neonderthaw** (`--font-script`, `font-script`, `36px`): exclusivamente para el wordmark `AloStudio` en la barra lateral y cabeceras públicas de autenticación.
6. **The Counting Rule:** todas las tablas, métricas y contadores usan números tabulares (`font-variant-numeric: tabular-nums`, `tabular-nums` / `font-numeric`) para alinear importes, horas y cantidades en columna.
7. **The Light-Not-Lift Rule:** un resplandor significa "está encendido", nunca "flota". Cards, filas, listas y modales no llevan halo ni `drop-shadow`; solo menús desplegables y popovers usan `shadow-menu` (`--menu-shadow`).
8. **The Ignition Rule:** un estado encendido prende una sola vez en `360ms` (`cubic-bezier(0.16, 1, 0.3, 1)`), y las transiciones entre estados toman `220ms` (`180ms` en campos). Jamás hay parpadeos ni animaciones en bucle. Con `prefers-reduced-motion: reduce` toda ignición y transición de luz se desactiva.

---

## 3. Tokens y utilidades Tailwind

Definidos en [`app/globals.css`](app/globals.css) (`:root` día y `.dark` noche) y expuestos en [`tailwind.config.ts`](tailwind.config.ts). Ambos temas cumplen contraste WCAG AA.

### Tokens del mundo neón (`--neon-*`)

| Variable CSS | Día (`:root`) | Noche (`.dark`) | Utilidad Tailwind | Uso |
|---|---|---|---|---|
| `--neon-core` | `#2f5bf0` | `#3d6bff` | `bg-neon`, `text-neon`, `border-neon`, `accent-neon` | Núcleo de tubo cobalto, botón primario, borde en foco, perilla activa |
| `--neon-core-hover` | `#1f47d6` | `#5a82ff` | `bg-neon-hover` | Hover del botón primario |
| `--neon-lit-text` | `#1a3bb8` | `#dbe4ff` | `text-lit` | Texto encendido o seleccionado |
| `--neon-unlit-text` | `#4f5b7c` | `#9eb0e6` | `text-unlit-text` | Filas inactivas de la barra lateral |
| `--neon-electrode` | `#e5512a` | `#ff6a3d` | `bg-electrode`, `text-electrode`, `border-electrode` | Acciones de IA (`variant="ai"`) |
| `--neon-glass` | `#d6dcef` | `#1c2644` | `border-glass`, `divide-glass` | Hairlines de `1px` en paneles, cards, tablas, campos y riel de pestañas |
| `--neon-field` | `#f7f9fe` | `#070b16` | `bg-field` | Pozo hundido de inputs, textareas, selects y conmutadores |
| `--neon-hover-glass` | `#f3f5fb` | `#111834` | `bg-hover-glass` | Hover de filas y controles tranquilos |
| `--neon-focused-glass` | `#e6ecff` | `#101a3d` | `bg-focused`, `bg-focused-glass` | Selección sin halo (filas activas, subnav, segmentos, track de toggle encendido) |
| `--neon-button-simple` | `#e9edf7` | `rgba(24, 33, 61, 0.55)` | `bg-btn-simple` | Botones utilitarios tranquilos (`variant="simple"`) |
| `--neon-settings` | `#f5f7fc` | `#131a30` | `bg-settings-surface` | Superficie secundaria de configuración |
| `--neon-backdrop` | `#0b1533` | `#01030a` | `bg-backdrop` | Velo detrás de modales y cajón móvil |
| `--neon-table-text-focused` | `#2f5bf0` | `#7fa0ff` | `text-table-focused` | Acento textual en celdas focalizadas |

### Tokens semánticos

| Variable CSS | Día (`:root`) | Noche (`.dark`) | Utilidad Tailwind | Equivalencia |
|---|---|---|---|---|
| `--bg` | `#eef1f8` | `#060912` | `bg-bg` | Suelo de la sala + derrame ambiental (`--canvas-accent`) |
| `--surface` | `#ffffff` | `#0b1020` | `bg-surface` | Panel principal / cards |
| `--surface-2` | `#f3f5fb` | `#0f1528` | `bg-surface-2` | Panel elevado, encabezado de tabla, botón secundario |
| `--surface-3` | `#e6ecff` | `#101a3d` | `bg-surface-3` | Equivalente a `--neon-focused-glass` |
| `--fg` | `#0c1124` | `#e7ecff` | `text-fg` | Texto primario |
| `--fg-muted` | `#5f6987` | `#8d97b8` | `text-fg-muted` | Texto secundario, etiquetas inactivas |
| `--border` | `#e3e7f3` | `#1c2644` | `border-border` | Borde estándar |
| `--border-strong` | `#d3d9ea` | `#2a3660` | `border-border-strong` | Separador reforzado |
| `--primary` / `--primary-fg` | `#2f5bf0` / `#ffffff` | `#3d6bff` / `#ffffff` | `bg-primary`, `text-primary-fg` | Cobalto primario con texto blanco |
| `--success` | `#0d7a52` | `#34d399` | `text-success`, `bg-success` | Estado positivo / publicado / en línea |
| `--warning` | `#9a5206` | `#f5b841` | `text-warning`, `bg-warning` | Estado pendiente / advertencia ámbar (nunca naranja electrodo) |
| `--danger` / `--danger-solid` | `#cc2444` / `#c41e3d` | `#ff6b85` / `#c92542` | `text-danger`, `bg-danger-solid` | Error textual y relleno destructivo AA con blanco |
| `--info` | `#2f5bf0` | `#7fa0ff` | `text-info` | Enlaces e indicadores informativos |

### Clases de superficie (`@layer components` en `app/globals.css`)

- `.glass-panel`: borde interior `1px` `--neon-glass` + reflejo superior `1px` `--neon-glass-highlight`, sin sombra exterior. Usado en los dos paneles del shell y tarjetas de autenticación.
- `.neon-wordmark`: Neonderthaw `36px` con brillo cobalto en noche y cobalto plano en día.
- `.neon-sign`: cartel de página en Tilt Neon con resplandor en noche y cobalto plano en día.
- `.neon-nav` / `.neon-nav-lit`: filas apagadas con zumbido y fila activa encendida en la barra lateral principal.
- `.lit-tube` / `.lit-tube-ignite`: contorno de tubo cobalto encendido + animación única de `360ms`.
- `.lit-tube-solid`: cuerpo sólido de tubo encendido para `<Button variant="primary">`.
- `.neon-tab` / `.neon-tab-active`: pestaña sobre riel con barra luminosa de `2px` e inset horizontal de `14px`.
- `.glass-field`: pozo `--neon-field` con borde `--neon-glass` que al recibir foco conmuta a `--neon-core` y anillo `3px` `--neon-halo-far` en `180ms`.

---

## 4. Geometría, radios y sombras

- **Radios:**
  - `rounded-sm` (`4px`): chips e insignias compactas.
  - `rounded-md` (`8px`): cards, tablas y subnavegación de Ajustes.
  - `rounded-control` (`10px`): botones, filas de navegación principal, inputs, textareas, selects y grupos segmentados.
  - `rounded-panel` (`16px`): los dos paneles principales del shell (barra lateral y panel de trabajo).
  - `rounded-pill` (`100px`): toggles tipo pastilla.
- **Sombras:**
  - `shadow-sm` → `none` (las cards y contenedores nunca flotan).
  - `shadow-menu` (`shadow-md` / `shadow-lg`) → caída oscura suave exclusiva para menús desplegables y popovers.

---

## 5. Componentes compartidos

### `components/ui/`

- **[`Button`](components/ui/button.tsx):** `40px` de alto (`rounded-control`), área táctil mínima de `44px` (`min-h-11` en móvil). Variantes:
  - `primary` (por defecto): `.lit-tube-solid`, texto blanco. Si el consumidor pasa un `bg-*` propio, desactiva automáticamente `.lit-tube-solid` para no mezclar brillo cobalto con fondos ajenos.
  - `secondary`: `bg-surface-2`, borde `border-glass`, sin luz.
  - `simple`: `bg-btn-simple` translúcido con `border-glass`, sin luz.
  - `ghost`: transparente con hover `bg-hover-glass`.
  - `destructive`: `bg-danger-solid` con texto blanco, sin halo cobalto.
  - `ai`: naranja electrodo (`bg-electrode text-white`), exclusivo para acciones de IA.
- **[`Input`](components/ui/input.tsx), [`Textarea`](components/ui/textarea.tsx), [`Select`](components/ui/select.tsx) (`selectClassName`):** campos hundidos `.glass-field` (`44px` de alto en tamaño `md`, `rounded-control`, texto Geologica `14px`).
- **[`Card`](components/ui/card.tsx):** `rounded-md` (`8px`), `border-glass`, `bg-surface`, padding interno de `20px`, sin sombra ni resplandor.
- **[`Label`](components/ui/label.tsx) y [`Avatar`](components/ui/avatar.tsx):** etiquetas Geologica `12px` `font-medium`; avatares circulares sobre `bg-focused text-lit` con `border-glass`.
- **[`Tabs`](components/ui/tabs.tsx) y `NavTabs`:** riel inferior `border-glass` con pestañas en Tilt Neon `17px` (`px-[14px] py-[10px]`) y tubo activo `.neon-tab-active`.
- **[`SegmentedControl`](components/ui/segmented-control.tsx):** selector compacto sin luz sobre `bg-field` con opción activa `bg-focused text-lit` (`aria-pressed`), para vistas (`Semana / Lista`), rangos (`7d / 30d / 90d`) y filtros rápidos.

### `components/shell/`

- **[`DashboardShell`](components/shell/dashboard-shell.tsx):** marco exterior de `12px` (`8px` en móvil) con barra lateral `.glass-panel` de `236px` a la izquierda (wordmark `.neon-wordmark` + [`SidebarNav`](components/shell/sidebar-nav.tsx)) y panel de trabajo `.glass-panel` a la derecha con barra superior (`80px` desktop / `64px` móvil: cartel `.neon-sign` `<h1>` a la izquierda; tema, notificaciones, cuenta y menú de agente a la derecha). En móvil la barra lateral abre como cajón de altura completa.
- **[`PageHeader`](components/shell/page-header.tsx):** sincroniza el título de la sección con el cartel `.neon-sign` del topbar y renderiza la fila opcional de migas de pan (`eyebrow`), descripción secundaria y acciones principales de la pantalla. En las subpáginas de `/settings/*`, el cartel permanece en `Ajustes` y cada subsección encabeza su panel con `<h2>`.

### Tablas y Toggles

- **Tablas:** contenedor `overflow-hidden rounded-md border border-glass bg-surface`, `<thead className="bg-surface-2">` con `th` en `11px` mayúsculas y tracking `0.08em` (aplicado globalmente en `app/globals.css`), filas con `border-t border-glass` y `hover:bg-hover-glass`, cifras alineadas con `tabular-nums`.
- **Toggles (`role="switch"`):** pastilla `rounded-pill border border-glass`; apagado `bg-field` con perilla `bg-fg-muted`; encendido `bg-focused` con perilla `bg-neon` (el riel nunca brilla).

---

## 6. Accesibilidad y convenciones Next.js

- Anillo `:focus-visible` global de `2px` en `--neon-core` con `2px` de offset; nunca eliminar outlines sin reemplazo visible.
- Objetivos táctiles `>= 44x44px`; botones de solo ícono siempre con `aria-label` descriptivo; íconos SVG de `lucide-react` (sin emojis como íconos).
- `prefers-reduced-motion: reduce` desactiva animaciones de ignición y transiciones de brillo/sombra.
- Server Components por defecto; `'use client'` solo en hojas interactivas; fuentes autoalojadas una sola vez mediante `next/font/google` en [`app/layout.tsx`](app/layout.tsx).
