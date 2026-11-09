"""Prueba en vivo de los servicios externos: python -m cdd.check_external

Comprueba la clave y el modelo de Gemini (una llamada mínima, coste de fracciones de céntimo) y los repositorios de
las dimensiones 1 y 2 (OpenAlex, Crossref, Europe PMC, arXiv). No guarda nada en la base de datos.
"""
from __future__ import annotations

import sys
import time

from .config import get_settings, mask_secret
from .connectors.registry import CONNECTORS
from .providers.gemini import GeminiClient, GeminiError


def main() -> int:
    s = get_settings()
    ok = True
    print("\nCIENCIA Y DIOS · servicios externos\n")
    print("Gemini (LLM)")
    if not s.gemini_api_key:
        print("  ⚠ CDD_GEMINI_API_KEY vacío: los agentes funcionarán sin LLM (modo determinista)")
    else:
        print(f"  · clave {mask_secret(s.gemini_api_key)} · modelo {s.gemini_model}")
        t = time.monotonic()
        try:
            r = GeminiClient().generate_json(
                "Responde solo con el JSON pedido.", "Devuelve {\"estado\": \"ok\"}.",
                {"type": "OBJECT", "properties": {"estado": {"type": "STRING"}}, "required": ["estado"]}, max_output_tokens=256)
            print(f"  ✓ responde ({r.model}) en {time.monotonic() - t:.1f}s · {r.input_tokens}+{r.output_tokens} tokens · "
                  f"{r.usd:.6f} USD · respuesta {r.data}")
        except GeminiError as e:
            ok = False
            print(f"  ✗ {e}")
    print("\nRepositorios (dimensiones 1 y 2)")
    for name in CONNECTORS:
        if name not in s.connectors_enabled:
            print(f"  · {name}: desactivado (CDD_CONNECTORS_ENABLED)")
            continue
        t = time.monotonic()
        rep = CONNECTORS[name]().search("dead sea scrolls radiocarbon dating", limit=2)
        if rep.ok:
            print(f"  ✓ {name}: {len(rep.candidates)} obras en {time.monotonic() - t:.1f}s")
        else:
            hint = ""
            if name == "openalex" and rep.error and ("429" in rep.error or "401" in rep.error):
                hint = " → configura CDD_OPENALEX_API_KEY (gratuita en https://openalex.org); sin ella no hay dimensión 2 (expertos)"
            print(f"  ✗ {name}: {rep.error[:160] if rep.error else ''}{hint}")
    if "openalex" in s.connectors_enabled and not s.openalex_api_key:
        print("  ⚠ Sin CDD_OPENALEX_API_KEY: OpenAlex usa un cupo diario compartido por IP y puede rechazar peticiones")
    print("\nResultado: " + ("listo." if ok else "hay errores (✗) que revisar."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
