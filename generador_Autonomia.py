import os
import shutil
import ast
import re
from pathlib import Path

# =========================================================
# GENERADOR DE MODO AUTÓNOMO Y LOGGER
# =========================================================

PATCH_CODE = r'''
    def _log_autonomous_activity(self, iteration, programmer_summary, applied, verdict):
        log_path = self.project.agent_dir / "autonomous_progress.md"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n## Iteración {iteration}\n")
            f.write(f"**Requerimiento:** {self.config.get('active_task', {}).get('requirement', 'N/A')}\n\n")
            f.write(f"**Resumen:** {programmer_summary}\n\n")
            f.write(f"**Archivos modificados:**\n")
            for item in applied:
                f.write(f"- `{item['path']}`: {item['reason']}\n")
            f.write(f"\n**Veredicto Auditoría:** {verdict}\n")
            f.write("---\n")

    # Modificación de confirmación global para ignorar si es modo autónomo
    def _ask_confirmation_patched(message: str) -> bool:
        if os.getenv("AUTONOMOUS_MODE") == "1":
            return True
        return ask_confirmation(message)
'''

def patch_autonomy():
    target = Path("autonomous_engineer.py")
    if not target.exists():
        print("Error: autonomous_engineer.py no encontrado.")
        return

    content = target.read_text(encoding="utf-8")

    # 1. Parchear ProjectManager.load_config para permitir "autonomous"
    content = content.replace(
        'if config.get("mode") != "supervised":',
        'if config.get("mode") not in ["supervised", "autonomous"]:'
    )

    # 2. Inyectar el método de log en AutonomousEngineer
    # Buscamos la clase AutonomousEngineer
    class_pattern = re.compile(r"(class AutonomousEngineer:)")
    content = class_pattern.sub(r"\1\n    # Inyectado por generador de autonomía\n" + PATCH_CODE.replace("    def", "    def"), content)

    # 3. Sustituir las llamadas a ask_confirmation dentro de AutonomousEngineer.run por nuestra versión
    # Usamos un flag de entorno para detectar el modo
    content = content.replace("ask_confirmation(", "self._ask_confirmation_patched(")

    # 4. Inyectar lógica de log al finalizar auditoría en AutonomousEngineer.run
    log_call = "self._log_autonomous_activity(iteration, programmer.get('summary', ''), applied, verdict)"
    content = content.replace("self.project.append_history({", f"{log_call}\n            self.project.append_history({{")

    # 5. Asegurar que al ejecutar, el proceso sepa que es autónomo si config dice eso
    # Parcheamos la inicialización
    content = content.replace(
        'self.config = self.project.load_config()',
        'self.config = self.project.load_config()\n        if self.config.get("mode") == "autonomous": os.environ["AUTONOMOUS_MODE"] = "1"'
    )

    try:
        ast.parse(content)
        target.write_text(content, encoding="utf-8")
        print("Autonomía y Logger habilitados con éxito.")
    except SyntaxError as e:
        print(f"Error al aplicar parches: {e}")

if __name__ == "__main__":
    patch_autonomy()
