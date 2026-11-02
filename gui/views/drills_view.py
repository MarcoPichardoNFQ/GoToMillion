from __future__ import annotations
import time
from typing import Optional
import random
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QPushButton,
    QLabel, QFrame, QSlider, QDoubleSpinBox, QComboBox, QLineEdit,
    QGridLayout, QMessageBox
)

from core.counting import CardCounter, CountingSystem, RoundingMode
from core.combinatorial import Action
from training.drills import (
    DeckEstimationDrill, SpeedCountDrill, IndexDeviationDrill,
    DEVIATION_CATALOG, DeviationTrial
)
from gui.components.table_view import DiscardTrayWidget


class DrillsView(QWidget):
    """Gimnasio Cuantitativo con 3 sub-entrenadores especializados."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.speed_drill = SpeedCountDrill(system=CountingSystem.HI_LO)
        self.deck_drill = DeckEstimationDrill(total_decks=6, resolution=0.5)
        self.index_drill = IndexDeviationDrill(DEVIATION_CATALOG)
        
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Selector de Entrenador
        nav_frame = QFrame(self)
        nav_frame.setStyleSheet("background-color: #14171F; border: 1px solid #2B2F3A; border-radius: 6px;")
        n_layout = QHBoxLayout(nav_frame)
        n_layout.setContentsMargins(8, 6, 8, 6)

        self.btn_sub_speed = QPushButton("1. Conteo Rápido / Cancelación")
        self.btn_sub_deck = QPushButton("2. Estimación de Descarte")
        self.btn_sub_index = QPushButton("3. Laboratorio de Índices (I18 / F4)")

        for idx, btn in enumerate((self.btn_sub_speed, self.btn_sub_deck, self.btn_sub_index)):
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent; color: #90A4AE; font-family: Consolas;
                    font-size: 12px; font-weight: bold; padding: 6px 14px; border: none; border-radius: 4px;
                }
                QPushButton:checked {
                    background-color: #2979FF; color: #FFFFFF;
                }
            """)
            btn.clicked.connect(lambda _, i=idx: self._switch_drill(i))
            n_layout.addWidget(btn)

        self.btn_sub_speed.setChecked(True)
        layout.addWidget(nav_frame)

        self.stack = QStackedWidget(self)
        layout.addWidget(self.stack, 1)

        self._build_speed_drill_ui()
        self._build_deck_drill_ui()
        self._build_index_drill_ui()

    def _switch_drill(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate((self.btn_sub_speed, self.btn_sub_deck, self.btn_sub_index)):
            btn.setChecked(i == idx)

    # -------------------------------------------------------------------------
    # Sub-Vista A: Conteo de Velocidad
    # -------------------------------------------------------------------------
    def _build_speed_drill_ui(self) -> None:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(8, 8, 8, 8)
        l.setSpacing(10)

        # Barra de Controles
        ctrl = QFrame()
        ctrl.setStyleSheet("background-color: #1A1D24; border: 1px solid #2B2F3A; border-radius: 6px; padding: 6px;")
        c_layout = QHBoxLayout(ctrl)

        c_layout.addWidget(QLabel("Velocidad:"))
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(["0.5s", "0.8s", "1.0s", "1.5s", "2.0s", "3.0s", "5.0s"])
        self.combo_speed.setCurrentIndex(2)
        c_layout.addWidget(self.combo_speed)

        c_layout.addWidget(QLabel("Modo:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Carta Individual", "Pares Cancelables"])
        c_layout.addWidget(self.combo_mode)

        self.btn_speed_start = QPushButton("Iniciar Racha")
        self.btn_speed_start.setStyleSheet("background-color: #00E676; color: #0F1117; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        self.btn_speed_start.clicked.connect(self._toggle_speed_drill)
        c_layout.addWidget(self.btn_speed_start)

        l.addWidget(ctrl)
        # Panel de referencia Hi-Lo
        self.lbl_hilo_reference = QLabel(
            "<b>SISTEMA HI-LO</b><br>"
            "<span style='color:#69F0AE;'>+1</span> &nbsp; 2, 3, 4, 5, 6"
            "&nbsp;&nbsp; | &nbsp;&nbsp;"
            "<span style='color:#CFD8DC;'>0</span> &nbsp; 7, 8, 9"
            "&nbsp;&nbsp; | &nbsp;&nbsp;"
            "<span style='color:#FF8A80;'>-1</span> &nbsp; 10, J, Q, K, A"
        )

        self.lbl_hilo_reference.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_hilo_reference.setStyleSheet("""
            QLabel {
                background-color: #14171F;
                color: #CFD8DC;
                border: 1px solid #2B2F3A;
                border-radius: 6px;
                padding: 8px;
                font-family: Consolas;
                font-size: 12px;
            }
        """)

        l.addWidget(self.lbl_hilo_reference)
        # Display Central de Cartas
        self.display_card_frame = QFrame()
        self.display_card_frame.setStyleSheet("background-color: #0A0C10; border: 2px solid #2B2F3A; border-radius: 8px;")
        d_layout = QVBoxLayout(self.display_card_frame)
        d_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
  
        # Contador de cartas procesadas (parte superior)
        self.lbl_cards_processed = QLabel("Cartas procesadas: 0")
        self.lbl_cards_processed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_cards_processed.setStyleSheet("""
            color: #90A4AE;
            font-size: 16px;
            font-family: Helvetica;
            font-weight: normal;
            border: none;
        """)

        # Display de cartas
        self.lbl_card_display = QLabel("LISTO")
        self.lbl_card_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_card_display.setStyleSheet("""
            color: #455A64;
            font-size: 54px;
            font-family: Helvetica;
            font-weight: bold;
            border: none;
        """)

        # Orden visual: contador arriba, cartas abajo
        d_layout.addWidget(self.lbl_cards_processed)
        d_layout.addWidget(self.lbl_card_display)
        l.addWidget(self.display_card_frame, 1)

        # Input y Verificación
        inp_frame = QFrame()
        inp_frame.setStyleSheet("background-color: #1A1D24; border: 1px solid #2B2F3A; border-radius: 6px; padding: 8px;")
        i_layout = QHBoxLayout(inp_frame)

        self.inp_rc = QLineEdit()
        self.inp_rc.setPlaceholderText("Ingresa el Running Count final...")
        self.inp_rc.setStyleSheet("background-color: #14171F; color: #FFFFFF; font-family: Consolas; font-size: 14px; padding: 6px; border: 1px solid #2B2F3A;")
        i_layout.addWidget(self.inp_rc)

        self.btn_verify_rc = QPushButton("Validar Conteo")
        self.btn_verify_rc.setStyleSheet("background-color: #2979FF; color: #FFFFFF; font-weight: bold; padding: 6px 16px; border-radius: 4px;")
        self.btn_verify_rc.clicked.connect(self._verify_speed_count)
        i_layout.addWidget(self.btn_verify_rc)

        l.addWidget(inp_frame)
        self.stack.addWidget(w)

        self.speed_timer = QTimer(self)
        self.speed_timer.timeout.connect(self._tick_speed_card)
        self.cards_shown_count = 0

    def _toggle_speed_drill(self) -> None:
        if self.speed_timer.isActive():
            self.speed_timer.stop()
            self.btn_speed_start.setText("Iniciar Racha")
            self.btn_speed_start.setStyleSheet("background-color: #00E676; color: #0F1117; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        else:
            self.speed_drill.reset()
            self.cards_shown_count = 0
            self.lbl_cards_processed.setText("Cartas procesadas: 0")
            self.inp_rc.clear()
            interval_ms = int(float(self.combo_speed.currentText().replace("s", "")) * 1000)
            self.speed_timer.start(interval_ms)
            self.btn_speed_start.setText("Detener")
            self.btn_speed_start.setStyleSheet("background-color: #FF5252; color: #FFFFFF; font-weight: bold; padding: 6px 14px; border-radius: 4px;")

    def _tick_speed_card(self) -> None:
        self.cards_shown_count += 1
        is_pair = (self.combo_mode.currentIndex() == 1)

        if is_pair:
            c1, c2 = self.speed_drill.generate_pair(cancelable_probability=0.6)
            s1 = "A" if c1.val == 1 else str(c1.val)
            s2 = "A" if c2.val == 1 else str(c2.val)
            self.lbl_card_display.setText(f"{s1}{c1.suit}   {s2}{c2.suit}")
            color = "#D32F2F" if (c1.suit in "♥♦" or c2.suit in "♥♦") else "#CFD8DC"
        else:
            c = self.speed_drill.generate_single_card()
            s = "A" if c.val == 1 else str(c.val)
            self.lbl_card_display.setText(f"{s}{c.suit}")
            color = "#D32F2F" if c.suit in "♥♦" else "#CFD8DC"

        self.lbl_card_display.setStyleSheet(f"color: {color}; font-size: 64px; font-family: Helvetica; font-weight: bold;")

        # Actualizar contador de cartas procesadas
        self.lbl_cards_processed.setText(
            f"Cartas procesadas: {self.cards_shown_count}"
        )
    def _verify_speed_count(self) -> None:
        if not self.inp_rc.text().strip():
            return

        try:
            user_rc = float(self.inp_rc.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Formato", "Ingresa un número entero o decimal válido.")
            return

        exact_rc = self.speed_drill.counter.running_count
        diff = user_rc - exact_rc

        if diff == 0:
            QMessageBox.information(self, "Resultado", f"¡EXACTO! Running Count = {exact_rc:+.1f}\nCartas procesadas: {self.cards_shown_count}")
        else:
            QMessageBox.critical(self, "Resultado", f"DESVÍO: Ingresaste {user_rc:+.1f}, Real era {exact_rc:+.1f} (Error: {diff:+.1f})\nCartas procesadas: {self.cards_shown_count}")

    # -------------------------------------------------------------------------
    # Sub-Vista B: Estimación de Mazos
    # -------------------------------------------------------------------------
    def _build_deck_drill_ui(self) -> None:
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(12, 12, 12, 12)
        l.setSpacing(14)

        self.drill_tray = DiscardTrayWidget(total_decks=6, penetration=0.75)
        self.drill_tray.setFixedWidth(140)
        l.addWidget(self.drill_tray)

        panel = QFrame()
        panel.setStyleSheet("background-color: #1A1D24; border: 1px solid #2B2F3A; border-radius: 6px; padding: 12px;")
        p_layout = QVBoxLayout(panel)
        p_layout.setSpacing(10)

        lbl_title = QLabel("ESTIMACIÓN VISUAL DE BANDEJA DE DESCARTE")
        lbl_title.setStyleSheet("color: #00E676; font-size: 14px; font-weight: bold; font-family: Consolas;")
        p_layout.addWidget(lbl_title)

        self.btn_new_tray = QPushButton("Generar Zapato / Descarte Aleatorio")
        self.btn_new_tray.setStyleSheet("background-color: #2979FF; color: #FFFFFF; font-weight: bold; padding: 8px; border-radius: 4px;")
        self.btn_new_tray.clicked.connect(self._generate_deck_trial)
        p_layout.addWidget(self.btn_new_tray)

        self.lbl_tray_info = QLabel("Running Count Simulado: +6.0")
        self.lbl_tray_info.setStyleSheet("color: #CFD8DC; font-family: Consolas; font-size: 12px;")
        p_layout.addWidget(self.lbl_tray_info)

        input_box = QHBoxLayout()
        input_box.addWidget(QLabel("Tu estimación (Mazos Restantes):"))
        self.spin_estimate = QDoubleSpinBox()
        self.spin_estimate.setRange(0.25, 6.0)
        self.spin_estimate.setSingleStep(0.25)
        self.spin_estimate.setValue(3.0)
        self.spin_estimate.setStyleSheet("background-color: #14171F; color: #00E676; font-family: Consolas; font-size: 14px; padding: 4px;")
        input_box.addWidget(self.spin_estimate)
        p_layout.addLayout(input_box)

        self.btn_check_estimate = QPushButton("Comprobar Estimación")
        self.btn_check_estimate.setStyleSheet("background-color: #00E676; color: #0F1117; font-weight: bold; padding: 8px; border-radius: 4px;")
        self.btn_check_estimate.clicked.connect(self._check_deck_estimate)
        p_layout.addWidget(self.btn_check_estimate)

        self.lbl_estimate_feedback = QLabel("")
        self.lbl_estimate_feedback.setStyleSheet("font-family: Consolas; font-size: 12px; color: #90A4AE; padding-top: 10px;")
        p_layout.addWidget(self.lbl_estimate_feedback)

        p_layout.addStretch()
        l.addWidget(panel, 1)
        self.stack.addWidget(w)
        self._cur_cards_remaining = 156
        self._cur_rc = 6.0

    def _generate_deck_trial(self) -> None:
        cards_dealt, cards_rem, _ = self.deck_drill.generate_trial()
        self._cur_cards_remaining = cards_rem
        self.drill_tray.set_discard_state(cards_dealt)
        self._cur_rc = random.choice([-8.0, -5.0, -2.0, 3.0, 6.0, 9.0])
        self.lbl_tray_info.setText(f"Running Count Simulado: {self._cur_rc:+.1f}")
        self.lbl_estimate_feedback.setText("")

    def _check_deck_estimate(self) -> None:
        user_est = self.spin_estimate.value()
        res = self.deck_drill.evaluate_estimate(
            self._cur_cards_remaining, user_est, self._cur_rc, RoundingMode.FLOOR
        )

        col = "#00E676" if res.is_acceptable else "#FF5252"
        self.lbl_estimate_feedback.setText(
            f"Mazos Reales: {res.actual_decks_remaining:.2f}D ({res.actual_cards_remaining} cartas)\n"
            f"Tu Estimación: {user_est:.2f}D  (Error: {res.deck_error:.2f}D)\n"
            f"True Count Real: {res.actual_true_count:+d}  |  True Count Inducido: {res.erroneous_true_count:+d}\n"
            f"Distorsión de TC: {res.tc_distortion} punto(s)  -> "
            f"{'¡ACEPTABLE!' if res.is_acceptable else 'ERROR CRÍTICO'}"
        )
        self.lbl_estimate_feedback.setStyleSheet(f"font-family: Consolas; font-size: 12px; color: {col}; font-weight: bold; line-height: 160%;")

    # -------------------------------------------------------------------------
    # Sub-Vista C: Laboratorio de Desviaciones (Index Lab)
    # -------------------------------------------------------------------------
    def _build_index_drill_ui(self) -> None:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(12, 12, 12, 12)
        l.setSpacing(10)

        self.card_scenario = QFrame()
        self.card_scenario.setStyleSheet("background-color: #1A1D24; border: 1px solid #2B2F3A; border-radius: 8px; padding: 16px;")
        s_layout = QVBoxLayout(self.card_scenario)

        self.lbl_scen_title = QLabel("ESCENARIO: --")
        self.lbl_scen_title.setStyleSheet("color: #2979FF; font-size: 18px; font-weight: bold; font-family: Consolas;")
        self.lbl_scen_tc = QLabel("TRUE COUNT ACTUAL: --")
        self.lbl_scen_tc.setStyleSheet("color: #FFD600; font-size: 20px; font-weight: bold; font-family: Consolas; margin: 8px 0;")

        s_layout.addWidget(self.lbl_scen_title)
        s_layout.addWidget(self.lbl_scen_tc)
        l.addWidget(self.card_scenario)

        btn_grid = QGridLayout()
        btn_grid.setSpacing(8)

        self.index_action_btns = {}
        actions = [
            (Action.STAND, "STAND", 0, 0),
            (Action.HIT, "HIT", 0, 1),
            (Action.DOUBLE, "DOUBLE", 0, 2),
            (Action.SPLIT, "SPLIT", 1, 0),
            (Action.SURRENDER, "SURRENDER", 1, 1),
            (Action.INSURANCE, "INSURANCE", 1, 2),
        ]

        for act, label, row, col in actions:
            btn = QPushButton(label)
            btn.setFixedHeight(38)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #14171F; color: #CFD8DC; border: 1px solid #2B2F3A;
                    border-radius: 4px; font-family: Consolas; font-weight: bold; font-size: 12px;
                }
                QPushButton:hover { background-color: #2979FF; color: #FFFFFF; }
            """)
            btn.clicked.connect(lambda _, a=act: self._check_index_answer(a))
            btn_grid.addWidget(btn, row, col)
            self.index_action_btns[act] = btn

        l.addLayout(btn_grid)

        self.lbl_index_feedback = QLabel("")
        self.lbl_index_feedback.setStyleSheet("font-family: Consolas; font-size: 13px; color: #90A4AE; padding: 8px;")
        l.addWidget(self.lbl_index_feedback)

        btn_next = QPushButton("Siguiente Dilema")
        btn_next.setStyleSheet("background-color: #00E676; color: #0F1117; font-weight: bold; padding: 10px; border-radius: 4px;")
        btn_next.clicked.connect(self._next_index_trial)
        l.addWidget(btn_next)

        l.addStretch()
        self.stack.addWidget(w)
        self._cur_trial: Optional[DeviationTrial] = None
        self._next_index_trial()

    def _next_index_trial(self) -> None:
        self._cur_trial = self.index_drill.generate_trial()
        scen = self._cur_trial.scenario
        self.lbl_scen_title.setText(f"DILEMA: {scen.hand_name}  ({scen.deviation_type.name})")
        self.lbl_scen_tc.setText(f"TRUE COUNT ACTUAL: {self._cur_trial.simulated_tc:+d}")
        self.lbl_index_feedback.setText("")

    def _check_index_answer(self, user_action: Action) -> None:
        if not self._cur_trial:
            return

        correct = (user_action == self._cur_trial.correct_action)
        scen = self._cur_trial.scenario

        if correct:
            self.lbl_index_feedback.setText(f"¡CORRECTO! Acción elegida: {user_action.name}\n{scen.explanation}")
            self.lbl_index_feedback.setStyleSheet("color: #00E676; font-family: Consolas; font-size: 13px; font-weight: bold; line-height: 160%;")
        else:
            self.lbl_index_feedback.setText(
                f"FALLO: Elegiste {user_action.name}. La acción correcta era {self._cur_trial.correct_action.name}.\n"
                f"{scen.explanation}"
            )
            self.lbl_index_feedback.setStyleSheet("color: #FF5252; font-family: Consolas; font-size: 13px; font-weight: bold; line-height: 160%;")
