"""Measure the help assistant against ``casos_ayuda.json``.

    LOCAL_LLM_URL=http://127.0.0.1:8092 python ops/llm/evaluar_ayuda.py [etiqueta]

Runs the real ``service.ask`` (same prompt, grammar and checks as the app)
against the model behind ``LOCAL_LLM_URL``. A case passes when the
assistant knows (or not) as expected and, when it knows, points to one of
the expected screens and says the expected words. Writes
``ops/llm/resultados/<etiqueta>.json``.
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.core.local_llm import LocalLlmError  # noqa: E402
from app.domains.help_assistant import service  # noqa: E402

CASES = pathlib.Path(__file__).with_name("casos_ayuda.json")


def judge(case: dict, out: dict) -> list[str]:
    """What went wrong, empty when the case passes."""
    problems = []
    expected_known = case.get("known", True)
    if out["known"] != expected_known:
        return ["sabía" if out["known"] else "no sabía"]
    if not expected_known:
        return []
    key = (out.get("screen") or {}).get("key") or ("ninguna" if not out.get("note") else "admin")
    if key not in case["screens"] and not (key == "admin" and case["screens"]):
        problems.append(f"pantalla {key}")
    for word in case["words"]:
        if word.lower() not in out["answer"].lower():
            problems.append(f"falta '{word}'")
    return problems


async def main() -> None:
    label = sys.argv[1] if len(sys.argv) > 1 else "modelo"
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    started = time.monotonic()
    await service.warm()
    print(f"calentado en {time.monotonic() - started:.0f} s", flush=True)
    results, passed = [], 0
    for case in cases:
        try:
            out = await service.ask(case["q"], page=case.get("page"), is_admin=True)
        except LocalLlmError as exc:
            out = {"known": None, "answer": f"ERROR {exc}", "seconds": None}
        problems = judge(case, out) if out["known"] is not None else ["error"]
        passed += not problems
        results.append({**case, "out": out, "problems": problems})
        mark = "OK " if not problems else "MAL"
        print(
            f"{mark} {out.get('seconds')}s | {case['q'][:60]} | {', '.join(problems)}", flush=True
        )
    seconds = [r["out"]["seconds"] for r in results if r["out"].get("seconds")]
    summary = {
        "label": label,
        "passed": passed,
        "total": len(cases),
        "avg_seconds": round(sum(seconds) / len(seconds), 1) if seconds else None,
        "max_seconds": max(seconds) if seconds else None,
    }
    print(json.dumps(summary, ensure_ascii=False))
    out_dir = pathlib.Path(__file__).with_name("resultados")
    out_dir.mkdir(exist_ok=True)
    (out_dir / f"{label}.json").write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    asyncio.run(main())
