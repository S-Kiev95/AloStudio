# Comparativa Antes y Después — `feat/neon-ux`

Capturas reales tomadas sobre la aplicación levantada en Next.js (`1440×900` escritorio y `390×844` celular, modo noche).

---

## 1. Login con agujero negro (`Anime.js v4` + Three.js GLSL + modelos 3D `.glb` reales)

### Antes (reposo del login)
![Login en reposo](./capturas/01-login-night.png)

### Después (secuencia real al iniciar sesión correctamente — `2,5 s`)

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
