import json
import logging
import socket
from typing import Any
from urllib import error, request

from backend.core.config import settings

logger = logging.getLogger(__name__)


class OllamaServiceError(RuntimeError):
    pass


class OllamaService:
    def chat_text(
        self,
        user_message: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
    ) -> str:
        payload = self._build_chat_payload(
            user_message=user_message,
            system=system,
            temperature=temperature,
        )
        response_payload = self._post_chat(payload)
        message = response_payload.get("message") or {}
        result = str(message.get("content", "")).strip()
        if not result:
            raise OllamaServiceError("Ollama chat returned an empty response.")
        return result

    def generate_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        format: str | dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> str:
        payload = self._generate_payload(
            prompt=prompt,
            system=system,
            format=format,
            temperature=temperature,
        )
        response_payload = self._post_generate(payload)
        result = str(response_payload.get("response", "")).strip()
        if not result:
            raise OllamaServiceError("Ollama returned an empty response.")
        return result

    def generate_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = 0.1,
    ) -> dict[str, Any]:
        raw_text = self.generate_text(
            prompt,
            system=system,
            format="json",
            temperature=temperature,
        )
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.exception("Ollama JSON parse error | body=%s", raw_text)
            raise OllamaServiceError("Ollama returned invalid JSON.") from exc
        if not isinstance(parsed, dict):
            raise OllamaServiceError("Ollama JSON response must be an object.")
        return parsed

    def _generate_payload(
        self,
        *,
        prompt: str,
        system: str | None,
        format: str | dict[str, Any] | None,
        temperature: float | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": settings.ollama_model,
            "prompt": prompt.strip(),
            "stream": False,
        }
        if system:
            payload["system"] = system.strip()
        if format is not None:
            payload["format"] = format
        if temperature is not None:
            payload["options"] = {
                "temperature": temperature,
            }
        return payload

    def _build_chat_payload(
        self,
        *,
        user_message: str,
        system: str | None,
        temperature: float | None,
    ) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if system:
            messages.append(
                {
                    "role": "system",
                    "content": system.strip(),
                }
            )
        messages.append(
            {
                "role": "user",
                "content": user_message.strip(),
            }
        )

        payload: dict[str, Any] = {
            "model": settings.ollama_model,
            "messages": messages,
            "stream": False,
        }
        if temperature is not None:
            payload["options"] = {
                "temperature": temperature,
            }
        return payload

    def _post_generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        req = request.Request(
            url=f"{settings.ollama_base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=settings.ollama_timeout_seconds) as response:
                raw_response = response.read().decode("utf-8")
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            logger.exception(
                "Ollama HTTP error | model=%s status=%s body=%s",
                settings.ollama_model,
                exc.code,
                error_body,
            )
            raise OllamaServiceError(
                f"Ollama request failed with status {exc.code}."
            ) from exc
        except (error.URLError, socket.timeout) as exc:
            logger.exception(
                "Ollama connection error | model=%s error=%s",
                settings.ollama_model,
                exc,
            )
            raise OllamaServiceError("Could not connect to Ollama.") from exc

        try:
            response_payload = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            logger.exception(
                "Ollama transport JSON parse error | model=%s body=%s",
                settings.ollama_model,
                raw_response,
            )
            raise OllamaServiceError("Ollama transport response was invalid JSON.") from exc

        return response_payload

    def _post_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        req = request.Request(
            url=f"{settings.ollama_base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=settings.ollama_timeout_seconds) as response:
                raw_response = response.read().decode("utf-8")
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            logger.exception(
                "Ollama chat HTTP error | model=%s status=%s body=%s",
                settings.ollama_model,
                exc.code,
                error_body,
            )
            raise OllamaServiceError(
                f"Ollama chat request failed with status {exc.code}."
            ) from exc
        except (error.URLError, socket.timeout) as exc:
            logger.exception(
                "Ollama chat connection error | model=%s error=%s",
                settings.ollama_model,
                exc,
            )
            raise OllamaServiceError("Could not connect to Ollama chat.") from exc

        try:
            response_payload = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            logger.exception(
                "Ollama chat transport JSON parse error | model=%s body=%s",
                settings.ollama_model,
                raw_response,
            )
            raise OllamaServiceError("Ollama chat transport response was invalid JSON.") from exc

        return response_payload
