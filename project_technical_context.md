# DOCUMENTO DE TRANSFERENCIA DE CONTEXTO TÉCNICO

## QUANTITATIVE AP BLACKJACK SUITE

**Objetivo General:** Desarrollo de una suite de escritorio profesional de análisis combinatorio, simulación estocástica y entrenamiento de Blackjack Advantage Play (AP). No es un juego convencional, sino una herramienta de auditoría matemática y entrenamiento de alto rendimiento.
**Estado Conocido:** Proyecto implementado y auditado rigurosamente hasta la Fase 4B (Backend matemático exacto, Módulos AP, Interfaz PyQt6 interactiva, Entrenadores).
**Tecnologías:** Python 3.11+, PyQt6 (QGraphicsScene, QThreadPool), NumPy (conceptualmente, aunque optimizado a nivel binario puro en Python).
**Fecha de Generación:** Noviembre 2026

## 1. RECONSTRUCCIÓN HISTÓRICA DEL PROYECTO

### 1.1 Objetivo Original y Problema a Resolver

El proyecto nace de la necesidad de contar con un motor de Blackjack que calcule el Valor Esperado (EV) **exacto y dependiente de la composición (CD)** en tiempo real, sin recurrir a simulaciones de Monte Carlo ni aproximaciones Total-Dependent (TD). Busca proporcionar a jugadores de ventaja (AP) una plataforma de auditoría de decisiones y un gimnasio de habilidades (estimación visual, conteo de velocidad, desviaciones de índice).

### 1.2 Evolución Funcional

* **Fase 1:** Diseño de arquitectura y planteamiento matemático (Ecuaciones de Bellman, Cono de absorción local).

* **Fase 2:** Implementación del Core Matemático. Se superaron cuellos de botella de recursión infinita en la división de pares (Split) usando el Teorema de Expectativa Marginal de Griffin y se optimizó la memoria usando hashes `uint64` inyectivos para el zapato residual.

* **Fase 3:** Integración de Finanzas Cuantitativas (Criterio de Kelly, SCORE, N-0, Riesgo de Ruina) y sistemas de conteo (Hi-Lo, Zen, Omega II, Wong Halves).

* **Fase 4:** Desarrollo de la GUI en PyQt6. Se implementó un esquema asíncrono (`QThreadPool`) para evitar bloqueos del UI Thread durante la inducción backward, componentes de mesa interactivos y submódulos de Drills.

### 1.3 Decisiones de Arquitectura Forzadas por Auditoría

A lo largo del proyecto, el código fue sometido a severas auditorías técnicas (Tech Lead) que obligaron a rehacer implementaciones "perezosas" o subóptimas:

* Se rechazó el uso de diccionarios/tuplas simples para la memoización del zapato, obligando a empaquetar el estado en un entero de 64 bits (`pack_shoe`).

* Se exigió cumplimiento de un SLA (Service Level Agreement) de latencia en frío menor a 10 ms para resolver manos complejas con split recursivo.

* Se impuso un modelado bayesiano estricto para la regla "American Peek" (donde la distribución del crupier se condiciona a la ausencia de un Blackjack natural).

## 2. ARQUITECTURA Y FUNCIONAMIENTO

### 2.1 Estructura de Módulos

El proyecto sigue una estricta separación de responsabilidades:

1. **`core/` (Backend Matemático y Cuantitativo):**

   * `rules.py`: Inmutable `TableRules` (S17/H17, DAS, RSA, OBO, Penetración, Payouts).

   * `shoe.py`: `CompositionShoe`. Empaqueta las 10 denominaciones en operaciones bit a bit (`uint64`).

   * `dealer.py`: `DealerEngine`. Resuelve la fdp terminal del crupier (17-21, Bust, Natural BJ) con condicionamiento Hole Card.

   * `combinatorial.py`: `CompositionDependentEngine`. Ejecuta inducción hacia atrás (Backward Induction) sobre el "Cono Local de Absorción". Evalúa Stand, Hit, Double, Split, Surrender e Insurance.

   * `counting.py`: Sistemas de conteo, modos de quantización (Floor, Truncate, Round) y Ace Surplus analítico.

   * `ap_metrics.py`: Matemáticas de Don Schlesinger (SCORE, N-0, RoR) y dimensionamiento Kelly fraccional.

2. **`training/drills.py` (Lógica de Entrenamiento):**

   * Controladores puros (independientes de UI) para estimación de descarte, conteo de velocidad y dilemas del *Illustrious 18* y *Fab 4*.

3. **`gui/` (Frontend PyQt6):**

   * `components/`: `BlackjackTableView` (Mesa `QGraphicsScene`), `CardItem`, `DiscardTrayWidget`, `APHudWidget` (Telemetría y Auditoría visual).

   * `views/`: Controladores de vista (`TableViewController`, `DrillsView`, `AcademyView`, `XAIView`).

   * `main_window.py`: Integrador maestro y orquestador de concurrencia (`CDEvaluationWorker`).

### 2.2 Flujo de Información Principal (Mesa AP)

1. Se extraen cartas de `shoe` y se actualiza `counter`.

2. Se instiga una evaluación asíncrona mediante `trigger_async_evaluation`.

3. Un `CDEvaluationWorker` ejecuta `evaluate_hand_with_counting` en background.

4. El motor CD resuelve el árbol exacto operando a nivel bitwise (`CARDS_DATA`).

5. Se emite una señal `finished` con un token atómico (`eval_id`) para evitar colisiones.

6. `APHudWidget` renderiza el EV exacto de cada jugada, la ventaja del jugador, la recomendación de Kelly y la probabilidad de Bust del crupier.

## 3. HISTORIAL DE PROBLEMAS Y CORRECCIONES

### Problemas Corregidos y Validados (Categoría B)

1. **Falsa Latencia y Overhead de Tuplas:**

   * *Problema:* El test de estrés inicial simulaba un SLA < 10ms pero en realidad medía el acceso a una caché caliente. En frío, la recursión de `Hit` y `Split` tardaba > 80ms.

   * *Solución:* Reescritura del bucle de extracción de cartas en `_ev_hit_tree` y `_ev_split_standard_branch` para evitar conversiones `list()` a `tuple()`. Se implementó lógica de desplazamiento de bits (shifts/masks) directamente sobre el entero empaquetado. **SLA actual < 7.5 ms.**

2. **Bug de Manos Blandas tras División (Soft Hand Split):**

   * *Problema:* Al dividir Ases permitiendo *hit* (o robando un As tras dividir cartas comunes), la condición `is_soft = (card_val == 1)` colapsaba manos como A+5 a un 6 duro en lugar de 16 blando.

   * *Solución:* Corrección a lógica simétrica `is_soft = (card == 1 or card_val == 1)`.

3. **Inconsistencia Bayesiana en Rendición (8-8 vs 10 bajo American Peek):**

   * *Problema:* Sin considerar el *Peek*, rendirse (-0.50) supera a dividir 8s vs 10 (-0.61). Bajo American Peek (el crupier descarta tener BJ antes de que el jugador actúe), la probabilidad de *Bust* del crupier sube a 23.16%, haciendo que Dividir (-0.47) sea matemáticamente superior a Rendirse (-0.50). El test original fallaba por no anticipar esta frontera bayesiana.

   * *Solución:* Ajuste de aserciones condicionales dependientes de `is_hole_card_game`.

4. **Omisión del Reintegro en Regla OBO (Original Bets Only):**

   * *Problema:* En mesas ENHC (Europeas/Aus), si rige OBO, el jugador solo pierde su apuesta original si el crupier saca Blackjack natural al final, debiendo reintegrarse la unidad del Double o del Split. El motor penalizaba con pérdida doble (-2.0).

   * *Solución:* Inyección profunda de `prob_dealer_bj` en las ramas del árbol de división, sumando explícitamente dicho valor al EV total cuando `is_hole_card_game == False and allow_obo == True`.

5. **Fuga de Memoria en GUI (`QGraphicsScene`):**

   * *Problema:* Los indicadores elípticos de "mano activa" se instanciaban sin guardar referencia, saturando la memoria visual en rondas sucesivas.

   * *Solución:* Limpieza estricta tracking de `_hand_markers`.

6. **Carreras de Hilos (Race Conditions) en UI:**

   * *Problema:* Cambiar rápidamente las reglas de mesa disparaba múltiples hilos de evaluación que sobreescribían el HUD desordenadamente.

   * *Solución:* Inyección de `eval_id` atómico; el hilo principal descarta callbacks con IDs obsoletos.

## 4. DECISIONES TÉCNICAS Y CRITERIOS DEL PROYECTO

* **Computación CD (Composition-Dependent) Exacta vs TD (Total-Dependent):** Decisión inamovible. El motor DEBE discriminar que un 16 duro compuesto por \[10, 6\] exige pedir contra un 10, mientras que un 16 duro compuesto por \[4, 5, 7\] exige plantarse debido al agotamiento de cartas bajas.

* **Teorema de Griffin para Split:** Evita el producto cartesiano infinito de subdivisiones asumiendo extracción paralela. Aceptado como estándar de la industria matemática.

* **Quantización de True Count:** Soporte requerido para `FLOOR` (estándar Schlesinger) diferenciado de `TRUNCATE` numérico tradicional.

* **Kelly Fraccional:** Límite estricto de sugerencias de apuestas entre `min_bet` y `max_bet` y redondeo discreto a múltiplos físicos de fichas (`chip_unit`).

## 5. FUNCIONALIDADES Y REQUISITOS (INVENTARIO)

| Funcionalidad | Descripción | Estado | 
| ----- | ----- | ----- | 
| **Empaquetado de Zapato** | Conversión biyectiva de `Tuple[int]` a `uint64` | Implementada y Validada | 
| **Dealer Engine** | Árbol recursivo de crupier con soporte American Peek | Implementada y Validada | 
| **CD Eval Engine** | Evalúa Stand, Hit, Double, Split, Surrender, Insurance | Implementada y Validada | 
| **Card Counter** | Módulos multinivel y quantización fraccional de mazos | Implementada y Validada | 
| **AP Metrics** | RoR continuo, SCORE, N-0 y Kelly Sizing | Implementada y Validada | 
| **Table Controller** | Orquestación interactiva, despliegue de cartas, bankroll | Implementada y Validada | 
| **Drills Module** | Entrenamiento visual, contrarreloj, e índices matriciales | Implementada y Validada | 
| **XAI Explainer** | Desglose formal de decisiones en texto y árbol jerárquico | Implementada y Validada | 

## 6. DEFICIENCIAS Y ÁREAS QUE REQUIEREN INVESTIGACIÓN EN AUDITORÍA

Durante la auditoría del repositorio de GitHub, la nueva sesión deberá examinar los siguientes focos de riesgo:

1. **Seguridad y Precisión de la Tabla Precomputada de Stand:** Verificar que `build_stand_table` no introduzca errores de redondeo de punto flotante.

2. **Validación OBO en Split Complejo:** El parche OBO en `_ev_split_standard_branch` involucra recursiones profundas; se debe verificar que la compensación de `prob_dealer_bj` no se duplique al re-dividir (Resplit).

3. **Rendimiento del QGraphicsScene:** Confirmar que no hay memory leaks residuales en la recreación continua de `CardItem`.

4. **Caché Epímero:** Verificar que `engine.clear_cache()` se invoque adecuadamente en los cambios de ronda para evitar colapso de RAM en sesiones largas.

## 7. REQUISITOS Y EXPECTATIVAS DEL PROPIETARIO

* **Auditoría Hostil:** No se espera complacencia. Se requiere identificar cualquier grieta matemática en la inducción de Bellman o en la lógica probabilística bayesiana.

* **Cero Código Simulado:** Cualquier componente en el repositorio que contenga "TODO" o "Dummy" es una infracción crítica del proyecto.

* **Performance:** La latencia combinatoria es vital. Cualquier refactorización sugerida durante la auditoría NO debe sacrificar el empaquetado binario (`uint64`) por legibilidad si eso eleva el tiempo en frío por encima de 10ms.

## 8. CRONOLOGÍA DE CAMBIOS (Resumen Técnico)

1. Estructura de Clases CD -> 2. Pruebas Griffin y Falla Latencia -> 3. Optimización Bitwise uint64 -> 4. Adición Módulos AP (Kelly/Count) -> 5. Correcciones Bayestianas (Peek y OBO) -> 6. Estructuración PyQt6 -> 7. Identificación de fugas de GUI y desincronización Asíncrona -> 8. Implementación de Worker con `eval_id` y limpieza `QGraphicsItem`.

## 9. INFORMACIÓN QUE DEBE VERIFICARSE CONTRA GITHUB

La nueva sesión **debe obligatoriamente contrastar** lo expuesto en este documento contra la realidad del repositorio:

1. Verificar si el archivo `core/combinatorial.py` refleja la optimización a nivel binario usando la tupla estática `CARDS_DATA` (shifts/masks) o si retrocedió a iteraciones nativas de tupla.

2. Comprobar que en `tests/test_ap_metrics.py` la prueba de la regla OBO fuerza `allow_rsa=False` para asertar matemáticamente 1 sola unidad devuelta.

3. Inspeccionar `gui/views/table_view_controller.py` para asegurar que las reglas del casino interactúan fielmente con el HUD.

4. Validar que `Action.INSURANCE` forme parte del enum y se procese debidamente en la evaluación.

**FIN DEL DOCUMENTO DE TRANSFERENCIA**