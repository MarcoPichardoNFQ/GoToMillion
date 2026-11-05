from pathlib import Path

script = r'''from __future__ import annotations

import ast
import json
import os
import random
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "autonomous_engineer.py"

NEW_PROVIDER = r'''
class GeminiProvider:
    """
    Proveedor Gemini con reintentos controlados por este agente.

    Desactiva los reintentos internos del SDK para evitar multiplicación
    de intentos. Respeta RetryInfo.retryDelay cuando Google lo proporciona.
    """

    MAX_ATTEMPTS_PER_MODEL = 2
    DEFAULT_FALLBACK_MODEL = "gemini-3.6-flash"
    DEFAULT_MAX_INPUT_TOKENS = 100_000
    MAX_SINGLE_RETRY_WAIT = 120.0
    MAX_TOTAL_RETRY_WAIT = 150.0

    def __init__(self, model: str, fallback_model: str | None = None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "No se encontró GEMINI_API_KEY en las variables de entorno."
            )

        self.primary_model = self._normalize_model_name(model)
        self.fallback_model = self._normalize_model_name(
            fallback_model
            or os.getenv(
                "GEMINI_FALLBACK_MODEL",
                self.DEFAULT_FALLBACK_MODEL
            )
        )
        self.max_input_tokens = self._positive_int_env(
            "GEMINI_MAX_INPUT_TOKENS",
            self.DEFAULT_MAX_INPUT_TOKENS
        )
        self.max_total_retry_wait = self._positive_float_env(
            "GEMINI_MAX_TOTAL_RETRY_WAIT",
            self.MAX_TOTAL_RETRY_WAIT
        )

        # El SDK reintenta por defecto errores 429/5xx. Se desactivan
        # esos reintentos para que RetryInfo y el presupuesto global
        # sean gestionados en un único lugar.
        try:
            http_options = types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1)
            )
            self.client = genai.Client(
                api_key=api_key,
                http_options=http_options
            )
        except (AttributeError, TypeError) as error:
            raise RuntimeError(
                "La versión instalada de google-genai no permite configurar "
                "HttpRetryOptions(attempts=1). Actualiza con "
                "'python -m pip install --upgrade google-genai'. "
                f"Detalle: {error}"
            ) from error

        self.model = self.primary_model
        self.active_model = None
        self.available_models = self._discover_models()
        self.models_to_try = self._build_model_chain()

    @staticmethod
    def _positive_int_env(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            value = int(raw)
        except ValueError as error:
            raise ValueError(f"{name} debe ser un entero positivo.") from error
        if value <= 0:
            raise ValueError(f"{name} debe ser un entero positivo.")
        return value

    @staticmethod
    def _positive_float_env(name: str, default: float) -> float:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            value = float(raw)
        except ValueError as error:
            raise ValueError(f"{name} debe ser un número positivo.") from error
        if value <= 0:
            raise ValueError(f"{name} debe ser un número positivo.")
        return value

    @staticmethod
    def _normalize_model_name(name: str) -> str:
        value = str(name or "").strip()
        if value.startswith("models/"):
            value = value.split("/", 1)[1]
        if not value:
            raise ValueError("El nombre del modelo Gemini está vacío.")
        return value

    @staticmethod
    def _model_field(model_info, field_name):
        if isinstance(model_info, dict):
            return model_info.get(field_name)
        return getattr(model_info, field_name, None)

    def _discover_models(self) -> set[str] | None:
        try:
            discovered = set()
            for model_info in self.client.models.list():
                name = self._model_field(model_info, "name")
                if not name:
                    continue

                actions = self._model_field(model_info, "supported_actions")
                if actions is not None:
                    normalized_actions = {
                        str(action).lower() for action in actions
                    }
                    if "generatecontent" not in normalized_actions:
                        continue

                discovered.add(self._normalize_model_name(name))

            print("Modelos Gemini visibles para la API key:", len(discovered))
            return discovered

        except Exception as error:
            print(
                "ADVERTENCIA: no fue posible consultar el catálogo de modelos. "
                "Se comprobarán los modelos mediante la solicitud real."
            )
            print(f"Detalle del catálogo: {type(error).__name__}: {error}")
            return None

    def _build_model_chain(self) -> list[str]:
        candidates = []
        for candidate in (self.primary_model, self.fallback_model):
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        if self.available_models is None:
            print(
                "Disponibilidad no verificada previamente; "
                "se intentarán los modelos configurados."
            )
            return candidates

        available = [m for m in candidates if m in self.available_models]
        for model in candidates:
            if model not in self.available_models:
                print(f"Modelo no listado para esta API key; se omitirá: {model}")

        if not available:
            raise RuntimeError(
                "Ninguno de los modelos configurados aparece disponible "
                f"con generateContent: {candidates}"
            )

        print("Cadena de modelos habilitados:", " -> ".join(available))
        return available

    @staticmethod
    def _error_code(error) -> int | None:
        for candidate in (
            getattr(error, "code", None),
            getattr(error, "status_code", None),
        ):
            try:
                if candidate is not None:
                    return int(candidate)
            except (TypeError, ValueError):
                pass
        return None

    @staticmethod
    def _error_text(error) -> str:
        pieces = [str(error)]
        for attribute in ("message", "details", "response"):
            value = getattr(error, attribute, None)
            if value is not None:
                pieces.append(str(value))
        return " ".join(pieces).lower()

    @classmethod
    def _classify_error(cls, error) -> str:
        """
        Categorías:
        - rate_limited: 429 de ventana/minuto; reintentar respetando RetryInfo.
        - model_quota: cuota diaria/de modelo; no reintentar mismo modelo.
        - unavailable: 408/5xx/timeout/red; reintento acotado.
        - model_not_found: pasar al fallback.
        - permanent: autenticación, permisos, facturación, petición inválida.
        """
        code = cls._error_code(error)
        message = cls._error_text(error)

        if code == 404 or "model not found" in message or "not_found" in message:
            return "model_not_found"

        if code == 429 or "resource_exhausted" in message:
            billing_markers = (
                "billing", "prepay", "spend cap", "payment required",
                "insufficient credit", "billing account"
            )
            if any(marker in message for marker in billing_markers):
                return "permanent"

            daily_markers = (
                "perday", "per_day", "per day", "daily limit",
                "requests per day", "per-day"
            )
            if any(marker in message for marker in daily_markers):
                return "model_quota"

            rate_markers = (
                "per minute", "per_minute", "tokens per minute",
                "token_count", "requestsperminute", "requests per minute",
                "ratelimit", "rate limit", "quota exceeded"
            )
            if any(marker in message for marker in rate_markers):
                return "rate_limited"

            # 429 sin detalle: se trata como limitación temporal,
            # pero el tiempo de espera se acota y no se asume que sea TPM.
            return "rate_limited"

        if (
            code in {408, 500, 502, 503, 504}
            or any(marker in message for marker in (
                "unavailable", "deadline_exceeded", "timed out",
                "timeout", "connection reset", "internal server error",
                "bad gateway", "gateway timeout"
            ))
        ):
            return "unavailable"

        return "permanent"

    @classmethod
    def _retry_after_seconds(cls, error) -> float | None:
        message = cls._error_text(error)

        # Google puede incluir RetryInfo como retryDelay: '51s'.
        patterns = (
            r"""retryDelay['"]?\s*:\s*['"]?(\d+(?:\.\d+)?)s""",
            r"""retry\s+in\s+(\d+(?:\.\d+)?)\s*s(?:econds?)?""",
            r"""retry\s+after\s+(\d+(?:\.\d+)?)\s*s(?:econds?)?""",
        )
        for pattern in patterns:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                try:
                    return max(0.0, float(match.group(1)))
                except ValueError:
                    pass

        # Algunas versiones del SDK exponen RetryInfo en atributos.
        details = getattr(error, "details", None)
        if isinstance(details, (list, tuple)):
            for item in details:
                if isinstance(item, dict):
                    retry_info = item.get("retryDelay")
                    if isinstance(retry_info, str):
                        match = re.fullmatch(
                            r"\s*(\d+(?:\.\d+)?)s\s*", retry_info
                        )
                        if match:
                            return float(match.group(1))
        return None

    def _count_input_tokens(
        self,
        model: str,
        system_instruction: str,
        prompt: str
    ) -> tuple[int, str]:
        # Se cuenta la concatenación de ambos textos para no subestimar
        # el system instruction. La cifra es conservadora frente al envío.
        combined = (
            "SYSTEM INSTRUCTION:\n"
            + system_instruction
            + "\n\nUSER PROMPT:\n"
            + prompt
        )

        try:
            result = self.client.models.count_tokens(
                model=model,
                contents=combined
            )
            total = getattr(result, "total_tokens", None)
            if total is not None:
                return int(total), "Gemini count_tokens"
        except Exception as error:
            print(
                "ADVERTENCIA: count_tokens no estuvo disponible; "
                "se utilizará una estimación conservadora. "
                f"{type(error).__name__}: {error}"
            )

        # Estimación local de respaldo: 1 token por cada 3 caracteres.
        # No reemplaza al tokenizer del modelo, por eso se etiqueta.
        estimate = (len(combined) + 2) // 3
        return estimate, "estimación local conservadora (3 caracteres/token)"

    def _validate_input_budget(
        self,
        model: str,
        system_instruction: str,
        prompt: str
    ) -> None:
        token_count, method = self._count_input_tokens(
            model, system_instruction, prompt
        )
        print(
            f"Tokens de entrada estimados/contados: {token_count:,} "
            f"({method}). Límite configurado: {self.max_input_tokens:,}."
        )
        if token_count > self.max_input_tokens:
            raise RuntimeError(
                "Contexto demasiado grande: "
                f"{token_count:,} tokens supera el límite configurado de "
                f"{self.max_input_tokens:,}. No se envió la solicitud. "
                "Ajusta GEMINI_MAX_INPUT_TOKENS conscientemente o reduce "
                "el alcance del inventario; no se truncó silenciosamente "
                "ningún archivo."
            )

    def _generate_with_model(
        self,
        model: str,
        system_instruction: str,
        prompt: str,
        schema: dict,
        temperature: float,
        retry_budget: dict
    ) -> dict:
        last_error = None

        for attempt in range(self.MAX_ATTEMPTS_PER_MODEL):
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=temperature,
                        max_output_tokens=60000,
                        response_mime_type="application/json",
                        response_json_schema=schema
                    )
                )
            except Exception as error:
                last_error = error
                category = self._classify_error(error)

                if category not in {"rate_limited", "unavailable"}:
                    raise

                if attempt + 1 >= self.MAX_ATTEMPTS_PER_MODEL:
                    break

                retry_after = self._retry_after_seconds(error)
                if retry_after is None:
                    retry_after = min(2 ** (attempt + 1), 15)
                    retry_after += random.uniform(0.0, min(1.0, retry_after * 0.2))

                if retry_after > self.MAX_SINGLE_RETRY_WAIT:
                    print(
                        f"Google solicita esperar {retry_after:.1f}s; "
                        f"supera el máximo por intento "
                        f"({self.MAX_SINGLE_RETRY_WAIT:.0f}s). "
                        "Se pasará al siguiente modelo sin reintentar este."
                    )
                    break

                remaining_budget = (
                    self.max_total_retry_wait - retry_budget["waited"]
                )
                if retry_after > remaining_budget:
                    print(
                        "Se agotaría el presupuesto global de espera. "
                        "No se realizará otro reintento."
                    )
                    break

                retry_budget["waited"] += retry_after
                print(
                    f"Modelo {model}: error {self._error_code(error) or category}. "
                    f"Intento {attempt + 1}/{self.MAX_ATTEMPTS_PER_MODEL}. "
                    f"Espera indicada: {retry_after:.1f}s."
                )
                time.sleep(retry_after)
                continue

            response_text = getattr(response, "text", None)
            if not response_text:
                raise RuntimeError(
                    f"Gemini devolvió una respuesta vacía con {model}."
                )

            if len(response_text.encode("utf-8")) > MAX_RESPONSE_BYTES:
                raise RuntimeError("La respuesta excede el límite de tamaño.")

            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as error:
                raise RuntimeError(
                    f"Gemini devolvió JSON inválido con {model}: {error}"
                ) from error

            if not isinstance(result, dict):
                raise RuntimeError("La respuesta JSON no es un objeto.")

            return result

        if last_error is not None:
            raise last_error

        raise RuntimeError(
            f"No se obtuvo respuesta válida del modelo {model}."
        )

    def generate_json(
        self,
        system_instruction: str,
        prompt: str,
        schema: dict,
        temperature: float = 0.1
    ) -> dict:
        self._validate_input_budget(
            self.models_to_try[0],
            system_instruction,
            prompt
        )

        errors = []
        retry_budget = {"waited": 0.0}

        for index, model in enumerate(self.models_to_try):
            if index > 0:
                print()
                print(
                    f"FALLBACK: cambiando de {self.primary_model} a {model}."
                )
                print(
                    "Se conserva el mismo prompt, system instruction "
                    "y esquema JSON."
                )
            else:
                print(f"Solicitando respuesta a Gemini: {model}")

            try:
                result = self._generate_with_model(
                    model=model,
                    system_instruction=system_instruction,
                    prompt=prompt,
                    schema=schema,
                    temperature=temperature,
                    retry_budget=retry_budget
                )
                self.active_model = model
                self.model = model
                print(f"Respuesta recibida correctamente de: {model}")
                return result

            except Exception as error:
                category = self._classify_error(error)
                errors.append(
                    f"{model} [{category}]: {type(error).__name__}: {error}"
                )

                can_try_fallback = index + 1 < len(self.models_to_try)
                fallback_categories = {
                    "rate_limited", "unavailable",
                    "model_not_found", "model_quota"
                }

                if can_try_fallback and category in fallback_categories:
                    print(
                        f"El modelo {model} terminó con categoría "
                        f"{category}; se probará el siguiente modelo."
                    )
                    continue

                raise RuntimeError(
                    "Gemini no pudo completar la solicitud. "
                    f"Categoría del error: {category}.\n"
                    + "\n".join(errors)
                ) from error

        raise RuntimeError(
            "Todos los modelos configurados fallaron:\n"
            + "\n".join(errors)
        )

    def close(self) -> None:
        self.client.close()
'''


def fail(message: str) -> None:
    raise RuntimeError(message)


def find_global_class(source: str, class_name: str) -> ast.ClassDef:
    tree = ast.parse(source)
    matches = [
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    if len(matches) != 1:
        fail(
            f"Se esperaba exactamente una clase global {class_name}; "
            f"se encontraron {len(matches)}."
        )
    return matches[0]


def replace_provider(source: str) -> str:
    node = find_global_class(source, "GeminiProvider")
    lines = source.splitlines(keepends=True)
    replacement = NEW_PROVIDER.strip("\n") + "\n"
    result = "".join(
        lines[:node.lineno - 1] + [replacement] + lines[node.end_lineno:]
    )

    tree = ast.parse(result)
    imports = {
        alias.name
        for item in tree.body
        if isinstance(item, ast.Import)
        for alias in item.names
    }
    if "random" not in imports:
        marker = "import re\n"
        if marker not in result:
            fail("No se encontró 'import re' para insertar 'import random'.")
        result = result.replace(marker, marker + "import random\n", 1)

    ast.parse(result)
    compile(result, str(TARGET), "exec")
    return result


def atomic_write(path: Path, content: str) -> None:
    fd, temp_name = tempfile.mkstemp(
        prefix=".autonomous_engineer_",
        suffix=".tmp",
        dir=str(path.parent)
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def isolated_tests(source: str) -> None:
    class FakeError(Exception):
        def __init__(self, code, message):
            super().__init__(message)
            self.code = code

    class FakeModelInfo:
        def __init__(self, name, actions):
            self.name = name
            self.supported_actions = actions

    class FakeResponse:
        text = '{"ok": true}'

    class FakeModels:
        def __init__(self):
            self.calls = []
            self.token_count_calls = 0

        def list(self):
            return [
                FakeModelInfo("models/gemini-3.8-flash", ["generateContent"]),
                FakeModelInfo("models/gemini-3.6-flash", ["generateContent"]),
                FakeModelInfo("models/not-a-text-model", ["generateImage"]),
            ]

        def count_tokens(self, model, contents):
            self.token_count_calls += 1
            return type("Count", (), {"total_tokens": 500})()

        def generate_content(self, model, contents, config):
            self.calls.append(model)
            if model == "gemini-3.8-flash":
                raise FakeError(
                    429,
                    "RESOURCE_EXHAUSTED retryDelay: '7s' "
                    "GenerateContentInputTokensPerModelPerMinute"
                )
            return FakeResponse()

    class FakeClient:
        def __init__(self):
            self.models = FakeModels()
            self.closed = False

        def close(self):
            self.closed = True

    fake_client = FakeClient()

    class FakeGenAI:
        @staticmethod
        def Client(api_key, http_options):
            assert http_options["retry_options"]["attempts"] == 1
            return fake_client

    class FakeTypes:
        @staticmethod
        def HttpRetryOptions(**kwargs):
            return kwargs

        @staticmethod
        def HttpOptions(**kwargs):
            return kwargs

        @staticmethod
        def GenerateContentConfig(**kwargs):
            return kwargs

    class FakeTime:
        @staticmethod
        def sleep(seconds):
            assert seconds == 7.0

    class FakeRandom:
        @staticmethod
        def uniform(_a, _b):
            return 0.0

    node = find_global_class(source, "GeminiProvider")
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "os": os,
        "re": __import__("re"),
        "json": json,
        "time": FakeTime,
        "random": FakeRandom,
        "genai": FakeGenAI,
        "types": FakeTypes,
        "MAX_RESPONSE_BYTES": 5_000_000,
    }

    old_values = {
        key: os.environ.get(key)
        for key in ("GEMINI_API_KEY", "GEMINI_MAX_INPUT_TOKENS")
    }
    os.environ["GEMINI_API_KEY"] = "test-key"
    os.environ["GEMINI_MAX_INPUT_TOKENS"] = "1000"

    try:
        exec(compile(module, "<isolated-provider-test>", "exec"), namespace)
        provider = namespace["GeminiProvider"](
            "gemini-3.8-flash",
            "gemini-3.6-flash"
        )
        result = provider.generate_json(
            "system",
            "prompt",
            {"type": "OBJECT"},
            temperature=0.0
        )

        assert result == {"ok": True}
        assert provider.active_model == "gemini-3.6-flash"
        assert fake_client.models.calls == [
            "gemini-3.8-flash",
            "gemini-3.8-flash",
            "gemini-3.6-flash",
        ]
        assert fake_client.models.token_count_calls == 1
        assert "not-a-text-model" not in provider.models_to_try
        provider.close()
        assert fake_client.closed

        # Verifica que un 429 diario no se trate como un retry TPM.
        daily = FakeError(429, "Quota exceeded: requests per day limit")
        assert namespace["GeminiProvider"]._classify_error(daily) == "model_quota"

        # Verifica extracción del RetryInfo textual devuelto por Google.
        retry_error = FakeError(429, "RetryInfo retryDelay: '51s'")
        assert namespace["GeminiProvider"]._retry_after_seconds(retry_error) == 51.0

    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def main() -> int:
    if not TARGET.is_file():
        fail(
            f"No se encontró {TARGET.name}. Coloca este generador "
            "en la misma carpeta que autonomous_engineer.py."
        )

    original = TARGET.read_text(encoding="utf-8")
    ast.parse(original)

    updated = replace_provider(original)
    if updated == original:
        fail("El parche no produjo cambios; se cancela.")

    # Validación aislada antes de tocar el archivo.
    isolated_tests(updated)
    compile(updated, str(TARGET), "exec")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = TARGET.with_name(f"{TARGET.name}.{stamp}.bak")
    shutil.copy2(TARGET, backup)

    try:
        atomic_write(TARGET, updated)
        subprocess.run(
            [os.sys.executable, "-m", "py_compile", str(TARGET)],
            check=True,
            cwd=str(ROOT)
        )
    except Exception:
        shutil.copy2(backup, TARGET)
        raise

    print("=" * 72)
    print("ACTUALIZACIÓN DEL PROVEEDOR GEMINI COMPLETADA")
    print("=" * 72)
    print("Archivo:", TARGET)
    print("Backup:", backup)
    print("Pruebas aisladas: OK")
    print("AST / compile: OK")
    print("py_compile: OK")
    print()
    print("Configuración opcional mediante variables de entorno:")
    print("  GEMINI_MAX_INPUT_TOKENS=100000")
    print("  GEMINI_MAX_TOTAL_RETRY_WAIT=150")
    print("  GEMINI_FALLBACK_MODEL=gemini-3.6-flash")
    print()
    print(
        "El generador NO ejecutó el proyecto, NO ejecutó pruebas del "
        "Blackjack y NO envió contenido a Gemini."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {type(error).__name__}: {error}")
        raise SystemExit(1)
'''

# El script debe conservar el código Python como texto literal.
out = Path("/mnt/data/generador_gemini_resiliencia.py")
out.write_text(script, encoding="utf-8")
compile(script, str(out), "exec")
print(f"Generador creado y compilado: {out} ({out.stat().st_size:,} bytes)")
