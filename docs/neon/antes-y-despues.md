# Comparativa Antes y Después — `feat/neon-ux`

Capturas reales tomadas sobre la aplicación levantada en Next.js (`1440×900` escritorio y `390×844` celular, modo noche).

---

## 1. Login con agujero negro (`Anime.js v4` + Three.js GLSL + modelos 3D `.glb` reales)

### Antes (reposo del login)
![Login en reposo](./capturas/01-login-night.png)

### Después (secuencia real al iniciar sesión correctamente — `5 s`)

#### 1) Fractura de los campos y grietas cobalto hacia el centro
![Login fractura real](./capturas/despues-login-bh-01-fractura.png)

#### 2) Esfera negra + disco de acreción azul cobalto + íconos 3D `.glb` estirados como chicle
![Login disco de acreción y chicle real](./capturas/despues-login-bh-02-chicle.png)

#### 3) Caída de la cámara dentro del agujero negro rumbo al Inicio
![Login caída de cámara real](./capturas/despues-login-bh-03-caida.png)

#### Vista en celular (`390×844`)
![Login agujero negro en celular](./capturas/despues-login-bh-mobile.png)

---

## 2. P0 #1 — Arreglo central de opacidad Tailwind (`<alpha-value>`)

### Cajón móvil (`bg-backdrop/80`)
- **Antes (`rgba(0, 0, 0, 0)` — fondo completamente descubierto):**

![Antes: cajón móvil sin oscurecer fondo](./capturas/14-mobile-drawer-backdrop.png)

- **Después (`rgba(1, 3, 10, 0.8)` — velo oscuro real + selector de cuenta y tema al pie):**

![Después: cajón móvil con velo oscuro real](./capturas/despues-01-drawer-backdrop.png)

---

## 3. P0 #2 — Barra superior en celular y popovers fijos

### Bandeja + Popover de Ayuda en celular (`390×844`)
- **Antes (cartel recortado a `B...` y popover de Ayuda en `x = -182px` fuera de pantalla):**

![Antes: Bandeja móvil con título B... y popover cortado](./capturas/06-bandeja-mobile-popover.png)

- **Después (cartel `Bandeja` entero sin corte de brillo y popover centrado en `x = 12px`):**

![Después: Bandeja móvil con título completo y popover centrado](./capturas/despues-03-bandeja-mobile-popover.png)

---

## 4. P0 #3 — Scroll horizontal en pestañas del CRM + Ajustes agrupado

### CRM Contactos en celular (`390×844`)
- **Antes (cartel `C...`, 6 pestañas apiladas en 3 filas con tubo flotando, badge `BLOQUEADO` sin fondo):**

![Antes: CRM móvil con tabs en 3 filas y badge sin fondo](./capturas/07-crm-contactos-mobile.png)

- **Después (cartel `Contactos` completo, 1 sola fila con scroll horizontal y badge `BLOQUEADO` con `rgba(255, 107, 133, 0.1)`):**

![Después: CRM móvil con tabs en 1 fila y badge con fondo](./capturas/despues-02-crm-contactos-mobile.png)

### Ajustes en celular (`390×844`)
- **Antes (cartel `Aj...`, 29 ítems en tira ciega de `3324px` sin mostrar el activo):**

![Antes: Ajustes móvil en tira horizontal ciega](./capturas/11-ajustes-mobile.png)

- **Después (cartel `Ajustes` completo y selector `<select>` con los 6 grupos temáticos mostrando el activo):**

![Después: Ajustes móvil con selector agrupado](./capturas/despues-04-ajustes-mobile.png)

### Ajustes en escritorio (`1440×900`)
- **Antes (25 ítems apilados en un solo grupo sin buscador):**

![Antes: Ajustes escritorio sin agrupar](./capturas/12-ajustes-desktop.png)

- **Después (buscador rápido + 6 grupos temáticos claros):**

![Después: Ajustes escritorio agrupado y con buscador](./capturas/despues-05-ajustes-desktop.png)

---

## 5. P1 — Inicio alineado a `DESIGN.md` + `ErrorState` sin ceros falsos

### Inicio en estado normal (`1440×900`)
- **Antes (doble `.neon-sign`, `.neon-nav` fuera de la sidebar, tarjetas estáticas):**

![Antes: Inicio con doble neon-sign y neon-nav](./capturas/03-inicio-night.png)

- **Después (un solo `.neon-sign` en el topbar, sin `.neon-nav` en tarjetas, 4 `LiveCard` interactivas hacia la Bandeja):**

![Después: Inicio alineado a DESIGN.md](./capturas/despues-p1-inicio-night.png)

### Inicio cuando fallan las APIs (`1440×900`)
- **Después (3 `ErrorState` con botón «Reintentar» y cero falsos `0`):**

![Después: Inicio con ErrorState y Reintentar](./capturas/despues-p1-inicio-error.png)

---

## 6. P1 — Agente IA con Electrode Orange (*The Electrode Rule*)

- **Antes (acento todo cobalto, sin distinción para acciones de IA):**

![Antes: Agente todo cobalto](./capturas/10-agente-night.png)

- **Después (badge `Sparkles` y botón de enviar `variant="ai"` en `--neon-electrode`):**

![Después: Agente con Electrode Orange](./capturas/despues-p1-agente-electrode.png)

---

## 7. P1 — `ErrorState` con «Reintentar» en Calendario y Oportunidades

### Calendario (`1440×900`)
- **Antes (texto rojo plano sin acción de recuperación):**

![Antes: Calendario error sin Reintentar](./capturas/13-calendario-night.png)

- **Después (`ErrorState` con botón «Reintentar»):**

![Después: Calendario con ErrorState y Reintentar](./capturas/despues-p1-calendario-error.png)

### Oportunidades (`1440×900`)
- **Antes (texto rojo plano sin acción de recuperación):**

![Antes: Oportunidades error sin Reintentar](./capturas/08-crm-oportunidades-night.png)

- **Después (`ErrorState` con botón «Reintentar»):**

![Después: Oportunidades con ErrorState y Reintentar](./capturas/despues-p1-oportunidades-error.png)

---

## 8. P1 — `ConfirmDialog` neón compartido + botones ≥ 44 px

- **Después (`ConfirmDialog` neón reemplazando `window.confirm()`, foco en Cancelar, cierre con `Escape`/clic afuera, y botones de ícono de `44×44 px` en Ajustes):**

![Después: ConfirmDialog neón sobre Ajustes Etiquetas](./capturas/despues-p1-confirm-dialog.png)

---

## 9. P1 — Módulo de WhatsApp en los 7 idiomas

- **Después (sección WhatsApp renderizada 100% en inglés con `alo_locale=en`, demostrando paridad en `es`, `en`, `pt`, `fr`, `de`, `ja`, `ko`):**

![Después: WhatsApp completamente traducido al inglés](./capturas/despues-p1-whatsapp-en.png)

---

## 10. P2 — Inicio personal/neutro, tarjetas «Ahora mismo» cliqueables y voz rioplatense pareja

- **Después (`Hola, Sofía` conectado a `useProfile()`, «Centro de ayuda» unificado en la barra lateral, acceso rápido «Bandeja», y las 4 tarjetas «Ahora mismo» con contadores animados Anime.js v4 que filtran directo en la Bandeja):**

![Después P2: Inicio con saludo personal, tarjetas cliqueables y Centro de ayuda](./capturas/despues-p2-inicio-desktop.png)

---

## 11. P2 — Filtros compactos en la Bandeja (`1440×900`)

- **Después (selectores de Canal y Bandeja lado a lado en una sola fila con grilla compacta y pills ajustados, liberando altura para la lista de chats):**

![Después P2: Bandeja con filtros compactos](./capturas/despues-p2-bandeja-filtros.png)

---

## 12. P2 — Geometría `rounded-md` y Kanban táctil en Oportunidades

### Escritorio (`1440×900`)
- **Después (columnas `rounded-md` según `DESIGN.md`, entrada escalonada Anime.js v4 y barra CRM con tubo cobalto deslizante):**

![Después P2: Oportunidades Kanban en escritorio](./capturas/despues-p2-oportunidades-kanban.png)

### Celular (`390×844`)
- **Después (selector táctil de etapa en el pie de cada tarjeta para mover oportunidades sin drag & drop):**

![Después P2: Oportunidades Kanban táctil en celular](./capturas/despues-p2-oportunidades-mobile.png)

---

## 13. P2 — Selector de idioma con contraste en Login

- **Después (`LanguageSwitcher` con borde `border-glass` y superficie translúcida `bg-surface/80 backdrop-blur-sm` legible sobre los logos 3D flotantes):**

![Después P2: Login con selector de idioma legible](./capturas/despues-p2-login-selector.png)

---

## 14. P3 — Microinteracciones con Anime.js v4 (Agente IA y popovers con mejor contraste)

### Agente IA en estado «Pensando…» (`1440×900`)
- **Después (3 puntos Electrode Orange animados con `stagger(120)` vía Anime.js v4, burbujas con entrada suave y respeto a `prefers-reduced-motion`):**

![Después P3: Agente IA pensando con puntos Electrode Orange](./capturas/despues-p3-agente-pensando.png)

### Popover de Ayuda animado + contraste limpio en metadatos (`1440×900`)
- **Después (popover de Ayuda con entrada `animatePopoverIn`, subtítulos de modo sin `opacity-80` lavado y barra lateral de Ajustes con texto legible):**

![Después P3: Popover de Ayuda abierto sobre Ajustes](./capturas/despues-p3-popover-ayuda.png)
