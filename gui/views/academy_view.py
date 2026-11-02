from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QPushButton,
    QLabel,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QDoubleSpinBox,
    QSpinBox,
    QComboBox,
    QScrollArea,
)

from core.rules import TableRules
from core.shoe import CompositionShoe
from core.combinatorial import CompositionDependentEngine, Action
from core.ap_metrics import AdvantagePlayMetrics, KellyFraction
from training.drills import DEVIATION_CATALOG


class AcademyView(QWidget):
    """Academia Cuantitativa y de Teoría de Juegos con matriz de estrategia básica dinámica."""

    def __init__(self, rules: TableRules, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.rules = rules
        self.engine = CompositionDependentEngine(rules)
        self._init_ui()

    def update_rules(self, new_rules: TableRules) -> None:
        self.rules = new_rules
        self.engine = CompositionDependentEngine(new_rules)
        self._generate_dynamic_matrix()
        self._recalculate_risk_lab()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        nav_frame = QFrame(self)
        nav_frame.setStyleSheet(
            "background-color: #14171F; border: 1px solid #2B2F3A; border-radius: 6px;"
        )
        n_layout = QHBoxLayout(nav_frame)
        n_layout.setContentsMargins(8, 6, 8, 6)

        self.btn_sec1 = QPushButton("1. Fundamentos & Matemáticas")
        self.btn_sec2 = QPushButton("2. Matriz Estrategia Básica (Dinámica)")
        self.btn_sec3 = QPushButton("3. Matrices de Desviación (I18 / F4)")
        self.btn_sec4 = QPushButton("4. Laboratorio de Riesgo & Kelly")

        for idx, btn in enumerate(
            (self.btn_sec1, self.btn_sec2, self.btn_sec3, self.btn_sec4)
        ):
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent; color: #90A4AE; font-family: Consolas;
                    font-size: 13px; font-weight: bold; padding: 6px 12px; border: none; border-radius: 4px;
                }
                QPushButton:checked { background-color: #2979FF; color: #FFFFFF; }
            """)
            btn.clicked.connect(lambda _, i=idx: self._switch_section(i))
            n_layout.addWidget(btn)

        self.btn_sec1.setChecked(True)
        layout.addWidget(nav_frame)

        self.stack = QStackedWidget(self)
        layout.addWidget(self.stack, 1)

        self._build_sec1_ui()
        self._build_sec2_ui()
        self._build_sec3_ui()
        self._build_sec4_ui()

    def _switch_section(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(
            (self.btn_sec1, self.btn_sec2, self.btn_sec3, self.btn_sec4)
        ):
            btn.setChecked(i == idx)

    # -------------------------------------------------------------------------
    # Sección 1: Fundamentos y Matemáticas
    # -------------------------------------------------------------------------
    def _build_sec1_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")

        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(12)

        content = (
            (
                "1. NATURALEZA ESTOCÁSTICA DEL BLACKJACK",
                "A diferencia de la ruleta o los dados (Procesos de Bernoulli independientes con reemplazo), el Blackjack "
                "es un Proceso Estocástico Finito dependiente de la composición sin reemplazo. Cada carta extraída "
                "altera irreversiblemente la densidad de probabilidad de las extracciones futuras (Efecto de Retirada).",
            ),
            (
                "2. ESPERANZA MATEMÁTICA Y VENTAJA DE LA CASA",
                "La ventaja de la casa proviene fundamentalmente de la regla de simultaneidad: si el jugador se pasa, "
                "pierde su apuesta de inmediato, incluso si el crupier se pasa posteriormente en la misma ronda. "
                "Bajo estrategia básica perfecta en 6 mazos S17 DAS, la casa retiene una ventaja de solo ~0.50%.",
            ),
            (
                "3. TEORÍA DE CONTEO Y DENSIDAD DE DIECES",
                "Las cartas altas (10, J, Q, K y Ases) benefician al jugador porque: (a) aumentan la probabilidad de cobrar 3:2 "
                "por Blackjack natural, (b) aumentan el EV de las jugadas de doblar (Double Down), y (c) fuerzan al crupier a pasarse "
                "cuando tiene cartas débiles (2 a 6). El Running Count mide este desbalance.",
            ),
            (
                "4. FALACIA DEL JUGADOR Y SISTEMAS DE PROGRESIÓN",
                "Estrategias como la Martingala asumen erróneamente que una racha de pérdidas incrementa la probabilidad de victoria "
                "inmediata. Dichas progresiones no alteran el EV negativo de cada ronda y provocan inevitablemente la ruina exponencial "
                "al topar con el límite de apuesta de la mesa (Max Bet) o agotar el bankroll.",
            ),
        )

        for title, text in content:
            box = QFrame()
            box.setStyleSheet(
                "background-color: #1A1D24; border: 1px solid #2B2F3A; border-radius: 6px; padding: 12px;"
            )
            b_layout = QVBoxLayout(box)
            lbl_t = QLabel(title)
            lbl_t.setStyleSheet(
                "color: #00E676; font-size: 13px; font-weight: bold; font-family: Consolas;"
            )
            lbl_p = QLabel(text)
            lbl_p.setWordWrap(True)
            lbl_p.setStyleSheet("color: #CFD8DC; font-size: 12px; line-height: 150%;")
            b_layout.addWidget(lbl_t)
            b_layout.addWidget(lbl_p)
            l.addWidget(box)

        l.addStretch()
        scroll.setWidget(w)
        self.stack.addWidget(scroll)

    # -------------------------------------------------------------------------
    # Sección 2: Matriz Dinámica de Estrategia Básica
    # -------------------------------------------------------------------------
    def _build_sec2_ui(self) -> None:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(4, 4, 4, 4)

        header = QLabel(
            "MATRIZ DE ESTRATEGIA BÁSICA GENERADA DINÁMICAMENTE POR COMPOSICIÓN (ZAPATO FRESCO)"
        )
        header.setStyleSheet(
            "color: #2979FF; font-size: 12px; font-weight: bold; font-family: Consolas; margin-bottom: 4px;"
        )
        l.addWidget(header)

        self.table_matrix = QTableWidget()
        self.table_matrix.setStyleSheet("""
            QTableWidget {
                background-color: #14171F; gridline-color: #2B2F3A;
                font-family: Consolas; font-size: 13px; color: #FFFFFF;
            }
            QHeaderView::section {
                background-color: #1A1D24; color: #90A4AE; font-weight: bold;
                border: 1px solid #2B2F3A; font-family: Consolas;
            }
        """)
        l.addWidget(self.table_matrix)
        self.stack.addWidget(w)
        self._generate_dynamic_matrix()

    def _generate_dynamic_matrix(self) -> None:
        shoe = CompositionShoe.from_decks(self.rules.decks)
        upcards = [2, 3, 4, 5, 6, 7, 8, 9, 10, 1]
        player_rows = [
            ("Dura 16", (10, 6)),
            ("Dura 15", (10, 5)),
            ("Dura 14", (9, 5)),
            ("Dura 13", (8, 5)),
            ("Dura 12", (10, 2)),
            ("Dura 11", (6, 5)),
            ("Dura 10", (6, 4)),
            ("Dura 9", (5, 4)),
            ("Dura 8", (5, 3)),
            ("Blanda A,7 (18)", (1, 7)),
            ("Blanda A,6 (17)", (1, 6)),
            ("Blanda A,5 (16)", (1, 5)),
            ("Blanda A,4 (15)", (1, 4)),
            ("Par 8,8", (8, 8)),
            ("Par A,A", (1, 1)),
            ("Par 10,10", (10, 10)),
            ("Par 9,9", (9, 9)),
            ("Par 7,7", (7, 7)),
            ("Par 6,6", (6, 6)),
        ]

        self.table_matrix.setRowCount(len(player_rows))
        self.table_matrix.setColumnCount(len(upcards))
        self.table_matrix.setHorizontalHeaderLabels(
            [str(u) if u != 1 else "A" for u in upcards]
        )
        self.table_matrix.setVerticalHeaderLabels([r[0] for r in player_rows])

        action_colors = {
            Action.STAND: "#D32F2F",  # Rojo
            Action.HIT: "#388E3C",  # Verde
            Action.DOUBLE: "#1976D2",  # Azul
            Action.SPLIT: "#0097A7",  # Cyan
            Action.SURRENDER: "#F57C00",  # Naranja
        }

        for r_idx, (_, hand) in enumerate(player_rows):
            for c_idx, u in enumerate(upcards):
                eval_cd = self.engine.evaluate_decision(hand, u, shoe)
                act = eval_cd.optimal_action
                act_str = act.name[:2]
                item = QTableWidgetItem(act_str)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                bg_col = action_colors.get(act, "#455A64")
                item.setBackground(QColor(bg_col))
                self.table_matrix.setItem(r_idx, c_idx, item)

        self.table_matrix.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

    # -------------------------------------------------------------------------
    # Sección 3: Matrices de Desviación
    # -------------------------------------------------------------------------
    def _build_sec3_ui(self) -> None:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(4, 4, 4, 4)

        header = QLabel(
            "TABLAS CANÓNICAS DE ÍNDICES DE DON SCHLESINGER (ILLUSTRIOUS 18 Y FAB 4)"
        )
        header.setStyleSheet(
            "color: #FFD600; font-size: 12px; font-weight: bold; font-family: Consolas; margin-bottom: 4px;"
        )
        l.addWidget(header)

        table = QTableWidget()
        table.setRowCount(len(DEVIATION_CATALOG))
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(
            [
                "ID",
                "Mano vs Crupier",
                "Índice TC",
                "Básica",
                "Desviación",
                "Explicación",
            ]
        )
        table.setStyleSheet("""
            QTableWidget {
                background-color: #14171F; gridline-color: #2B2F3A;
                font-family: Consolas; font-size: 13px; color: #CFD8DC;
            }
            QHeaderView::section {
                background-color: #1A1D24; color: #90A4AE; font-weight: bold;
                border: 1px solid #2B2F3A; font-family: Consolas;
            }
        """)

        for r_idx, scen in enumerate(DEVIATION_CATALOG):
            table.setItem(r_idx, 0, QTableWidgetItem(scen.scenario_id))
            table.setItem(r_idx, 1, QTableWidgetItem(scen.hand_name))
            tc_str = f"{scen.comparison} {scen.index_tc:+d}"
            table.setItem(r_idx, 2, QTableWidgetItem(tc_str))
            table.setItem(r_idx, 3, QTableWidgetItem(scen.basic_action.name))
            item_dev = QTableWidgetItem(scen.deviation_action.name)
            item_dev.setForeground(QColor("#00E676"))
            table.setItem(r_idx, 4, item_dev)
            table.setItem(r_idx, 5, QTableWidgetItem(scen.explanation))

        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        l.addWidget(table)
        self.stack.addWidget(w)

    # -------------------------------------------------------------------------
    # Sección 4: Laboratorio de Riesgo y Kelly
    # -------------------------------------------------------------------------
    def _build_sec4_ui(self) -> None:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(12)

        lbl = QLabel("CALCULADORA DE RIESGO, DIMENSIONAMIENTO DE KELLY Y SCORE")
        lbl.setStyleSheet(
            "color: #00E676; font-size: 13px; font-weight: bold; font-family: Consolas;"
        )
        l.addWidget(lbl)

        box = QFrame()
        box.setStyleSheet(
            "background-color: #1A1D24; border: 1px solid #2B2F3A; border-radius: 6px; padding: 10px;"
        )
        b_layout = QHBoxLayout(box)

        b_layout.addWidget(QLabel("Bankroll ($):"))
        self.spin_bankroll = QDoubleSpinBox()
        self.spin_bankroll.setRange(1000, 1_000_000)
        self.spin_bankroll.setValue(10_000)
        self.spin_bankroll.setSingleStep(1000)
        self.spin_bankroll.valueChanged.connect(self._recalculate_risk_lab)
        b_layout.addWidget(self.spin_bankroll)

        b_layout.addWidget(QLabel("Kelly:"))
        self.combo_kelly = QComboBox()
        self.combo_kelly.addItems(
            ["Full Kelly (1.0)", "Half Kelly (0.5)", "Quarter Kelly (0.25)"]
        )
        self.combo_kelly.setCurrentIndex(1)
        self.combo_kelly.currentIndexChanged.connect(self._recalculate_risk_lab)
        b_layout.addWidget(self.combo_kelly)

        l.addWidget(box)

        self.res_card = QFrame()
        self.res_card.setStyleSheet(
            "background-color: #14171F; border: 1px solid #2B2F3A; border-radius: 6px; padding: 14px;"
        )
        r_layout = QVBoxLayout(self.res_card)

        self.lbl_score_val = QLabel("SCORE: --")
        self.lbl_n0_val = QLabel("N-0: -- manos")
        self.lbl_ror_val = QLabel("Riesgo de Ruina (RoR): --%")
        self.lbl_win_val = QLabel("Ganancia / 100 manos: $--")

        for lbl_w in (
            self.lbl_score_val,
            self.lbl_n0_val,
            self.lbl_ror_val,
            self.lbl_win_val,
        ):
            lbl_w.setStyleSheet(
                "color: #CFD8DC; font-family: Consolas; font-size: 14px; font-weight: bold; margin: 3px 0;"
            )
            r_layout.addWidget(lbl_w)

        l.addWidget(self.res_card)
        l.addStretch()
        self.stack.addWidget(w)
        self._recalculate_risk_lab()

    def _recalculate_risk_lab(self) -> None:
        b = self.spin_bankroll.value()
        schlesinger_data = [
            (-2, 0.185, -0.0145, 1.0),
            (-1, 0.134, -0.0095, 1.0),
            (0, 0.230, -0.0045, 1.0),
            (1, 0.165, 0.0005, 1.0),
            (2, 0.115, 0.0055, 2.0),
            (3, 0.072, 0.0105, 4.0),
            (4, 0.044, 0.0155, 8.0),
            (5, 0.027, 0.0205, 12.0),
            (6, 0.028, 0.0260, 12.0),
        ]
        metrics = AdvantagePlayMetrics.evaluate_game_spread(
            schlesinger_data, bankroll=b
        )

        self.lbl_score_val.setText(f"SCORE (Schlesinger): {metrics.score:.2f}")
        self.lbl_score_val.setStyleSheet(
            "color: #00E676; font-family: Consolas; font-size: 14px; font-weight: bold;"
        )
        self.lbl_n0_val.setText(
            f"N-0 (Manos para superar varianza): {metrics.n_zero:,.0f} manos"
        )
        self.lbl_ror_val.setText(
            f"Riesgo de Ruina (RoR): {metrics.risk_of_ruin * 100.0:.2f}%"
        )
        self.lbl_win_val.setText(
            f"Ganancia Esperada / 100 manos: ${metrics.hourly_win_rate_100:.2f}"
        )
