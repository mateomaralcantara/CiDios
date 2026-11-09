"""Cliente de Google Gemini (API REST generateContent) con salida JSON estructurada y control de coste.

La clave se envía en la cabecera x-goog-api-key y nunca se registra ni se muestra completa.
Documentación: https://ai.google.dev/api/generate-content
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..config import get_settings
from ..net import http_client


class GeminiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status, self.retryable = status, retryable


@dataclass
class LLMResult:
    data: Any
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    usd: float = 0.0
    finish_reason: str = ""
    latency_s: float = 0.0
    meta: dict = field(default_factory=dict)

    def usage(self) -> dict[str, Any]:
        return {"provider": "gemini", "model": self.model, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens, "usd": round(self.usd, 6)}


def configured() -> bool:
    return bool(get_settings().gemini_api_key)


def estimate_usd(input_chars: int, max_output_tokens: int) -> float:
    s = get_settings()
    return (input_chars / 4) / 1e6 * s.gemini_input_usd_per_mtok + max_output_tokens / 1e6 * s.gemini_output_usd_per_mtok


def _friendly(status: int, body: str) -> GeminiError:
    try:
        msg = json.loads(body).get("error", {}).get("message", body)
    except ValueError:
        msg = body
    msg = (msg or "")[:300]
    if status == 400 and "API key" in msg:
        return GeminiError(f"Clave de Gemini no válida (CDD_GEMINI_API_KEY). {msg}", status)
    if status in (401, 403):
        return GeminiError(f"Gemini rechazó la clave o la API no está habilitada para ese proyecto. {msg}", status)
    if status == 404:
        return GeminiError(f"El modelo «{get_settings().gemini_model}» no existe o no está disponible para tu clave "
                           f"(CDD_GEMINI_MODEL). {msg}", status)
    if status == 429:
        return GeminiError(f"Cuota o límite de peticiones de Gemini alcanzado. {msg}", status, retryable=True)
    if status >= 500:
        return GeminiError(f"Gemini no disponible temporalmente ({status}). {msg}", status, retryable=True)
    return GeminiError(f"Error de Gemini ({status}): {msg}", status)


class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        s = get_settings()
        self.api_key = api_key or s.gemini_api_key
        self.model = model or s.gemini_model
        if not self.api_key:
            raise GeminiError("Falta CDD_GEMINI_API_KEY en apps/api/.env")

    def generate_json(self, system: str, prompt: str, schema: dict, *, max_output_tokens: int = 4096,
                      temperature: float = 0.1, attempts: int = 3) -> LLMResult:
        s = get_settings()
        gen: dict[str, Any] = {"temperature": temperature, "maxOutputTokens": max_output_tokens,
                               "responseMimeType": "application/json", "responseSchema": schema}
        if s.gemini_thinking_budget is not None:
            gen["thinkingConfig"] = {"thinkingBudget": s.gemini_thinking_budget}
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": gen}
        url = f"{s.gemini_base_url}/models/{self.model}:generateContent"
        last: GeminiError | None = None
        with http_client(timeout=s.gemini_timeout_s, headers={"x-goog-api-key": self.api_key}) as client:
            for i in range(attempts):
                t0 = time.monotonic()
                try:
                    r = client.post(url, json=body)
                except httpx.HTTPError as e:
                    last = GeminiError(f"No se pudo contactar con Gemini: {type(e).__name__}", retryable=True)
                else:
                    if r.status_code == 200:
                        return self._parse(r.json(), time.monotonic() - t0)
                    last = _friendly(r.status_code, r.text)
                if not last.retryable or i == attempts - 1:
                    break
                time.sleep(min(20, 2 ** (i + 1)))
        raise last or GeminiError("Error desconocido de Gemini")

    def _parse(self, payload: dict, latency: float) -> LLMResult:
        s = get_settings()
        fb = payload.get("promptFeedback") or {}
        if fb.get("blockReason"):
            raise GeminiError(f"Gemini bloqueó la petición: {fb['blockReason']}")
        cands = payload.get("candidates") or []
        if not cands:
            raise GeminiError("Gemini no devolvió ninguna respuesta")
        c = cands[0]
        text = "".join(p.get("text", "") for p in (c.get("content") or {}).get("parts", []) if not p.get("thought"))
        um = payload.get("usageMetadata") or {}
        tin = int(um.get("promptTokenCount", 0))
        tout = int(um.get("candidatesTokenCount", 0)) + int(um.get("thoughtsTokenCount", 0))
        usd = tin / 1e6 * s.gemini_input_usd_per_mtok + tout / 1e6 * s.gemini_output_usd_per_mtok
        finish = c.get("finishReason", "")
        try:
            data = json.loads(text)
        except ValueError as e:
            raise GeminiError(f"Gemini devolvió JSON no válido (finishReason={finish}). Prueba a subir maxOutputTokens.") from e
        return LLMResult(data=data, text=text, model=payload.get("modelVersion") or self.model, input_tokens=tin,
                         output_tokens=tout, usd=usd, finish_reason=finish, latency_s=round(latency, 2))
