"""F9 · Recursos de EmbeddingGemma 2 en CPU (VPS de develop).

Mide RAM, tiempo de carga y latencia por texto y por lote. Correrlo dentro
de un límite de memoria y con prioridad baja, como correría en producción:

    systemd-run --user --scope -p MemoryMax=2500M -p CPUWeight=20 \
        nice -n 10 python embeddinggemma_recursos.py datos.json \
        [float32|bfloat16] [texto|completo] [hilos]

Imprime una línea JSON con los resultados.
"""

from __future__ import annotations

import json
import os
import resource
import statistics
import sys
import time
from pathlib import Path

import psutil
import torch

MODEL = "google/embeddinggemma-2"


def rss_mb() -> float:
    return psutil.Process(os.getpid()).memory_info().rss / 2**20


def peak_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def main(
    datos_path: str,
    dtype_name: str = "float32",
    modo: str = "texto",
    hilos: str = "6",
) -> None:
    torch.set_num_threads(int(hilos))
    datos = json.loads(Path(datos_path).read_text(encoding="utf-8"))
    base = rss_mb()

    t0 = time.perf_counter()
    from sentence_transformers import SentenceTransformer

    dtype = {"float32": torch.float32, "bfloat16": torch.bfloat16}[dtype_name]
    config_kwargs = (
        {"vision_config": None, "audio_config": None} if modo == "texto" else {}
    )
    model = SentenceTransformer(
        MODEL,
        device="cpu",
        model_kwargs={"torch_dtype": dtype},
        config_kwargs=config_kwargs,
    )
    carga_s = time.perf_counter() - t0
    params_m = sum(p.numel() for p in model.parameters()) / 1e6
    rss_carga = rss_mb()

    sts = model.prompts["SentenceSimilarity"]
    q = model.prompts["SearchQuery"]
    comments = [c["text"] for c in datos["comments"]]
    queries = [x["text"] for x in datos["queries"]]
    docs = [f"title: {a['title']} | text: {a['content']}" for a in datos["articles"]]

    model.encode(sts + "calentamiento")  # primera llamada, fuera de la medida

    def lat_ms(texts: list[str], prefix: str) -> list[float]:
        out = []
        for t in texts:
            s = time.perf_counter()
            model.encode(prefix + t, normalize_embeddings=True)
            out.append((time.perf_counter() - s) * 1000)
        return out

    lc = lat_ms(comments[:60], sts)
    lq = lat_ms(queries[:40], q)
    ld = lat_ms(docs, "")

    s = time.perf_counter()
    model.encode([sts + t for t in comments], batch_size=32, normalize_embeddings=True)
    lote_s = time.perf_counter() - s

    def p(xs: list[float], k: float) -> float:
        return round(statistics.quantiles(xs, n=100)[int(k) - 1], 1)

    print(
        json.dumps(
            {
                "dtype": dtype_name,
                "modo": modo,
                "hilos": int(hilos),
                "parametros_M": round(params_m),
                "carga_s": round(carga_s, 1),
                "rss_base_mb": round(base),
                "rss_tras_carga_mb": round(rss_carga),
                "rss_pico_mb": round(peak_mb()),
                "comentario_ms_p50": p(lc, 50),
                "comentario_ms_p95": p(lc, 95),
                "consulta_ms_p50": p(lq, 50),
                "consulta_ms_p95": p(lq, 95),
                "articulo_ms_p50": p(ld, 50),
                "articulo_ms_max": round(max(ld), 1),
                "lote_textos": len(comments),
                "lote_s": round(lote_s, 2),
                "lote_textos_por_s": round(len(comments) / lote_s, 1),
            }
        )
    )


if __name__ == "__main__":
    main(*sys.argv[1:])
