import os
import shutil
import ast
import sys
import time
import re
from pathlib import Path

# =========================================================
# CÓDIGO DE LA NUEVA CLASE GEMINI_PROVIDER
# =========================================================
# Nota: La implementación incluye control de presupuesto global,
# clasificación granular de errores y conteo de tokens.
NEW_GEMINI_PROVIDER_CODE = r'''
class GeminiProvider:
    MAX_ATTEMPTS_PER_MODEL = 2
    GLOBAL_BUDGET_SECONDS = 150
    FALLBACK_MODELS = ["gemini-3.6-flash"]

    def __init__(self, model: str, fallback_model: str | None = None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("No se encontró GEMINI_API_KEY.")
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.fallback_model = fallback_model or "gemini-3.6-flash"
        self.start_time = time.time()

    def _get_deadline(self) -> float:
        return self.start_time + self.GLOBAL_BUDGET_SECONDS

    def _is_transient(self, error) -> bool:
        code = getattr(error, "code", None)
        msg = str(error).upper()
        # Códigos HTTP 5xx son transitorios.
        return code in [503, 500, 502, 504] or any(x in msg for x in ["UNAVAILABLE", "DEADLINE_EXCEEDED", "INTERNAL SERVER ERROR"])

    def _is_rate_limit(self, error) -> bool:
        code = getattr(error, "code", None)
        # 429 indica limitación de tasa (Resource Exhausted).
        return code == 429 or "RESOURCE_EXHAUSTED" in str(error).upper()

    def generate_json(self, system_instruction: str, prompt: str, schema: dict, temperature: float = 0.1) -> dict:
        self.start_time = time.time()
        models_to_try = [self.model, self.fallback_model]
        
        last_error = None
        for model in models_to_try:
            attempt = 0
            while attempt < self.MAX_ATTEMPTS_PER_MODEL:
                if time.time() >= self._get_deadline():
                    raise RuntimeError("Presupuesto global de tiempo agotado.")

                try:
                    # Validar tokens antes de enviar para evitar errores de cuota innecesarios
                    try:
                        count = self.client.models.count_tokens(model=model, contents=prompt)
                        if count.total_tokens > 900000: # Margen de seguridad sobre el límite
                             raise RuntimeError(f"Solicitud excede tokens permitidos: {count.total_tokens}")
                    except Exception as e:
                        # Si count_tokens falla, procedemos con cautela
                        print(f"Advertencia: No se pudo verificar tokens: {e}")

                    response = self.client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=temperature,
                            response_mime_type="application/json",
                            response_json_schema=schema
                        )
                    )
                    
                    if not response.text:
                        raise RuntimeError("Respuesta vacía del modelo.")
                        
                    return json.loads(response.text)

                except Exception as e:
                    last_error = e
                    if self._is_rate_limit(e):
                        # Intentar esperar 30s sugeridos o backoff simple
                        print(f"Cuota agotada (429). Esperando...")
                        time.sleep(30.0)
                        attempt += 1
                        continue
                    elif self._is_transient(e):
                        wait = 2 ** attempt
                        print(f"Error transitorio ({type(e).__name__}). Reintentando en {wait}s...")
                        time.sleep(wait)
                        attempt += 1
                        continue
                    else:
                        # Error permanente (400, 401, 403, etc.), no reintentar
                        raise e
        raise RuntimeError(f"No se pudo completar la solicitud después de todos los intentos. Último error: {last_error}")

    def close(self):
        # Si el cliente necesita cierre explícito
        pass
'''

def patch_provider():
    target = Path("autonomous_engineer.py")
    if not target.exists():
        print("Error: autonomous_engineer.py no encontrado.")
        return

    backup = target.with_suffix(".bak")
    shutil.copy2(target, backup)
    print(f"Backup creado: {backup}")

    content = target.read_text(encoding="utf-8")
    
    # Regex para localizar la clase GeminiProvider. 
    # Busca 'class GeminiProvider' y captura hasta el inicio de la siguiente clase o fin de archivo.
    pattern = re.compile(r"class GeminiProvider:.*?(?=\n\nclass|\Z)", re.DOTALL)
    
    if not pattern.search(content):
        print("Error: No se pudo localizar la clase GeminiProvider en el archivo.")
        return

    new_content = pattern.sub(NEW_GEMINI_PROVIDER_CODE.strip(), content)
    
    try:
        # Validación de sintaxis antes de escribir
        ast.parse(new_content)
        target.write_text(new_content, encoding="utf-8")
        print("Archivo parcheado con éxito.")
    except SyntaxError as e:
        print(f"Error de sintaxis en el parche: {e}. Restaurando backup.")
        shutil.copy2(backup, target)
        sys.exit(1)

if __name__ == "__main__":
    patch_provider()