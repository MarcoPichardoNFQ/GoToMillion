
from __future__ import annotations

import ast
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "autonomous_engineer.py"
DEFAULT_FALLBACK_MODEL = "gemini-3.6-flash"

NEW_PROVIDER = r'''
class GeminiProvider:
    MAX_ATTEMPTS_PER_MODEL = 3
    FALLBACK_MODEL_DEFAULT = "gemini-3.6-flash"

    def __init__(self, model: str, fallback_model: str | None = None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "No se encontró GEMINI_API_KEY en las variables de entorno."
            )

        self.client = genai.Client(api_key=api_key)
        self.primary_model = self._normalize_model_name(model)
        self.fallback_model = self._normalize_model_name(
            fallback_model
            or os.getenv(
                "GEMINI_FALLBACK_MODEL",
                self.FALLBACK_MODEL_DEFAULT
            )
        )
        self.model = self.primary_model
        self.active_model = None
        self.available_models = self._discover_models()
        self.models_to_try = self._build_model_chain()

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

                actions = self._model_field(
                    model_info,
                    "supported_actions"
                )

                if actions is not None:
                    normalized_actions = {
                        str(action).lower()
                        for action in actions
                    }
                    if "generatecontent" not in normalized_actions:
                        continue

                discovered.add(self._normalize_model_name(name))

            print(
                "Modelos Gemini visibles para la API key:",
                len(discovered)
            )
            return discovered

        except Exception as error:
            print(
                "ADVERTENCIA: no fue posible consultar el catálogo "
                "de modelos. Se comprobarán los modelos mediante "
                "la solicitud real."
            )
            print(
                f"Detalle del catálogo: {type(error).__name__}: {error}"
            )
            return None

    def _build_model_chain(self) -> list[str]:
        candidates = []

        for candidate in (self.primary_model, self.fallback_model):
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        if self.available_models is None:
            print(
                "Disponibilidad no verificada previamente. "
                "Se intentarán los modelos configurados."
            )
            return candidates

        available = [
            model for model in candidates
            if model in self.available_models
        ]

        for model in candidates:
            if model not in self.available_models:
                print(
                    f"Modelo no listado para esta API key; se omitirá: {model}"
                )

        if not available:
            raise RuntimeError(
                "Ninguno de los modelos configurados aparece disponible "
                "con capacidad generateContent para esta API key. "
                f"Modelos configurados: {candidates}"
            )

        print("Cadena de modelos habilitados:", " -> ".join(available))
        return available

    @staticmethod
    def _error_code(error) -> int | None:
        code = getattr(error, "code", None)
        try:
            return int(code) if code is not None else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _is_transient_error(cls, error) -> bool:
        code = cls._error_code(error)
        message = str(error).upper()

        return (
            code in {408, 429, 500, 502, 503, 504}
            or any(
                marker in message
                for marker in (
                    "UNAVAILABLE",
                    "RESOURCE_EXHAUSTED",
                    "DEADLINE_EXCEEDED",
                    "INTERNAL SERVER ERROR",
                    "BAD GATEWAY",
                    "GATEWAY TIMEOUT",
                    "CONNECTION RESET",
                    "TIMED OUT",
                    "TIMEOUT",
                    "HTTP 503",
                    "HTTP 429",
                )
            )
        )

    @classmethod
    def _is_model_not_found(cls, error) -> bool:
        code = cls._error_code(error)
        message = str(error).upper()
        return (
            code == 404
            or "NOT_FOUND" in message
            or "MODEL NOT FOUND" in message
        )

    def _generate_with_model(
        self,
        model: str,
        system_instruction: str,
        prompt: str,
        schema: dict,
        temperature: float
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
                if not self._is_transient_error(error):
                    raise

                if attempt + 1 >= self.MAX_ATTEMPTS_PER_MODEL:
                    break

                delay = min(2 ** (attempt + 1), 12)
                delay += random.uniform(0, min(1.5, delay * 0.25))

                print(
                    f"Modelo {model} temporalmente indisponible "
                    f"({self._error_code(error) or type(error).__name__}). "
                    f"Intento {attempt + 1}/"
                    f"{self.MAX_ATTEMPTS_PER_MODEL}. "
                    f"Nuevo intento en {delay:.1f} segundos."
                )
                time.sleep(delay)
                continue

            response_text = getattr(response, "text", None)
            if not response_text:
                raise RuntimeError(
                    f"Gemini devolvió una respuesta vacía con {model}."
                )

            if len(response_text.encode("utf-8")) > MAX_RESPONSE_BYTES:
                raise RuntimeError(
                    "La respuesta excede el límite de tamaño."
                )

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
        errors = []

        for index, model in enumerate(self.models_to_try):
            if index > 0:
                print()
                print(
                    f"FALLBACK: cambiando de {self.primary_model} "
                    f"a {model}."
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
                    temperature=temperature
                )
                self.active_model = model
                self.model = model
                print(f"Respuesta recibida correctamente de: {model}")
                return result

            except Exception as error:
                errors.append(
                    f"{model}: {type(error).__name__}: {error}"
                )

                can_try_fallback = index + 1 < len(self.models_to_try)
                can_switch = (
                    self._is_transient_error(error)
                    or self._is_model_not_found(error)
                )

                if can_try_fallback and can_switch:
                    print(
                        f"El modelo {model} no pudo completar la solicitud. "
                        "Se intentará el siguiente modelo disponible."
                    )
                    continue

                raise RuntimeError(
                    "Gemini no pudo completar la solicitud. "
                    "No se cambiará de modelo porque el error no parece "
                    "transitorio.\n" + "\n".join(errors)
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


def find_provider(source: str) -> ast.ClassDef:
    tree = ast.parse(source)
    matches = [
        node for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "GeminiProvider"
    ]
    if len(matches) != 1:
        fail(
            "Se esperaba exactamente una clase global GeminiProvider; "
            f"se encontraron {len(matches)}."
        )
    return matches[0]


def replace_provider(source: str) -> str:
    node = find_provider(source)
    lines = source.splitlines(keepends=True)

    replacement = NEW_PROVIDER.strip("\n") + "\n"
    updated = (
        lines[:node.lineno - 1]
        + [replacement]
        + lines[node.end_lineno:]
    )
    result = "".join(updated)

    tree = ast.parse(result)
    has_random = any(
        isinstance(item, ast.Import)
        and any(alias.name == "random" for alias in item.names)
        for item in tree.body
    )

    if not has_random:
        marker = "import re\n"
        if marker not in result:
            fail("No se encontró el import re para insertar import random.")
        result = result.replace(marker, marker + "import random\n", 1)

    ast.parse(result)
    compile(result, str(TARGET), "exec")
    return result


def atomic_write(path: Path, content: str) -> None:
    fd, temporary_name = tempfile.mkstemp(
        prefix=".autonomous_engineer_",
        suffix=".tmp",
        dir=str(path.parent)
    )
    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def create_backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.name}.{stamp}.bak")
    shutil.copy2(path, backup)
    return backup


def run_isolated_provider_test(source: str) -> None:
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

        def list(self):
            return [
                FakeModelInfo(
                    "models/gemini-3.8-flash",
                    ["generateContent"]
                ),
                FakeModelInfo(
                    "models/gemini-3.6-flash",
                    ["generateContent"]
                ),
                FakeModelInfo(
                    "models/gemini-3.1-flash-image",
                    ["generateImage"]
                ),
            ]

        def generate_content(self, model, contents, config):
            self.calls.append(model)
            if model == "gemini-3.8-flash":
                raise FakeError(503, "UNAVAILABLE")
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
        def Client(api_key):
            return fake_client

    class FakeTypes:
        @staticmethod
        def GenerateContentConfig(**kwargs):
            return kwargs

    class FakeTime:
        @staticmethod
        def sleep(_seconds):
            return None

    class FakeRandom:
        @staticmethod
        def uniform(_a, _b):
            return 0.0

    provider_node = find_provider(source)
    module = ast.Module(body=[provider_node], type_ignores=[])
    ast.fix_missing_locations(module)

    namespace = {
        "os": os,
        "json": json,
        "time": FakeTime,
        "random": FakeRandom,
        "genai": FakeGenAI,
        "types": FakeTypes,
        "MAX_RESPONSE_BYTES": 5_000_000,
    }

    old_key = os.environ.get("GEMINI_API_KEY")
    os.environ["GEMINI_API_KEY"] = "test-key"

    try:
        exec(
            compile(module, "<isolated-provider-test>", "exec"),
            namespace
        )

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
            "gemini-3.8-flash",
            "gemini-3.6-flash",
        ]
        assert "gemini-3.1-flash-image" not in provider.models_to_try

        provider.close()
        assert fake_client.closed

    finally:
        if old_key is None:
            os.environ.pop("GEMINI_API_KEY", None)
        else:
            os.environ["GEMINI_API_KEY"] = old_key

    print("Fallback 503 -> modelo alternativo: OK")
    print("Filtro de modelos generateContent: OK")
    print("Cierre del cliente: OK")


def main() -> int:
    print("=" * 72)
    print("ACTUALIZADOR DEL PROVEEDOR GEMINI")
    print("=" * 72)

    if not TARGET.is_file():
        fail(
            f"No se encontró autonomous_engineer.py en:\n{ROOT}"
        )

    original = TARGET.read_text(encoding="utf-8")
    ast.parse(original)
    compile(original, str(TARGET), "exec")
    find_provider(original)
    print("Código original y GeminiProvider: OK")

    updated = replace_provider(original)
    ast.parse(updated)
    compile(updated, str(TARGET), "exec")
    print("Proveedor actualizado en memoria: OK")

    run_isolated_provider_test(updated)

    if updated == original:
        fail("No se detectaron cambios para aplicar.")

    backup = create_backup(TARGET)
    print(f"Backup creado: {backup.name}")

    atomic_write(TARGET, updated)

    written = TARGET.read_text(encoding="utf-8")
    if written != updated:
        fail(
            "La verificación posterior a la escritura falló. "
            f"Backup: {backup}"
        )

    ast.parse(written)
    compile(written, str(TARGET), "exec")
    print("Sustitución atómica y validación AST: OK")

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(TARGET)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False
    )

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        fail(
            "py_compile falló. No ejecutes la auditoría. "
            f"Backup disponible: {backup}"
        )

    print("py_compile: OK")
    print()
    print("ACTUALIZACIÓN APLICADA Y VALIDADA.")
    print(f"Archivo: {TARGET}")
    print(f"Backup: {backup}")
    print(
        "Modelo alternativo predeterminado: "
        f"{DEFAULT_FALLBACK_MODEL}"
    )
    print(
        "Para cambiarlo, define GEMINI_FALLBACK_MODEL antes de ejecutar "
        "autonomous_engineer.py."
    )
    print()
    print(
        "No se ejecutó la auditoría ni se enviaron archivos a Gemini."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nOperación cancelada.")
        raise SystemExit(130)
    except Exception as error:
        print(f"\nERROR: {type(error).__name__}: {error}")
        raise SystemExit(1)
