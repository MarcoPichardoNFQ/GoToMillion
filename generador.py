from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "autonomous_engineer.py"

AUDIT_TASK = (
    "Realiza una auditoría diagnóstica exhaustiva del proyecto actual. "
    "No modifiques archivos, no ejecutes cambios y no propongas "
    "implementaciones. Identifica defectos verificables, riesgos "
    "matemáticos, errores de lógica, problemas de arquitectura y "
    "deficiencias en las pruebas existentes. Distingue hechos "
    "comprobados de hipótesis."
)


# ============================================================
# UTILIDADES
# ============================================================

def print_section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def fail(message: str) -> None:
    raise RuntimeError(message)


def load_source(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"No se pudo leer {path.name}: {exc}")


def validate_python(source: str, label: str) -> None:
    try:
        ast.parse(source, filename=label)
        compile(source, label, "exec")
    except (SyntaxError, ValueError, TypeError) as exc:
        fail(
            f"El código resultante no es válido ({label}).\n"
            f"Detalle: {exc}"
        )


def find_class_method(
    source: str,
    class_name: str,
    method_name: str
) -> ast.FunctionDef:
    tree = ast.parse(source)

    matching_classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == class_name
    ]

    if len(matching_classes) != 1:
        fail(
            f"Se esperaba exactamente una clase {class_name}; "
            f"se encontraron {len(matching_classes)}."
        )

    methods = [
        node
        for node in matching_classes[0].body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == method_name
    ]

    if len(methods) != 1:
        fail(
            f"Se esperaba exactamente un método "
            f"{class_name}.{method_name}; "
            f"se encontraron {len(methods)}."
        )

    return methods[0]


def replace_method(
    source: str,
    class_name: str,
    method_name: str,
    replacement: str
) -> str:
    """
    Reemplaza un método completo utilizando posiciones AST.
    No depende de números de línea ni de coincidencias frágiles.
    """

    node = find_class_method(source, class_name, method_name)

    lines = source.splitlines(keepends=True)

    start = node.lineno - 1
    end = node.end_lineno

    indentation = " " * node.col_offset

    replacement_lines = replacement.strip("\n").splitlines()

    normalized = []

    for line in replacement_lines:
        if line.strip():
            normalized.append(indentation + line)
        else:
            normalized.append("")

    replacement_text = "\n".join(normalized) + "\n"

    updated_lines = (
        lines[:start]
        + [replacement_text]
        + lines[end:]
    )

    return "".join(updated_lines)


# ============================================================
# NUEVO MÉTODO REDACT
# ============================================================

REDACT_METHOD = r'''
def redact(self, content: str) -> str:
    """
    Oculta valores sensibles sin alterar código Python.

    Solo redacta valores literales asociados a asignaciones
    de credenciales. No modifica llamadas como:

        os.getenv("GEMINI_API_KEY")

    La redacción es heurística; no garantiza detectar todos
    los secretos posibles.
    """

    if not isinstance(content, str) or not content:
        return content

    assignment_pattern = re.compile(
        r"""(?ix)
        (
            \b
            (?:
                api[_-]?key
                |access[_-]?token
                |secret[_-]?key
                |password
                |passwd
                |client[_-]?secret
                |private[_-]?key
            )
            \b
            \s*[:=]\s*
        )
        (["'])
        (.*?)
        (\2)
        """
    )

    def redact_assignment(match):
        return (
            match.group(1)
            + match.group(2)
            + "[REDACTED]"
            + match.group(4)
        )

    content = assignment_pattern.sub(
        redact_assignment,
        content
    )

    bearer_pattern = re.compile(
        r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/=-]{12,}"
    )

    content = bearer_pattern.sub(
        r"\1[REDACTED]",
        content
    )

    private_key_pattern = re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
        r".*?"
        r"-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL
    )

    content = private_key_pattern.sub(
        "[REDACTED PRIVATE KEY]",
        content
    )

    return content
'''


# ============================================================
# CORRECCIÓN DEL MÉTODO SCAN
# ============================================================

def fix_scan_method(source: str) -> str:
    """
    Garantiza que el análisis estático Python/JSON reciba
    el contenido original, no el contenido redactado.

    El contenido redactado continúa siendo el que se conserva
    para construir el contexto enviado a Gemini.
    """

    node = find_class_method(
        source,
        "ReadOnlyProjectAuditor",
        "scan"
    )

    lines = source.splitlines(keepends=True)

    method_source = "".join(
        lines[node.lineno - 1:node.end_lineno]
    )

    marker = re.compile(
        r"(?m)^([ \t]*)content[ \t]*=[ \t]*"
        r"self\.redact\(content\)[ \t]*$"
    )

    matches = list(marker.finditer(method_source))

    if len(matches) != 1:
        fail(
            "No se pudo identificar de forma inequívoca "
            "la instrucción content = self.redact(content) "
            "dentro de ReadOnlyProjectAuditor.scan(). "
            f"Coincidencias encontradas: {len(matches)}."
        )

    match = matches[0]
    indentation = match.group(1)

    replacement = (
        f"{indentation}raw_content = content\n"
        f"{indentation}content = self.redact(raw_content)"
    )

    method_source = (
        method_source[:match.start()]
        + replacement
        + method_source[match.end():]
    )

    # El análisis estático debe utilizar el contenido original.
    inspection_pattern = re.compile(
        r"(self\.inspect_(?:python|json)\([^)]*)"
        r"\bcontent\b"
    )

    method_source, inspection_count = inspection_pattern.subn(
        lambda match: match.group(1) + "raw_content",
        method_source
    )

    if inspection_count < 1:
        fail(
            "No se encontraron llamadas a inspect_python() "
            "o inspect_json() que utilicen content. "
            "No se aplicará un parche parcial."
        )

    # Sustituye el método en el archivo completo.
    updated_lines = (
        lines[:node.lineno - 1]
        + [method_source]
        + lines[node.end_lineno:]
    )

    return "".join(updated_lines)


# ============================================================
# PRUEBAS DE REDACCIÓN
# ============================================================

def test_redaction() -> None:
    """
    Prueba el comportamiento de la expresión de redacción
    independientemente de la clase del auditor.
    """

    assignment_pattern = re.compile(
        r"""(?ix)
        (
            \b
            (?:
                api[_-]?key
                |access[_-]?token
                |secret[_-]?key
                |password
                |passwd
                |client[_-]?secret
                |private[_-]?key
            )
            \b
            \s*[:=]\s*
        )
        (["'])
        (.*?)
        (\2)
        """
    )

    bearer_pattern = re.compile(
        r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/=-]{12,}"
    )

    def redact_for_test(content: str) -> str:
        content = assignment_pattern.sub(
            lambda match: (
                match.group(1)
                + match.group(2)
                + "[REDACTED]"
                + match.group(4)
            ),
            content
        )

        content = bearer_pattern.sub(
            r"\1[REDACTED]",
            content
        )

        return content

    tests = [
        (
            'api_key = "abcdefgh123456"',
            "[REDACTED]" in redact_for_test(
                'api_key = "abcdefgh123456"'
            )
        ),
        (
            'password: "my-secret-password"',
            "[REDACTED]" in redact_for_test(
                'password: "my-secret-password"'
            )
        ),
        (
            'api_key = os.getenv("GEMINI_API_KEY")',
            redact_for_test(
                'api_key = os.getenv("GEMINI_API_KEY")'
            ) == 'api_key = os.getenv("GEMINI_API_KEY")'
        ),
        (
            "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123",
            "[REDACTED]" in redact_for_test(
                "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123"
            )
        ),
    ]

    failures = [
        description
        for description, passed in tests
        if not passed
    ]

    print(f"Pruebas de redacción: {len(tests) - len(failures)}/{len(tests)}")

    if failures:
        for failure in failures:
            print(f"  ERROR: {failure}")

        fail("Fallaron las pruebas locales de redacción.")


# ============================================================
# BACKUP Y ESCRITURA ATÓMICA
# ============================================================

def atomic_replace(path: Path, content: str) -> None:
    """
    Escribe primero en un archivo temporal y después reemplaza
    el archivo original mediante os.replace().
    """

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=".autonomous_engineer_",
        suffix=".tmp",
        dir=str(path.parent)
    )

    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(
            file_descriptor,
            "w",
            encoding="utf-8",
            newline=""
        ) as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary_path, path)

    except Exception:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass

        raise


def create_backup(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    backup = path.with_name(
        f"{path.name}.{timestamp}.bak"
    )

    shutil.copy2(path, backup)

    return backup


# ============================================================
# PROCESO PRINCIPAL
# ============================================================

def patch_agent() -> Path:
    print_section("1. VALIDACIÓN DEL ENTORNO")

    if not TARGET.is_file():
        fail(
            "No se encontró autonomous_engineer.py.\n"
            f"Ruta esperada: {TARGET}\n"
            "Coloca generador.py en la raíz del proyecto."
        )

    original = load_source(TARGET)

    print(f"Proyecto: {ROOT}")
    print(f"Archivo objetivo: {TARGET.name}")
    print(f"Tamaño original: {len(original.encode('utf-8')):,} bytes")

    print_section("2. VALIDACIÓN DEL CÓDIGO ORIGINAL")

    validate_python(original, TARGET.name)

    print("Sintaxis original: OK")

    print_section("3. LOCALIZACIÓN DE MÉTODOS")

    find_class_method(
        original,
        "ReadOnlyProjectAuditor",
        "redact"
    )

    find_class_method(
        original,
        "ReadOnlyProjectAuditor",
        "scan"
    )

    print("ReadOnlyProjectAuditor.redact(): encontrado")
    print("ReadOnlyProjectAuditor.scan(): encontrado")

    print_section("4. CONSTRUCCIÓN DEL PARCHE")

    updated = replace_method(
        original,
        "ReadOnlyProjectAuditor",
        "redact",
        REDACT_METHOD
    )

    updated = fix_scan_method(updated)

    validate_python(updated, TARGET.name)

    print("Método redact(): actualizado")
    print("Método scan(): actualizado")
    print("Validación AST y compilación: OK")

    print_section("5. PRUEBAS LOCALES")

    test_redaction()

    print("El código conserva llamadas os.getenv().")
    print("El análisis estático utilizará el contenido original.")

    if updated == original:
        fail("El parche no produjo ningún cambio.")

    print_section("6. BACKUP Y APLICACIÓN")

    backup = create_backup(TARGET)

    print(f"Backup creado: {backup.name}")

    try:
        atomic_replace(TARGET, updated)
    except Exception:
        print("ERROR: no se pudo sustituir el archivo.")
        print(f"El backup original está disponible en: {backup}")
        raise

    # Verificar el archivo realmente escrito.
    final_source = load_source(TARGET)

    validate_python(final_source, TARGET.name)

    if final_source != updated:
        fail(
            "La verificación posterior a la escritura "
            "no coincide con el código esperado."
        )

    print("Sustitución atómica: OK")
    print("Verificación posterior: OK")

    return backup


def run_compile_check() -> None:
    print_section("7. COMPILACIÓN REAL DEL ARCHIVO")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "py_compile",
            str(TARGET)
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        fail("py_compile detectó un error.")

    print("python -m py_compile: OK")


def launch_audit() -> int:
    print_section("8. EJECUCIÓN DE AUDITORÍA DE SOLO LECTURA")

    print("Se ejecutará el auditor con los siguientes parámetros:")
    print("  --audit-only")
    print("  --project-dir .")
    print("  --task [diagnóstico exhaustivo]")
    print()
    print(
        "El auditor puede solicitar autorización para enviar "
        "el contexto a Gemini."
    )
    print(
        "Revisa esa solicitud antes de responder. "
        "Este generador no autoriza el envío automáticamente."
    )

    command = [
        sys.executable,
        str(TARGET),
        "--audit-only",
        "--project-dir",
        str(ROOT),
        "--task",
        AUDIT_TASK
    ]

    print()
    print("Iniciando auditoría...")
    print("-" * 72)

    result = subprocess.run(
        command,
        cwd=str(ROOT),
        check=False
    )

    print("-" * 72)

    return result.returncode


def main() -> int:
    try:
        print_section("GENERADOR DE CORRECCIÓN DEL AUDITOR")

        print("Este proceso no modifica la lógica del proyecto.")
        print("Solo corrige el análisis estático y la redacción.")

        backup = patch_agent()

        run_compile_check()

        print_section("9. RESULTADO DEL PARCHE")

        print("PARCHE APLICADO Y VALIDADO")
        print(f"Archivo actualizado: {TARGET}")
        print(f"Backup disponible: {backup}")

        return launch_audit()

    except KeyboardInterrupt:
        print("\nProceso interrumpido por el usuario.")
        return 130

    except Exception as exc:
        print_section("ERROR")

        print(f"{type(exc).__name__}: {exc}")
        print()
        print("No continúes con la auditoría hasta revisar el error.")

        return 1


if __name__ == "__main__":
    raise SystemExit(main())