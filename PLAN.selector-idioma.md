# PLAN — Selector de idioma y desplegables con el estilo de la página

Pedido del dueño (2026-11-24): en el login, el selector de idioma abre una lista
nativa del sistema (fondo blanco, resaltado celeste de Windows) que no acompaña
el estilo oscuro y de neón de la página.

Rama `feat/selector-idioma`, worktree `C:\Users\Zeek\Desktop\AloStudio-idioma`,
sale de `develop`. Lo hace Neon (Antigravity) y lo revisa Claude contra este
documento.

## Qué hay hoy

- `frontend/components/shell/language-switcher.tsx`: un `<select>` nativo dentro
  de un `<label>` con estilo de vidrio; se usa en `app/(auth)/layout.tsx` (login,
  recuperar contraseña). Las `<option>` tienen `bg-surface-2 text-fg`, pero
  Windows y Chrome dibujan la lista con sus propios colores.
- `frontend/components/settings/profile/language-card.tsx`: el mismo elegido en
  Ajustes → Mi perfil.
- `frontend/components/ui/select.tsx`: el `<Select>` base (nativo) que usan ~40
  pantallas. `globals.css` ya pone `color-scheme: light` / `dark` por tema.
- Guías de diseño: `frontend/DESIGN-SYSTEM.md` y `docs/design-neon/DESIGN.md`.

## Qué hacer

1. **Componente nuevo `components/ui/listbox.tsx`** (sin librerías nuevas): un
   desplegable propio con el estilo de la página (vidrio, borde `border-glass`,
   fondo de superficie, opción activa y con foco resaltadas con los tokens de
   neón, sombra y esquinas como los menús que ya existen). Patrón de accesibilidad
   WAI-ARIA «select-only combobox»: botón con `role="combobox"`,
   `aria-expanded`, `aria-controls`, `aria-activedescendant`; lista con
   `role="listbox"` y opciones `role="option"` con `aria-selected`.
   - Teclado: Enter/Espacio/↓ abre, ↑/↓/Inicio/Fin mueven, Enter elige, Esc
     cierra y devuelve el foco, escribir letras salta a la opción, Tab cierra.
   - Mouse y touch; cierra al hacer clic afuera.
   - Se posiciona debajo (o arriba si no entra) sin salirse de la pantalla y por
     encima de todo (portal o `z-index` correcto; ojo con `view-transition-name`
     que crea contexto de apilamiento, ver `.vt-page-over-bar` en `globals.css`).
   - Cada opción puede llevar `lang` (para los nombres de idioma).
   - Claro y oscuro con los tokens del tema; `prefers-reduced-motion` sin
     animación de apertura.
2. **Usarlo en `language-switcher.tsx` y en `language-card.tsx`**, con el mismo
   comportamiento de hoy (cambiar la cookie en el login; guardar en el perfil en
   Ajustes).
3. **Arreglo general para los `<select>` nativos** que quedan: que la lista que
   abre el sistema siga el tema. Asegurar `color-scheme` correcto en el
   `<select>` (y en `option`/`optgroup` fondo y texto con los tokens del tema)
   para que en modo oscuro no salga blanca. No reemplaces los ~40 `<Select>` por
   el listbox: solo anotá en **Estado** cuáles convendría migrar después.
4. **Pruebas** en vitest del listbox (abrir, teclado, elegir, Esc, clic afuera,
   atributos ARIA) y que el selector de idioma cambie el idioma.

## Reglas

- Trabajá **solo** en `C:\Users\Zeek\Desktop\AloStudio-idioma`. Solo frontend.
- Nada de `git push`, `ssh`, `.env*`, bases ni contenedores. Sin librerías nuevas.
- Sin modificadores de opacidad sobre colores del tema (`bg-primary/60`…): usá
  los tokens CSS.
- Textos nuevos (si hay) en los 7 idiomas (`frontend/lib/i18n/messages/*`).
- Commits chicos en español (`feat(ui): ...`, `fix(ui): ...`), terminados en
  `Co-Authored-By: Antigravity <noreply@google.com>`.
- Revisalo en el navegador (`npm run dev` en `frontend/`, el login no necesita
  backend) en claro y en oscuro, y dejá capturas en `docs/selector-idioma/`.
- Al final completá **Estado** con la salida real de `npm run typecheck`,
  `npm run lint` y `npm test` en `frontend/`.

## Estado

Completado en `feat/selector-idioma` (2026-11-24).

### Qué se hizo

1. **`frontend/components/ui/listbox.tsx`** (sin librerías nuevas):
   - Desplegable propio con patrón WAI-ARIA *select-only combobox* (`role="combobox"`, `aria-haspopup="listbox"`, `aria-expanded`, `aria-controls`, `aria-activedescendant`, lista `role="listbox"` y opciones `role="option"` con `aria-selected`, `aria-disabled` y `lang` opcional).
   - Teclado completo: `Enter`/`Espacio`/`↓`/`↑`/`Inicio`/`Fin` abren; `↑`/`↓`/`Inicio`/`Fin`/`RePág`/`AvPág` navegan saltando deshabilitadas; `Enter`/`Espacio` eligen y devuelven foco; `Esc` cierra devolviendo foco; `Tab` cierra; typeahead (normalizado sin acentos, con ciclado de inicial repetida) salta a la opción.
   - Mouse y touch; cierra al hacer clic o tocar fuera.
   - Portal hacia `document.body` (o al `<dialog>` ancestro si está dentro de un modal) con `position: fixed` y `z-[60]` para superar `overflow-hidden` y contextos `view-transition-name` (`.vt-topbar` / `.vt-page-over-bar`). Se ubica debajo o voltea arriba si no entra, con clamping horizontal a los bordes de la pantalla y recálculo en `resize`/`scroll`.
   - Estilo de vidrio neón (`.glass-dialog`, `border-glass`, `shadow-menu`, opción activa con `bg-focused text-lit ring-1 ring-inset ring-neon` y marca `Check` en `text-neon`, sin modificadores de opacidad sobre colores del tema). Animación de apertura con `animatePopoverIn` respetando `prefers-reduced-motion: reduce`.
2. **`frontend/components/shell/language-switcher.tsx` y `frontend/components/settings/profile/language-card.tsx`**:
   - Migrados a `<Listbox>` manteniendo el mismo comportamiento: `LanguageSwitcher` en login/recuperación escribe la cookie `alo_locale` y hace `router.refresh()`; `LanguageCard` en Ajustes → Mi perfil cambia el idioma al instante y persiste `ui_settings.locale` en el perfil.
3. **Arreglo general para `<select>` nativos (`frontend/app/globals.css`)**:
   - Reglas base para `select` (`color-scheme: light` / `.dark select { color-scheme: dark }`), `select option, select optgroup` (`background-color: var(--surface-2); color: var(--fg)`), `:disabled` (`var(--fg-muted)`) y `:checked` (`var(--neon-focused-glass)` / `var(--neon-lit-text)`).
4. **Pruebas en Vitest**:
   - `frontend/components/ui/listbox.test.tsx` (6 pruebas: atributos ARIA y `lang`, apertura y navegación por teclado, typeahead, `Esc`/`Tab`/clic afuera, opciones deshabilitadas y selección por clic, volteo hacia arriba).
   - `frontend/components/shell/language-switcher.test.tsx` (2 pruebas: listado de los 7 idiomas con `lang`, cambio por clic y por teclado).
   - `frontend/components/settings/profile/profile-view.test.tsx` (actualizada la prueba de idioma para operar el `combobox`).

### Candidatos recomendados para migrar a `<Listbox>` más adelante

Los ~40 `<select>` / `<Select>` restantes ya heredan `color-scheme` y colores de `option`/`optgroup` del tema. Conviene priorizar la migración a `<Listbox>` en las pantallas de mayor visibilidad y uso diario:

- **Prioridad alta (uso constante en la vista principal):**
  - `components/conversations/conversation-actions.tsx` (asignar agente, equipo, estado y prioridad).
  - `components/conversations/conversation-list.tsx` y `components/conversations/conversation-filters.tsx` (filtros y orden de la bandeja).
  - `components/conversations/message-composer.tsx` (selector del compositor).
  - `components/contacts/contact-filters.tsx` (filtros de contactos).
  - `components/crm/opportunities-view.tsx` (selector de embudo/etapa).
- **Prioridad media (requieren añadir soporte de grupos al `<Listbox>` para reemplazar `<optgroup>`):**
  - `components/lifecycle/contact-stage.tsx` (etapa del contacto).
  - `components/settings/settings-sidebar.tsx` (selector móvil de secciones de Ajustes).
  - `components/reports/reports-view.tsx` y `components/publications/analytics-view.tsx` (filtros de métricas/canales).
- **Dejar nativos por ahora:** formularios de configuración poco frecuentes (automatizaciones, macros, webhooks, horarios, atributos personalizados, plantillas de correo, formularios de campañas/WhatsApp/Instagram), donde el arreglo de `color-scheme` y `option`/`optgroup` ya evita la lista blanca en modo oscuro.

### Verificación en navegador y capturas

Verificado en Chrome contra `npm run dev` en `/login` (sin backend):
- Modo oscuro con desplegable abierto y alineado dentro del viewport: `docs/selector-idioma/login-dark-open.png`
- Cambio a inglés por teclado (`ArrowDown` + `Enter`, cookie `alo_locale=en`, título actualizado a *Sign in*): `docs/selector-idioma/login-dark-en-open.png`
- Modo claro con desplegable abierto: `docs/selector-idioma/login-light-open.png`
- Vista móvil (`390×844`) en modo oscuro, por encima de la tarjeta y sin salirse de pantalla: `docs/selector-idioma/login-mobile-dark-open.png`

### Salida real de verificaciones (`frontend/`)

```text
> alostudio-frontend@0.1.0 typecheck
> tsc --noEmit
(exit code 0)

> alostudio-frontend@0.1.0 lint
> next lint
✔ No ESLint warnings or errors
(exit code 0)

> alostudio-frontend@0.1.0 test
> vitest run

 Test Files  130 passed (130)
      Tests  591 passed (591)
   Start at  14:56:12
   Duration  92.04s
(exit code 0)
```
