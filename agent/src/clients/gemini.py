import json
import time

import structlog
from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from agent.src.config import settings
from agent.src.exceptions import GeminiError
from agent.src.utils.retry import retry_network

log = structlog.get_logger(__name__)


class GeminiClient:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self._model_pro = settings.GEMINI_MODEL_PRO
        self._model_flash = settings.GEMINI_MODEL_FLASH

    def generate_json_pro(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        try:
            return self._generate_json(self._model_pro, prompt, schema)
        except GeminiError:
            raise
        except Exception as e:
            raise GeminiError(f"Failed after retries: {e}") from e

    def generate_json_flash(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        try:
            return self._generate_json(self._model_flash, prompt, schema)
        except GeminiError:
            raise
        except Exception as e:
            raise GeminiError(f"Failed after retries: {e}") from e

    def generate_text_flash(self, prompt: str) -> str:
        try:
            return self._generate_text(prompt)
        except GeminiError:
            raise
        except Exception as e:
            raise GeminiError(f"Failed after retries: {e}") from e

    @retry_network(extra_exceptions=(ValidationError, json.JSONDecodeError))
    def _generate_json(
        self, model: str, prompt: str, schema: type[BaseModel]
    ) -> BaseModel:
        start = time.time()
        try:
            response = self._client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    http_options=types.HttpOptions(timeout=30000),
                ),
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            log.warning(
                "gemini_call_failed",
                model=model,
                latency_ms=latency_ms,
                schema=schema.__name__,
                error=str(e),
            )
            raise GeminiError(f"Gemini API call failed: {e}") from e

        latency_ms = int((time.time() - start) * 1000)

        if response.parsed is not None:
            log.info(
                "gemini_call_success",
                model=model,
                latency_ms=latency_ms,
                schema=schema.__name__,
            )
            return response.parsed

        # Fallback: manual parsing if SDK didn't auto-parse
        data = json.loads(response.text)
        result = schema.model_validate(data)
        log.info(
            "gemini_call_success",
            model=model,
            latency_ms=latency_ms,
            schema=schema.__name__,
            fallback_parse=True,
        )
        return result

    @retry_network()
    def _generate_text(self, prompt: str) -> str:
        start = time.time()
        try:
            response = self._client.models.generate_content(
                model=self._model_flash,
                contents=prompt,
                config=types.GenerateContentConfig(
                    http_options=types.HttpOptions(timeout=30000),
                ),
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            log.warning(
                "gemini_call_failed",
                model=self._model_flash,
                latency_ms=latency_ms,
                error=str(e),
            )
            raise GeminiError(f"Gemini API call failed: {e}") from e

        latency_ms = int((time.time() - start) * 1000)
        log.info(
            "gemini_call_success",
            model=self._model_flash,
            latency_ms=latency_ms,
        )
        return response.text


gemini = GeminiClient()
