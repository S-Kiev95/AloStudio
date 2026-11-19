# IA local para la Ayuda

El botón Ayuda usa un modelo chico que corre en el servidor (llama.cpp).
`levantar.sh` lo levanta; `evaluar_ayuda.py` lo mide con los 30 casos de
`casos_ayuda.json` (dudas reales de agentes, más 6 que la ayuda no cubre).

## Mediciones (staging, limitado a 4 núcleos como la VPS de CTC, 2026-11-19)

| Ronda | Modelo | Correctas | Promedio | Máximo | Primera lectura |
|---|---|---|---|---|---|
| 1 | Qwen3 4B Instruct 2507 | 26/30 | 21 s | 39 s | 3 min |
| 2 | Qwen3 4B Instruct 2507 | 27/30 | 22 s | 47 s | 3 min |
| 2 | Qwen3 1.7B | 16/30 | 13 s | 21 s | 1,5 min |
| 3 | Qwen3 4B Instruct 2507 | 29/30 | 22 s | 41 s | 4 min |

- Entre rondas cambió la ayuda (separar usar y crear respuestas rápidas,
  Reportes a la izquierda, cómo se atiende una llamada) y los controles
  (flechas que no salen de un menú real, botones entre comillas que la
  ayuda no nombra).
- Qwen3 1.7B es más rápido pero dice que sabe cosas que AloStudio no hace
  (exportar a Excel, borrar la cuenta, verificación en dos pasos).
- Las 6 preguntas fuera de la ayuda las contesta "no lo encuentro" en unos
  8 segundos. En la ronda 3 el control frenó una respuesta inventada
  ("Enviar por correo").
- Leer cuesta ~12 tokens/s y escribir ~4 tokens/s: por eso la parte fija va
  primero y se reutiliza, y las respuestas son cortas.
- Memoria: ~4,5 GB con 8192 de contexto.
