# Quantitative Advantage Play (AP) Blackjack Analytical Suite & Training Engine

**Tipo de documento:** expediente técnico consolidado y transferencia de conocimiento  
**Fecha de consolidación:** 2 de noviembre de 2026  
**Estado:** contexto histórico consolidado; requiere contraste obligatorio con el repositorio GitHub  
**Fuentes:** dos documentos de contexto proporcionados por el propietario del proyecto  
**Propósito:** proporcionar a una sesión independiente el contexto funcional, matemático, arquitectónico e histórico necesario para auditar el repositorio con exigencia de nivel Principal Software Engineer.

---

## 0. Instrucciones de lectura y autoridad de la información

Este documento consolida dos versiones previas de `PROJECT_TECHNICAL_CONTEXT.md`. No debe interpretarse como una certificación independiente del software ni como evidencia de que el repositorio actual contiene todos los cambios descritos.

### 0.1 Jerarquía de fuentes

1. **Repositorio GitHub:** fuente de verdad sobre el código, configuración, dependencias, pruebas y estado actual de la implementación.
2. **Pruebas reproducibles ejecutadas durante la auditoría:** fuente de evidencia sobre el comportamiento observado en un entorno concreto.
3. **Este documento:** fuente de contexto histórico, requisitos, decisiones declaradas, problemas previamente reportados y focos de investigación.
4. **Afirmaciones históricas no acompañadas de artefactos:** pistas que deben verificarse, no hechos demostrados.

Si el repositorio contradice este documento, no se debe modificar mentalmente el contexto para hacerlo coincidir con el código. Se debe registrar la discrepancia, identificar su impacto y determinar qué versión representa el comportamiento deseado.

### 0.2 Convenciones epistemológicas obligatorias

En la auditoría, clasificar cada afirmación relevante como:

- **Hecho observado:** comprobado directamente en el repositorio o reproducido mediante ejecución.
- **Antecedente reportado:** descrito en la conversación o en este documento, pero todavía no verificado de forma independiente.
- **Hipótesis:** explicación plausible que requiere investigación.
- **Riesgo:** condición que podría producir un defecto o una pérdida de calidad.
- **Pendiente:** cuestión que no puede resolverse con la información disponible.

No elevar una afirmación histórica a la categoría de hecho validado sin evidencia.

### 0.3 Advertencia sobre la integridad del contexto

Los documentos de origen contienen afirmaciones que no son completamente consistentes. En vez de ocultarlas, este expediente las conserva y las convierte en tareas explícitas de auditoría. En particular, deben investigarse las diferencias relativas a latencia, exactitud del método de Split, compensación OBO, cobertura de pruebas y garantías de concurrencia.

---

# 1. Identidad, objetivo y alcance del proyecto

## 1.1 Nombre

**Quantitative Advantage Play (AP) Blackjack Analytical Suite & Training Engine.**

## 1.2 Objetivo general

Suite de escritorio orientada al análisis cuantitativo del Blackjack, la evaluación de decisiones mediante composición de cartas, el entrenamiento operativo de habilidades de Advantage Play (AP) y el dimensionamiento financiero de apuestas.

El proyecto no se concibe como un juego recreativo convencional. Su propósito declarado es estudiar y entrenar decisiones de Blackjack considerando la composición residual del zapato, las reglas de la mesa, la distribución terminal del crupier, los sistemas de conteo, las desviaciones de índice y el riesgo financiero.

El núcleo pretende calcular el valor esperado (**EV**) de las acciones legales disponibles mediante un motor Composition-Dependent (CD), con recursión y memoización sobre estados de composición. La aspiración declarada es evitar aproximaciones Total-Dependent (TD) cuando la composición exacta sea necesaria y computacionalmente viable.

## 1.3 Alcance funcional conocido

El alcance descrito comprende:

- Modelo configurable de reglas de mesa.
- Representación compacta del zapato y sus cartas restantes.
- Cálculo de distribuciones terminales del crupier.
- Evaluación de acciones del jugador: Stand, Hit, Double, Split, Surrender e Insurance.
- Conteo de cartas y conversión a True Count.
- Métricas de Advantage Play y gestión de apuestas.
- Entrenadores de conteo, estimación de descarte y desviaciones de índice.
- Interfaz de escritorio PyQt6 para jugar manos de prueba, visualizar resultados y entrenar.
- Explicabilidad de decisiones y desglose de EV.

## 1.4 Tecnologías declaradas

- Python 3.10 / 3.11+ (las versiones exactas compatibles deben verificarse).
- PyQt6.
- NumPy (su uso efectivo en el código debe verificarse; uno de los documentos lo describe como tecnología conceptual o secundaria).
- `unittest` y/o `pytest` (el mecanismo real de ejecución debe verificarse).
- Componentes Qt: `QGraphicsScene`, `QThreadPool`, `QRunnable`, señales y slots.

No asumir que todas estas dependencias se utilizan actualmente ni que las versiones mínimas citadas son las instaladas en el repositorio.

---

# 2. Evolución histórica reconstruida

La siguiente cronología refleja los antecedentes reportados, no una verificación del historial de commits.

## 2.1 Fase 1 — Formalización teórica

- Planteamiento del Blackjack como proceso de decisión finito y absorbente.
- Uso declarado de ecuaciones de Bellman e inducción hacia atrás.
- Preferencia por estrategias Composition-Dependent (CD) frente a heurísticas Total-Dependent (TD).
- Modelado de estados mediante la composición residual del zapato y las reglas activas.
- Identificación del problema combinatorio de Split y necesidad de limitar la exploración del árbol.

## 2.2 Fase 2 — Core combinatorio

Se reporta la creación de:

- `core/rules.py`
- `core/shoe.py`
- `core/dealer.py`
- `core/combinatorial.py`

Decisiones y técnicas declaradas:

- Representación del zapato como frecuencias de diez denominaciones.
- Empaquetado de la composición en un entero de 64 bits.
- Precomputación de desplazamientos, máscaras y datos de cartas.
- Memoización de estados para la evaluación recursiva.
- Tabla de EV de Stand precomputada.
- Uso de una técnica atribuida a Peter Griffin para reducir la complejidad del cálculo de Split.

**Punto crítico:** la reducción de complejidad del Split debe auditarse matemáticamente. No aceptar que una técnica sea exacta únicamente por su atribución bibliográfica o por producir resultados plausibles. Deben documentarse las hipótesis de independencia, extracción sin reemplazo, composición compartida, orden de resolución de manos y condiciones bajo las cuales la transformación conserva el EV.

## 2.3 Fase 3 — Advantage Play y métricas financieras

Se reporta la incorporación de:

- `core/counting.py`
- `core/ap_metrics.py`

Capacidades declaradas:

- Sistemas de conteo Hi-Lo, Zen, Omega II y Wong Halves.
- Modos de cuantización del True Count: `FLOOR`, `TRUNCATE` y `ROUND`.
- Cálculo de Ace Surplus.
- Estimación de Player Edge.
- Cálculo de `N_0`.
- SCORE mediante la identidad declarada `SCORE = 1,000,000 / N_0`.
- Riesgo de Ruina (RoR).
- Dimensionamiento de apuesta mediante Kelly fraccional.

Las fórmulas, unidades, convenciones y supuestos estadísticos deben verificarse contra la implementación y referencias técnicas reconocidas. En particular, no asumir que una fórmula de RoR o Kelly es válida para cualquier distribución de resultados, spread, reglas, penetración o dependencia entre manos.

## 2.4 Fase 4A — Infraestructura gráfica

Se reporta el desarrollo de:

- `gui/components/table_view.py`
- `gui/components/ap_hud.py`
- `training/drills.py`

Capacidades declaradas:

- Renderizado vectorial de mesa y cartas.
- Bandeja de descarte con indicador de corte.
- HUD de conteo y métricas AP.
- Entrenadores desacoplados de la interfaz gráfica.
- Visualización de métricas y auditoría de decisiones.

## 2.5 Fase 4B — Vistas y orquestación

Se reporta el desarrollo de:

- `gui/views/table_view_controller.py`
- `gui/views/drills_view.py`
- `gui/views/academy_view.py`
- `gui/views/xai_view.py`
- `gui/main_window.py`

Capacidades declaradas:

- Mesa interactiva con Decision Coach.
- Banners de coste de error expresado en EV/centavos.
- Entrenadores de conteo rápido, estimación de descarte y laboratorio de índices.
- Matriz de estrategia básica generada según reglas activas.
- Árbol de decisión y explicaciones matemáticas.
- Ejecución de evaluaciones en segundo plano mediante `QThreadPool`.
- Identificador de evaluación `eval_id` para descartar resultados obsoletos.

---

# 3. Arquitectura y estructura de archivos reportada

La siguiente estructura es la estructura esperada descrita en los documentos de origen. No constituye prueba de que todos los archivos existan en la rama actual.

```text
PROJECT_COMPLETO/
├── core/
│   ├── __init__.py
│   ├── rules.py
│   ├── shoe.py
│   ├── dealer.py
│   ├── combinatorial.py
│   ├── counting.py
│   └── ap_metrics.py
├── training/
│   ├── __init__.py
│   └── drills.py
├── gui/
│   ├── __init__.py
│   ├── main_window.py
│   ├── components/
│   │   ├── __init__.py
│   │   ├── table_view.py
│   │   └── ap_hud.py
│   └── views/
│       ├── __init__.py
│       ├── table_view_controller.py
│       ├── drills_view.py
│       ├── academy_view.py
│       └── xai_view.py
├── tests/
│   ├── __init__.py
│   ├── test_ap_master_suite.py
│   └── test_ap_metrics.py
├── run_app.py
└── run_gui_demo.py
```

También deben inspeccionarse `requirements.txt`, archivos de configuración, documentación, workflows de CI/CD, scripts auxiliares, datos de prueba y cualquier otro módulo que realmente exista en GitHub.

## 3.1 `core/rules.py` — Reglas de mesa

Se atribuye a este módulo la definición inmutable `TableRules`.

Reglas y parámetros mencionados:

- Número de mazos: 1–8.
- Penetración: 10–95%.
- Pago de Blackjack: 3:2, 6:5 y, según uno de los documentos, 1:1.
- Crupier planta o pide en Soft 17: S17/H17.
- Juego con carta oculta (`is_hole_card_game`) o ENHC.
- OBO (`allow_obo`).
- DAS (`double_after_split` o nombre equivalente).
- RSA (`allow_rsa`).
- Surrender.
- Límite máximo de manos divididas.
- Restricciones y validaciones de combinaciones de reglas.

Se menciona que `TableRules` podría utilizar `dataclass(frozen=True, slots=True)` y enums. Verificar la implementación real, validaciones, tipos, valores por defecto y compatibilidad de reglas.

## 3.2 `core/shoe.py` — Composición y empaquetado

El zapato se describe como un vector de diez frecuencias:

\[
\mathbf{s}=(c_1,c_2,\ldots,c_{10})
\]

Las denominaciones 1–9 representan As y valores 2–9; la décima representa todas las cartas de valor 10 (10, J, Q, K).

### Empaquetado `uint64` declarado

- Denominaciones 1–9: 6 bits por frecuencia.
- Denominación 10: 8 bits.
- Desplazamientos: `0, 6, 12, ..., 48` para los primeros nueve campos y `54` para el décimo.

Expresión reportada:

\[
packed =
\left(\sum_{i=0}^{8} c_{i+1} \ll (6i)\right)
\;|\;
(c_{10}\ll54)
\]

La suma de anchos ocupa 62 bits, por lo que cabe en un entero de 64 bits. Los anchos declarados admiten hasta 63 cartas en cada uno de los primeros nueve campos y 255 en el décimo; son suficientes para los máximos esperados en ocho mazos (32 y 128, respectivamente).

Se reporta precomputación de:

- `CARDS_DATA`
- `SHIFTS`
- `MASKS`
- `DECREMENT_MASKS`

La extracción y decremento se realizarían mediante operaciones de bits y resta del decrement mask.

**Auditoría obligatoria:**

1. Verificar que `pack_shoe` y `unpack_shoe` sean inversas para todo el dominio válido.
2. Verificar que no existan colisiones entre composiciones válidas.
3. Validar límites, valores negativos, tipos y entradas fuera de rango.
4. Comprobar que el decremento solo se realice cuando el contador correspondiente sea positivo.
5. Comprobar que el decremento de un campo no provoque borrow hacia campos adyacentes en estados inválidos.
6. Verificar que el formato no exceda 64 bits y que no haya supuestos ocultos sobre el máximo de mazos.
7. Comparar el resultado de las operaciones empaquetadas contra una implementación de referencia simple.

## 3.3 `core/dealer.py` — Distribución terminal del crupier

Clase reportada: `DealerEngine`.

Calcula una distribución de probabilidad terminal condicionada a la carta visible y a la composición residual del zapato.

Estados terminales citados:

- Totales 17, 18, 19, 20 y 21.
- `BUST = 22`.
- `NATURAL_BJ = 210` (sentinela reportado; verificar que no colisione con otro estado y que se use consistentemente).

### American Hole Card / Peek

Cuando `is_hole_card_game == True`, se afirma que, si el crupier muestra As o 10 y el Peek ha descartado Blackjack, la distribución se condiciona a la ausencia de la carta complementaria. En ese escenario, la masa de probabilidad de `NATURAL_BJ` debe ser cero durante la decisión del jugador.

Verificar cuidadosamente **cuándo** se aplica el Peek: no se debe eliminar la probabilidad de Blackjack antes de que el juego haya realizado efectivamente el chequeo correspondiente. También deben distinguirse los casos en que no se realiza Peek o en que la información aún no está disponible.

### ENHC — European No Hole Card

Cuando `is_hole_card_game == False`, se reporta que el crupier obtiene la segunda carta posteriormente y conserva la posibilidad de Blackjack natural al completar su mano.

Verificar el momento en que se materializa la segunda carta y cómo se contabilizan las apuestas adicionales del jugador bajo las reglas de pérdida aplicables.

## 3.4 `core/combinatorial.py` — Motor CD

Clase reportada: `CompositionDependentEngine`.

Capacidades atribuidas:

- Stand mediante tabla precomputada.
- Hit mediante inducción hacia atrás y memoización.
- Double.
- Split con límite de resplits y tratamiento especial de Ases.
- Surrender.
- Insurance (se menciona `Action.INSURANCE = auto()` en una de las verificaciones pendientes).
- Aplicación de reglas de crupier, pago, Peek, ENHC y OBO.

Se reporta una caché:

`hit_cache: Dict[Tuple[int, bool, int], float]`

La estructura real de la clave, la semántica de cada campo y la estrategia de invalidación deben comprobarse.

### Stand

`build_stand_table(dealer_dist)` produciría una tabla de EV para totales 0–21, permitiendo evaluar Stand en tiempo constante.

Auditar:
- Tratamiento de push, Blackjack natural y bust.
- Multiplicadores y convención de unidades de apuesta.
- Diferencias entre mano ordinaria y natural.
- Condicionamiento del crupier.
- Precisión numérica y tolerancias.

### Hit

Se reporta una recursión sobre composiciones residuales empaquetadas y memoizadas.

Auditar:
- Corrección de las probabilidades sin reemplazo.
- Condiciones terminales.
- Soft totals y conversión de As.
- Profundidad de recursión.
- Estados imposibles.
- Reutilización e invalidación de caché.
- Consistencia entre el estado de mano y el estado del zapato.

### Split

Se describe una optimización atribuida a la expectativa marginal de Griffin para evitar una expansión combinatoria excesiva.

Auditar con especial rigor:
- Si las manos divididas comparten el mismo zapato residual o se modelan como ramas independientes.
- Cómo se representa el orden de juego de las manos.
- Cuándo se extraen las cartas de cada mano.
- Qué dependencias se conservan o se aproximan.
- Cómo se gestionan DAS, RSA, límites de manos, Ases divididos y cartas adicionales.
- Si la técnica preserva el EV bajo las reglas concretas implementadas.
- Si las pruebas comparan contra una enumeración exacta independiente para zapatos pequeños.

No llamar “exacto” a un resultado si el método introduce una aproximación, independencia asumida o simplificación no demostrada.

### OBO

Se reporta soporte para `Original Bets Only` bajo ENHC. La descripción histórica de su implementación es inconsistente y se trata en la sección 6.2.

## 3.5 `core/counting.py` — Conteo de cartas

Clase reportada: `CardCounter`.

Sistemas citados:

- Hi-Lo.
- Zen.
- Omega II.
- Wong Halves.

Modos de conversión a True Count:

- `FLOOR`.
- `TRUNCATE`.
- `ROUND`.

También se reporta cálculo de Ace Surplus.

Auditar:
- Tabla exacta de tags por denominación.
- Balanceo de cada sistema.
- Escalamiento de conteo verdadero por mazos restantes.
- Convención de redondeo para negativos.
- Precisión de Wong Halves.
- Estimación de mazos restantes y penetración.
- Consistencia entre cartas vistas, descarte y cartas remanentes.
- Tratamiento de un zapato nuevo, corte y reshuffle.

## 3.6 `core/ap_metrics.py` — Métricas AP

Clase reportada: `AdvantagePlayMetrics`.

Métricas declaradas:

- Player Edge.
- Kelly fraccional.
- Límites de apuesta.
- `N_0`.
- SCORE.
- Riesgo de Ruina (RoR).

Identidad de SCORE declarada:

\[
SCORE=\frac{1{,}000{,}000}{N_0}
\]

Auditar fórmulas, unidades y supuestos. Verificar si `N_0` se calcula con la definición y las convenciones estadísticas correctas; si se utiliza varianza por mano, por ronda o por unidad de apuesta; y si el resultado es compatible con el SCORE reportado.

Para Kelly, revisar:
- Edge y varianza utilizados.
- Fracción de Kelly.
- Bankroll y límites.
- Mínimo/máximo de apuesta.
- Redondeo a `chip_unit`.
- Condición de edge no positivo.
- Bankroll insuficiente para `min_bet`.
- Posibilidad de apostar por encima del bankroll.
- Efecto de spreads, correlación y variabilidad de resultados.

Se reporta que `recommend_bet` puede forzar `min_bet` cuando el bankroll es bajo, salvo que se active `allow_wong_out`. Esto requiere evaluación crítica: imponer la apuesta mínima con bankroll insuficiente o ventaja negativa podría ser una decisión de producto peligrosa. Debe existir una política explícita y testeada para no apostar, abandonar la mesa o emitir una advertencia de riesgo.

## 3.7 `training/drills.py` — Entrenadores

Se describen tres entrenadores desacoplados de PyQt6:

1. **Estimación de descarte:** estimación visual de mazos descartados, cálculo de error y distorsión inducida en True Count.
2. **Conteo rápido:** presentación de cartas y cálculo del Running Count, con generación de secuencias y pares cancelables.
3. **Laboratorio de índices:** escenarios de desviación de estrategia básica, con catálogo reportado de 22 escenarios: Illustrious 18 (incluyendo Insurance) y Fab 4.

Se reporta que el muestreo del entrenador de conteo rápido fue corregido para reflejar frecuencias reales:

`random.choices(range(1, 11), weights=[4, 4, 4, 4, 4, 4, 4, 4, 4, 16])`

Auditar:
- Que la distribución corresponda a una baraja estándar y a la representación de diez denominaciones.
- Que la secuencia de cartas sea reproducible mediante semilla cuando se requiera.
- Que la generación respete el número de mazos, si el drill pretende simular un zapato real.
- Que los pares cancelables no distorsionen inadvertidamente la distribución.
- Que los índices correspondan a las reglas de mesa y sistema de conteo seleccionados.
- Que no se presente un índice como universal cuando dependa de reglas o convenciones.

## 3.8 `gui/components/table_view.py` — Mesa gráfica

Se reporta uso de `QGraphicsScene`, `CardItem` y `DiscardTrayWidget`.

Capacidades:
- Renderizado de mesa y cartas.
- Animaciones.
- Bandeja de descarte.
- Indicador visual de corte.
- Marcadores de manos divididas y mano activa.

Se reportó una fuga de elementos gráficos por creación de marcadores de mano activa sin retener referencias. La corrección declarada fue mantener `self._hand_markers: List[QGraphicsItem]` y retirar los elementos anteriores de la escena antes de redibujar.

Auditar:
- Ciclo de vida de cada `QGraphicsItem`.
- Propiedad y pertenencia a `QGraphicsScene`.
- Eliminación de señales, timers y referencias.
- Crecimiento de objetos tras miles de rondas.
- Animaciones interrumpidas y objetos huérfanos.
- Coste de repintado y escalabilidad de la escena.

## 3.9 `gui/components/ap_hud.py` — HUD AP

Se atribuyen al HUD:
- Running Count.
- True Count.
- Edge.
- Apuesta Kelly.
- Histograma de densidad de residuo.
- Auditoría de EV.
- Distribución terminal del crupier.

Auditar que los valores mostrados correspondan al mismo estado de mano, zapato, reglas y versión de evaluación. Evitar mezclar resultados de cálculos asíncronos diferentes.

## 3.10 `gui/views/table_view_controller.py` — Controlador de mesa

Se describe como controlador de la mesa interactiva:
- Botonera y atajos.
- Ciclo de vida de mano.
- Despliegue de cartas.
- Decision Coach.
- Coste de error en EV.
- Actualización del conteo y HUD.
- Reset de zapato y contador al alcanzar la tarjeta de corte.

Auditar especialmente el orden de mutaciones del estado, la consistencia de las manos divididas, el cierre de ronda, los estados de botones y la interacción con workers activos.

## 3.11 `gui/views/drills_view.py` — Interfaz de entrenadores

Orquesta:
- Conteo de velocidad mediante `QTimer`.
- Estimación visual mediante slider.
- Dilemas de índices.

Auditar cancelación de timers, cambio de vistas, reinicio de sesiones, acumulación de señales y sincronización entre estado visual y lógica de entrenamiento.

## 3.12 `gui/views/academy_view.py` — Academia

Se describe como módulo educativo con cuatro subsecciones y generador dinámico de matriz de estrategia básica según reglas activas.

Auditar:
- Coherencia de reglas y matriz generada.
- Tratamiento de pares, manos blandas y duras.
- Reglas de surrender, DAS, H17/S17 y número de mazos.
- Diferenciación entre estrategia básica y estrategia dependiente de composición.
- Evitar presentar una matriz aproximada como exacta.

## 3.13 `gui/views/xai_view.py` — Explicabilidad

Se describe un árbol jerárquico de decisión y demostraciones matemáticas paso a paso.

Auditar que la explicación se derive de los mismos valores y estados que el motor utilizó. La explicación no debe reconstruir una lógica paralela que pueda contradecir el cálculo real.

## 3.14 `gui/main_window.py` — Shell y concurrencia

Se reporta:
- Navegación lateral y `QStackedWidget`.
- Selector de reglas.
- `CDEvaluationWorker(QRunnable)`.
- Uso de `QThreadPool.globalInstance()`.
- Token `eval_id` para descartar resultados obsoletos.

Flujo descrito:
1. El controlador actualiza el estado de mano y zapato.
2. Se solicita una evaluación asíncrona.
3. El worker ejecuta `evaluate_hand_with_counting` o la operación equivalente.
4. El motor CD calcula los EV.
5. El worker emite resultado y `eval_id`.
6. El hilo de UI compara el identificador con el vigente.
7. El HUD actualiza únicamente si el resultado sigue siendo actual.

**Advertencia:** un token de generación evita aplicar resultados obsoletos, pero no garantiza por sí mismo la seguridad de concurrencia. Debe verificarse si los workers reciben snapshots inmutables o referencias a objetos mutables; si las cachés son compartidas; si el motor es thread-safe; y si el cierre de ventana o reset de zapato puede dejar workers activos.

## 3.15 Entradas de ejecución

- `run_app.py`: punto de entrada de producción.
- `run_gui_demo.py`: punto de entrada de demostración.

Auditar imports, rutas relativas, configuración, errores de arranque, dependencias y ejecución desde directorios distintos. Verificar que no existan rutas absolutas locales.

---

# 4. Historial de defectos, correcciones y resultados reportados

Las correcciones siguientes fueron descritas en los documentos de origen. Deben comprobarse en el repositorio y, cuando sea posible, reproducirse con pruebas independientes.

## 4.1 Latencia del motor combinatorio

**Problema reportado:** evaluaciones en frío de manos complejas con Split excedían ampliamente el objetivo. Las cifras históricas no son consistentes: una versión se describe con latencias superiores a 900 ms; otra versión intermedia, con 18–22 ms; el segundo documento menciona más de 80 ms en frío.

**Causa atribuida:** conversiones redundantes entre listas y tuplas dentro de la recursión (`counts_list = list(counts_tuple)` y `next_counts = tuple(counts_list)`), asignaciones temporales y recorrido repetido de estados terminales del crupier.

**Correcciones reportadas:**
- Tabla de Stand precomputada.
- Uso de enteros empaquetados y decrementos mediante máscaras.
- Reutilización de datos estáticos de cartas.
- Reducción de asignaciones intermedias.

**Resultado reportado:** aproximadamente 7.2–7.5 ms en frío para una prueba de Split compleja; objetivo declarado inferior a 10 ms.

**Verificación obligatoria:** ejecutar benchmark realmente frío, limpiar todas las cachés pertinentes, documentar hardware, versión de Python, sistema operativo, reglas, composición, número de repeticiones, percentiles y dispersión. Distinguir tiempo de una evaluación individual, inicialización, compilación/imports y latencia end-to-end de UI. No afirmar “consistentemente” sin datos reproducibles.

## 4.2 Blackjack natural y pago

**Problema reportado:** una mano inicial As + carta de valor 10 se trataba como 21 ordinario y no recibía el pago especial configurado.

**Corrección reportada:** detección de Blackjack natural al inicio de `evaluate_decision`; acciones no aplicables (`Hit`, `Double`, `Split`, `Surrender`) se fijan en `None`; cálculo del pago conforme a `TableRules.blackjack_payout`, considerando la posibilidad de empate con Blackjack del crupier.

**Pruebas mencionadas:** `test_02_natural_blackjack_payouts_and_dealer_peek`, para pagos 3:2 y 6:5.

**Auditoría:** comprobar si el natural se reconoce únicamente con dos cartas iniciales, si un 21 posterior no se clasifica como natural, cómo interactúa con Peek/ENHC y cómo se calcula el push contra natural del crupier.

## 4.3 Acondicionamiento de American Peek

**Problema reportado:** la distribución del crupier conservaba probabilidad de Blackjack natural después de que el Peek americano lo hubiera descartado.

**Corrección reportada:** acondicionar la distribución de la carta oculta cuando el crupier muestra As o 10 y el chequeo ha descartado Blackjack.

**Prueba mencionada:** `test_03_hole_card_peek_conditioning_effect`.

**Auditoría:** verificar el denominador de la distribución condicionada, la carta visible, las cartas disponibles, la secuencia exacta del Peek y que el acondicionamiento no se aplique en ENHC ni antes del momento correcto.

## 4.4 Re-split de Ases y límite de manos

**Problemas reportados:**
- `allow_rsa=True` y `False` producían el mismo EV.
- Se permitía dividir cuando `max_split_hands <= 1`.
- La lógica de Ases podía impedir un re-split permitido.

**Correcciones reportadas:**
- Guardar la posibilidad de Split con `max_split_hands >= 2`.
- Inicializar `resplits_left = max_split_hands - 2`.
- Permitir resplit de Ases cuando `allow_rsa` sea verdadero y se cumplan los límites.

**Pruebas mencionadas:** `test_04_resplit_aces_differential` y `test_01_split_limits_and_zero_division_guard`.

Auditar conteo de manos, semántica de `max_split_hands`, límite de resplits, orden de extracción y casos de varios Ases.

## 4.5 Manos blandas tras Split

**Problema reportado:** al dividir Ases y robar una carta, la mano podía clasificarse incorrectamente como dura.

**Corrección reportada:** cálculo simétrico de la condición soft, descrito como `is_soft = (card == 1 or card_val == 1)`.

**Prueba mencionada:** `test_04_resplit_aces_and_soft_eval`.

Auditar la evaluación general de Ases con más de dos cartas. La expresión reportada puede ser válida para un subcaso concreto, pero no debe asumirse suficiente para todos los estados: verificar total duro, número de Ases, conversión de 11 a 1 y soft total resultante.

## 4.6 Frontera de Surrender en 8-8 vs 10

**Problema reportado:** una prueba esperaba que Surrender superara a Split en 8-8 vs 10, pero esa expectativa no coincidía con el modelo de American Peek.

**Explicación reportada:** el Peek modifica la distribución condicional del crupier; se citan valores aproximados de Bust de 23.16%, 21 de 3.77%, EV de Split entre -0.4749 y -0.4862, y EV de Surrender de -0.50. Para ENHC se reporta un EV de Split de -0.6102.

**Corrección reportada:** ajustar las aserciones para diferenciar American Peek de ENHC.

**Auditoría:** no aceptar esos valores como referencias universales. Recalcularlos desde la composición exacta, reglas, número de mazos, composición de la mano, carta visible, penetración y condiciones de la prueba. Comprobar que las unidades de EV y las apuestas iniciales sean consistentes.

## 4.7 Regla OBO en ENHC

**Problema reportado:** al producirse Blackjack natural del crupier, el motor no devolvía correctamente apuestas adicionales de Split o Double bajo OBO.

**Correcciones descritas en los documentos, potencialmente contradictorias:**
- Una versión afirma que `evaluate_decision` consolida el EV de Split añadiendo `+P(Dealer BJ)` cuando aplica ENHC + OBO.
- Otra afirma que la compensación se inyectó en ramas internas, incluyendo `_ev_split_ace_branch`, para devolver la apuesta secundaria.
- Se menciona que la prueba `test_02_obo_rule_behavior_in_enhc` fija `allow_rsa=False` para aislar una sola división.
- Se cita una discrepancia numérica previa de `0.082718` frente a `0.071197`.

**Estado:** discrepancia de implementación histórica no resuelta por el material disponible.

**Auditoría obligatoria:** derivar primero la convención de EV y la regla exacta de liquidación. Enumerar casos de Double, Split simple, múltiples resplits, Split de Ases, DAS y varias manos. Determinar qué apuestas se pierden o devuelven cuando el crupier obtiene Blackjack. Probar que la compensación se aplica exactamente una vez por apuesta adicional afectada, sin omisión ni doble conteo. No adoptar ninguna de las dos descripciones de implementación sin inspeccionar el código y derivar el resultado esperado.

## 4.8 Error `UnboundLocalError` en DealerEngine

**Problema reportado:** `get_terminal_distribution` con carta visible 10 generaba `UnboundLocalError` para `shift`.

**Causa atribuida:** uso de `shift` y `mask` sin desempaquetar previamente los datos de `CARDS_DATA[i]`.

**Corrección reportada:** desempaquetado explícito de `shift, mask, dec_mask, card_val`.

**Estado reportado:** validado por la suite local. Reproducir con una prueba de regresión.

## 4.9 Fuga de elementos gráficos

**Problema reportado:** degradación del rendimiento gráfico tras partidas prolongadas.

**Causa atribuida:** marcadores elípticos de mano activa añadidos a `QGraphicsScene` sin referencias retenidas ni limpieza.

**Corrección reportada:** colección `self._hand_markers` y retirada explícita de elementos anteriores antes de redibujar.

**Estado reportado:** inspección estática del ciclo de vida. No equivale a una prueba de ausencia de fugas. Medir crecimiento de memoria y cantidad de items tras ciclos prolongados.

## 4.10 Muestreo sesgado en SpeedCountDrill

**Problema reportado:** el generador utilizaba `random.randint(1, 10)`, asignando probabilidad uniforme a las diez denominaciones y provocando una deriva positiva artificial del conteo Hi-Lo.

**Corrección reportada:** muestreo ponderado con pesos `[4,4,4,4,4,4,4,4,4,16]`.

**Estado reportado:** verificado mediante simulaciones de muestreo determinista.

Auditar que el muestreo coincida con la composición de una baraja estándar y que los tests evalúen tanto frecuencias como valor esperado del tag de conteo.

---

# 5. Inventario de funcionalidades y estado histórico declarado

Los estados siguientes son los declarados en los documentos de origen; no son una certificación de la rama actual.

| ID | Componente | Funcionalidad | Estado histórico declarado |
|---|---|---|---|
| FN-CORE-01 | `core/rules.py` | Reglas de mesa, validación de mazos, penetración, payout, S17/H17, Peek/ENHC, OBO, DAS, RSA y Surrender | Implementada y reportada como validada |
| FN-CORE-02 | `core/shoe.py` | Composición de diez denominaciones, packing/unpacking y cut card | Implementada y reportada como validada |
| FN-CORE-03 | `core/dealer.py` | Distribución terminal del crupier y condicionamiento Peek | Implementada y reportada como validada |
| FN-CORE-04 | `core/combinatorial.py` | EV CD de Stand, Hit, Double, Split, Surrender e Insurance | Implementada y reportada como validada |
| FN-CORE-05 | `core/counting.py` | Sistemas multinivel, True Count, cuantización y Ace Surplus | Implementada y reportada como validada |
| FN-CORE-06 | `core/ap_metrics.py` | Edge, Kelly, límites, N₀, SCORE y RoR | Implementada y reportada como validada |
| FN-TRN-01 | `training/drills.py` | Estimación de descarte | Implementada y reportada como validada |
| FN-TRN-02 | `training/drills.py` | Conteo rápido con muestreo ponderado | Implementada y reportada como validada |
| FN-TRN-03 | `training/drills.py` | Catálogo de 22 escenarios Illustrious 18 + Fab 4 | Implementada y reportada como validada |
| FN-GUI-01 | `gui/components/table_view.py` | Mesa vectorial, cartas, bandeja de descarte y marcadores | Implementada y reportada como validada |
| FN-GUI-02 | `gui/components/ap_hud.py` | HUD de telemetría y auditoría EV | Implementada y reportada como validada |
| FN-GUI-03 | `gui/views/table_view_controller.py` | Mesa jugable y Decision Coach | Implementada y reportada como validada |
| FN-GUI-04 | `gui/views/drills_view.py` | Interfaz de los tres entrenadores | Implementada y reportada como validada |
| FN-GUI-05 | `gui/views/academy_view.py` | Academia y matriz dinámica de estrategia básica | Implementada y reportada como validada |
| FN-GUI-06 | `gui/views/xai_view.py` | Árbol de explicabilidad y demostraciones | Implementada y reportada como validada |
| FN-GUI-07 | `gui/main_window.py` | Navegación y evaluación asíncrona | Implementada y reportada como validada |

La auditoría debe actualizar esta tabla con estados basados en evidencia: presente, ausente, incompleto, ejecutable, probado, parcialmente probado, defectuoso o no verificable.

---

# 6. Discrepancias y riesgos que no deben ocultarse

## 6.1 Latencia: cifras históricas incompatibles

Los documentos mencionan:
- Más de 900 ms en una versión inicial.
- Entre 18 y 22 ms en una versión intermedia.
- Más de 80 ms en otra descripción de la versión previa.
- Aproximadamente 7.2–7.5 ms tras las optimizaciones.

No se conoce si las cifras se obtuvieron con el mismo hardware, composición, reglas, caché, versión de Python o metodología. La auditoría debe reconstruir un benchmark reproducible antes de confirmar la mejora.

## 6.2 OBO: dos explicaciones de compensación

Una descripción aplica una compensación en el nivel superior de evaluación y otra la aplica en ramas de Split. No se puede asumir que ambas sean equivalentes. Existe riesgo de:
- Compensar dos veces una apuesta.
- No compensar apuestas de determinadas ramas.
- Aplicar el reintegro a una apuesta no elegible.
- Obtener un resultado correcto en el caso simple y erróneo con resplits.

Debe derivarse el EV por escenario y comparar contra enumeración independiente.

## 6.3 Exactitud de Split y método de Griffin

La documentación utiliza expresiones como “exacto” y “podar combinatoria” sin detallar formalmente las condiciones. Es un punto de alto riesgo: las manos divididas interactúan mediante un zapato común sin reemplazo. La auditoría debe determinar si el algoritmo modela esa dependencia de forma exacta o si utiliza una aproximación marginal.

Solicitar:
- Definición matemática del estado.
- Ecuación de recurrencia.
- Invariantes.
- Supuestos.
- Demostración o referencia técnica verificable.
- Pruebas diferenciales contra enumeración exhaustiva en zapatos pequeños.

## 6.4 Pruebas: cantidad y validez

Se citan dos archivos de pruebas con 10 y 6 pruebas, respectivamente, y se afirma un total de 16/16. También se citan nombres de pruebas concretas. No se adjuntan logs, hashes de commit, entorno ni salida de ejecución.

Verificar:
- Existencia y contenido real de ambos archivos.
- Descubrimiento efectivo de las pruebas.
- Si el proyecto usa `unittest`, `pytest` o ambos.
- Si `python -m unittest discover tests/ -v` descubre realmente todas las pruebas.
- Si hay pruebas omitidas por nombres, imports o configuración.
- Si las aserciones son independientes o replican la misma lógica del código.
- Si los tests comprueban resultados matemáticos conocidos.
- Si hay pruebas de propiedades, fuzzing, regresión y casos límite.

No describir el core como “validado al 100%” hasta disponer de evidencia suficiente.

## 6.5 Concurrencia y estado compartido

El identificador `eval_id` puede descartar resultados viejos, pero no evita que un worker lea un objeto que otro hilo está mutando.

Investigar:
- Snapshots inmutables de `TableRules`, zapato, manos y contador.
- Compartición de `CompositionShoe`.
- Thread-safety de las cachés.
- Mutaciones del motor durante evaluación.
- Cancelación o invalidación de workers.
- Cierre de ventana con tareas activas.
- Excepciones dentro de `QRunnable`.
- Emisión y consumo de señales Qt.
- Reutilización de resultados correspondientes a estados distintos.

## 6.6 Penetración extrema y zapato casi agotado

Se menciona la preocupación por composiciones con menos de 15 cartas y penetraciones superiores al 90%.

Verificar:
- Probabilidades con denominador cero.
- Estado de zapato vacío o insuficiente.
- Momento exacto de reshuffle.
- Coherencia entre cut card y cartas realmente extraídas.
- Estabilidad numérica de métricas financieras.
- Si las métricas de Kelly/RoR aceptan entradas fuera de su dominio matemático.

## 6.7 Reglas OBO y ENHC

Un documento afirma que el validador prohíbe `is_hole_card_game == True` junto con `allow_obo == True`. Verificar la regla, su justificación y si corresponde a la semántica de la aplicación. No asumir que la nomenclatura de una regla coincide con todas las variantes de reglas de casino.

## 6.8 Kelly y apuesta mínima

Se reporta que el sistema puede forzar `min_bet` cuando el bankroll es insuficiente, salvo con `allow_wong_out`. Revisar si eso puede recomendar una apuesta financieramente imposible o contraria al criterio de ventaja. El comportamiento ante edge no positivo y bankroll inferior al mínimo debe estar definido y probado.

## 6.9 GUI y memoria

La corrección de `_hand_markers` no demuestra que no existan otras fugas. Inspeccionar `CardItem`, animaciones, timers, señales, closures, widgets y referencias retenidas por escenas.

## 6.10 Dependencias y CI

Se citan como mínimos esperados PyQt6 >= 6.4.0 y NumPy >= 1.24.0, pero deben comprobarse en `requirements.txt`, archivos lock y workflows. Verificar compatibilidad real con las versiones de Python declaradas.

---

# 7. Decisiones y principios técnicos declarados

Los siguientes criterios representan las expectativas técnicas reportadas:

1. **Separación de capas:** `core/` y `training/` deben funcionar sin depender de PyQt6. La GUI consume la lógica, no la contiene.
2. **Exactitud cuantitativa:** no usar aproximaciones estocásticas cuando se exija y sea viable un cálculo analítico exacto. Si se usa una aproximación, declararla, cuantificar su error y justificarla.
3. **CD frente a TD:** conservar la composición residual cuando sea necesaria para la exactitud; no sustituir silenciosamente el motor por tablas TD.
4. **Rendimiento:** objetivo histórico inferior a 10 ms en frío para el caso de benchmark especificado. Debe tratarse como SLA condicionado a entorno y caso de prueba, no como garantía universal.
5. **Integridad de código:** no entregar funciones truncadas, placeholders ni bloques omitidos.
6. **Tipado e inmutabilidad:** preferencia declarada por dataclasses inmutables con slots y enums tipados, cuando sean apropiados.
7. **Optimización:** mantener el empaquetado binario si su beneficio se demuestra y no compromete la corrección o mantenibilidad.
8. **Trazabilidad:** cada recomendación debe vincularse a archivo, función, línea, impacto, evidencia y prueba de regresión.
9. **Auditoría independiente:** no dar por correcta una implementación porque el historial diga que fue corregida o porque pasen las pruebas existentes.
10. **Explicabilidad:** el XAI debe mostrar los cálculos reales del motor y no una explicación paralela incongruente.

---

# 8. Requisitos de auditoría matemática

La revisión no debe limitarse a estilo, linting o estructura de clases.

## 8.1 Probabilidad y composición

- Validar que las probabilidades de cada distribución sumen 1 dentro de una tolerancia justificada.
- Validar que no haya probabilidades negativas ni NaN/Inf.
- Comprobar extracción sin reemplazo.
- Comparar distribuciones contra enumeración exacta independiente.
- Validar condicionamiento bayesiano del Peek.
- Comprobar todos los estados terminales y las reglas S17/H17.
- Probar cartas visibles As y 10, y composiciones con escasez de cartas.

## 8.2 EV de acciones

Para cada acción:
- Derivar el EV desde la convención de apuesta.
- Confirmar el tratamiento de push, bust y Blackjack natural.
- Confirmar pagos 3:2, 6:5 y cualquier otro payout admitido.
- Validar Double, DAS, Split, RSA, Surrender, Insurance y OBO.
- Verificar que acciones ilegales o no aplicables se representen inequívocamente.
- Comparar resultados con casos analíticos conocidos y una implementación de referencia.

## 8.3 Split y resplit

Construir pruebas específicas para:
- Pares de Ases.
- Pares de 8.
- Cartas de valor 10.
- RSA activado y desactivado.
- DAS activado y desactivado.
- Límite de manos 1, 2 y valores superiores.
- Hit tras Split de Ases.
- Blackjack del crupier bajo ENHC.
- OBO con una y varias manos divididas.
- Zapatos pequeños que permitan enumeración exhaustiva.

## 8.4 Conteo

- Verificar tags y balance de cada sistema.
- Validar True Count con distintos números de mazos restantes.
- Probar valores negativos para `FLOOR`, `TRUNCATE` y `ROUND`.
- Confirmar precisión de sistemas fraccionarios.
- Verificar Ace Surplus y su efecto en estimación de ventaja.

## 8.5 Métricas financieras

- Derivar N₀, SCORE, Kelly y RoR desde definiciones y unidades explícitas.
- Probar edge cero y negativo.
- Probar varianza cero o degenerada.
- Probar bankroll cero, inferior al mínimo y muy alto.
- Probar límites, unidades de fichas y redondeos.
- Identificar los supuestos de independencia y estacionariedad.
- No presentar RoR como exacto si la fórmula es una aproximación bajo supuestos restrictivos.

---

# 9. Plan de auditoría del repositorio GitHub

La nueva sesión debe ejecutar el trabajo por etapas y conservar evidencia.

## Etapa 1 — Inventario y reproducibilidad

1. Inspeccionar el árbol completo del repositorio y la rama/commit auditados.
2. Identificar archivos, dependencias, configuración y puntos de entrada.
3. Revisar README, documentación y workflows.
4. Preparar entorno limpio.
5. Ejecutar pruebas existentes sin modificar el código.
6. Registrar comandos, versiones, salida, fallos y duración.

## Etapa 2 — Arquitectura y calidad estática

1. Analizar dependencias entre capas.
2. Detectar imports circulares y dependencias GUI en el core.
3. Revisar tipos, mutabilidad, interfaces y responsabilidades.
4. Ejecutar herramientas estáticas disponibles o justificar las que se incorporen.
5. Buscar `TODO`, `FIXME`, `pass`, `NotImplemented`, mocks accidentales, código muerto y placeholders. No asumir que todo `pass` es un defecto: clasificar cada aparición según contexto.
6. Revisar manejo de errores, logging y configuración.

## Etapa 3 — Auditoría matemática

Seguir las secciones 8.1–8.5. Construir oráculos independientes para casos pequeños y comparar resultados. No reutilizar el mismo algoritmo como única fuente de verdad para generar expectativas de tests.

## Etapa 4 — Rendimiento y memoria

1. Reproducir benchmark frío y caliente.
2. Medir caché, memoria y crecimiento de estado.
3. Perfilar las rutas de Hit y Split.
4. Probar múltiples configuraciones de mazos y reglas.
5. Ejecutar sesiones prolongadas de GUI.
6. Documentar hardware, entorno, datos y metodología.

## Etapa 5 — Concurrencia y GUI

1. Inspeccionar snapshots y objetos compartidos.
2. Forzar cambios rápidos de reglas y manos mientras hay evaluaciones activas.
3. Verificar que los resultados obsoletos no actualicen el HUD.
4. Verificar que los workers no lean estado mutable inconsistente.
5. Probar cierre de ventana, reset de zapato y navegación durante tareas.
6. Ejecutar pruebas gráficas en un entorno adecuado; para CI headless, comprobar si se usa `QT_QPA_PLATFORM=offscreen` y/o `pytest-qt`.

## Etapa 6 — Informe y correcciones

Cada hallazgo debe contener:
- Identificador.
- Severidad (Critical, High, Medium, Low, Informational).
- Archivo y ubicación exacta.
- Evidencia reproducible.
- Condición de activación.
- Impacto funcional, matemático, financiero, de seguridad o rendimiento.
- Causa raíz.
- Corrección recomendada.
- Prueba de regresión necesaria.
- Riesgo de la corrección.

No modificar código sin separar primero hallazgos, hipótesis y recomendaciones. No afirmar que una corrección quedó validada sin ejecutar las pruebas pertinentes.

---

# 10. Verificaciones concretas heredadas de los documentos anteriores

Comprobar directamente en GitHub:

1. Que `core/combinatorial.py` use realmente `CARDS_DATA`, shifts y masks para las operaciones binarias descritas.
2. Que `Action.INSURANCE` exista y esté integrado en la evaluación, no solo declarado.
3. Que `gui/main_window.py` implemente `_current_eval_id` o el mecanismo equivalente y que los workers transporten el identificador correcto.
4. Que `gui/components/table_view.py` gestione y retire correctamente `self._hand_markers` o su equivalente.
5. Que `gui/views/table_view_controller.py` sincronice correctamente reglas, manos, zapato y HUD.
6. Que `tests/test_ap_master_suite.py` y `tests/test_ap_metrics.py` existan y contengan las pruebas mencionadas.
7. Que las pruebas se descubran y ejecuten con el comando documentado; no asumir que el comando de `unittest` ejecuta tests escritos exclusivamente para pytest.
8. Que `requirements.txt` y los archivos de dependencias declaren versiones compatibles.
9. Que `run_app.py` y `run_gui_demo.py` no dependan de rutas absolutas locales.
10. Que el backend funcione sin inicializar PyQt6 ni requerir display.
11. Que el mecanismo de limpieza de caché no invalide datos todavía utilizados por workers.
12. Que el reset de zapato no permita que una evaluación antigua se aplique sobre una mano nueva.
13. Que las reglas ENHC/OBO estén implementadas con una semántica coherente.
14. Que las pruebas de OBO no se limiten al caso `allow_rsa=False`.
15. Que las cifras históricas de EV de 8-8 vs 10 puedan reproducirse con una configuración documentada.

---

# 11. Expectativas del propietario del proyecto

El propietario espera una revisión técnica exigente, crítica e independiente.

Prioridades declaradas:
- Exactitud matemática y probabilística.
- Integridad funcional.
- Rendimiento medible.
- Robustez ante casos límite.
- Concurrencia segura.
- Ausencia de fugas de memoria.
- Arquitectura mantenible.
- Código completo y sin truncamientos.
- Pruebas independientes y reproducibles.
- Documentación técnica y operativa.

La auditoría no debe buscar confirmar que el trabajo anterior fue correcto. Debe intentar refutar las afirmaciones del proyecto mediante análisis, pruebas y contraejemplos.

No preservar una optimización por orgullo técnico si es incorrecta. Tampoco reemplazar una optimización válida por una solución más legible sin medir el impacto.

---

# 12. Cronología consolidada de hitos reportados

| Hito | Descripción |
|---|---|
| 1 | Diseño formal CD, ecuaciones de Bellman y estados del zapato |
| 2 | Implementación de reglas, shoe, dealer y motor combinatorio |
| 3 | Identificación de problemas de latencia, Peek, Blackjack natural y Split |
| 4 | Optimización del empaquetado binario y tabla de Stand; latencia reportada de 7.2–7.5 ms |
| 5 | Correcciones de resplit de Ases y evaluación de manos blandas |
| 6 | Revisión de la frontera Surrender/Split bajo American Peek frente a ENHC |
| 7 | Incorporación y corrección de OBO para Double/Split |
| 8 | Desarrollo de conteo multinivel, True Count y Ace Surplus |
| 9 | Incorporación de N₀, SCORE, RoR y Kelly |
| 10 | Desarrollo de entrenadores de descarte, conteo rápido e índices |
| 11 | Corrección de distribución de muestreo en SpeedCountDrill |
| 12 | Desarrollo de componentes gráficos y HUD |
| 13 | Corrección reportada de fuga de marcadores en QGraphicsScene |
| 14 | Desarrollo de vistas Table, Drills, Academy y XAI |
| 15 | Integración de workers Qt y token `eval_id` |

Las fechas y los commits concretos no están disponibles en los documentos de origen. Obtenerlos del historial Git.

---

# 13. Limitaciones del presente expediente

Este documento se construyó únicamente a partir de dos textos de contexto suministrados. No se proporcionó en esta solicitud el repositorio, el código fuente, los logs de pruebas, los benchmarks ni los commits.

Por tanto, no se puede certificar:
- Que la estructura de archivos sea la actual.
- Que las clases y funciones citadas existan con esos nombres.
- Que los defectos estén efectivamente corregidos.
- Que las pruebas existan o pasen.
- Que la latencia reportada sea reproducible.
- Que el método de Split sea exacto.
- Que OBO esté implementado correctamente.
- Que el sistema esté libre de race conditions o memory leaks.
- Que las fórmulas financieras sean correctas para todos los supuestos.
- Que el proyecto sea apto para producción.

Las referencias internas como `[cite: 1]`, `[cite: 2]`, etc., aparecían en los documentos originales sin una bibliografía resoluble. Se han omitido como citas verificables. La auditoría deberá aportar referencias bibliográficas o técnicas concretas cuando utilice resultados externos.

---

# 14. Lista de control para la nueva sesión

Antes de emitir un dictamen final, la nueva sesión debe poder responder con evidencia:

- [ ] ¿Qué commit y rama se auditaron?
- [ ] ¿El inventario real coincide con la arquitectura descrita?
- [ ] ¿El core funciona sin dependencias de GUI?
- [ ] ¿El empaquetado de zapato es inyectivo y está probado por propiedades?
- [ ] ¿Las distribuciones del crupier están normalizadas y son correctas?
- [ ] ¿El Peek se condiciona exactamente en el momento correcto?
- [ ] ¿El EV de Blackjack natural respeta los payouts y pushes?
- [ ] ¿Hit y Stand coinciden con oráculos independientes?
- [ ] ¿Split y resplit son matemáticamente correctos con extracción sin reemplazo?
- [ ] ¿La técnica de Griffin conserva la exactitud bajo las reglas implementadas?
- [ ] ¿OBO se compensa exactamente una vez en todos los escenarios?
- [ ] ¿DAS, RSA, S17/H17 y Surrender están cubiertos por pruebas?
- [ ] ¿Insurance está implementado y no solo listado?
- [ ] ¿Los sistemas de conteo y True Count usan convenciones correctas?
- [ ] ¿N₀, SCORE, RoR y Kelly tienen fórmulas, unidades y supuestos documentados?
- [ ] ¿Los entrenadores generan muestras estadísticamente correctas?
- [ ] ¿La GUI evita fugas y crecimiento no acotado?
- [ ] ¿Los workers usan snapshots consistentes y no mutan estado compartido?
- [ ] ¿El token de evaluación evita resultados obsoletos sin ocultar carreras de datos?
- [ ] ¿El benchmark frío inferior a 10 ms es reproducible?
- [ ] ¿Las pruebas se ejecutan desde un entorno limpio y están integradas en CI?
- [ ] ¿Los puntos de entrada funcionan sin rutas locales?
- [ ] ¿Todos los hallazgos tienen evidencia, severidad y prueba de regresión?

---

# 15. Instrucción de transferencia a la sesión auditora

La sesión que reciba este documento debe:

1. Leerlo íntegramente antes de comenzar la revisión.
2. Solicitar o utilizar el enlace del repositorio GitHub.
3. Inspeccionar el repositorio real y fijar el commit auditado.
4. Tratar este expediente como contexto histórico, no como prueba del estado actual.
5. Priorizar las discrepancias de las secciones 6 y 10.
6. Auditar matemáticas, implementación, rendimiento, concurrencia, memoria, seguridad y mantenibilidad.
7. No declarar correcto un subsistema solo porque sus tests actuales pasen.
8. No modificar ni reescribir archivos antes de presentar los hallazgos y explicar el impacto.
9. Si se proponen correcciones, entregar archivos completos, sin placeholders ni secciones omitidas, y acompañarlos de pruebas reproducibles.
10. Generar un informe final con hallazgos priorizados, evidencia, metodología, limitaciones y estado de cada corrección.

**Criterio de aceptación:** la auditoría se considerará técnicamente sólida únicamente si sus conclusiones pueden rastrearse hasta código, ejecución reproducible, derivaciones matemáticas o fuentes técnicas identificables. Las afirmaciones heredadas de este documento no son evidencia suficiente por sí solas.

---

**FIN DEL DOCUMENTO**
