# Autonomous Engineer

Versión: 1.0.0

Este directorio contiene el estado persistente del agente de ingeniería.

## Contenido

- `config.json`: configuración local y comandos autorizados de pruebas.
- `state.json`: estado de ejecución y tareas.
- `audit_history.jsonl`: historial de decisiones del auditor.
- `backups/`: copias de seguridad previas a modificaciones.
- `iterations/`: reportes técnicos de cada iteración.

## Seguridad

El agente no elimina archivos automáticamente ni ejecuta comandos
proporcionados por Gemini.

Las modificaciones requieren aprobación humana en modo supervisado.

## Recuperación

Los backups conservan la ruta original del archivo y su contenido anterior.
No se realiza rollback automático de cambios sin autorización.

## Configuración

Consulta `config.json` para modificar los comandos de pruebas autorizados.
