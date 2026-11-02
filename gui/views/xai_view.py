from __future__ import annotations
from typing import Optional, Tuple
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QTextEdit,
    QScrollArea
)

from core.rules import TableRules
from core.shoe import CompositionShoe
from core.combinatorial import CompositionDependentEngine, DecisionEvaluation, Action
from core.dealer import DealerEngine


class XAIView(QWidget):
    """Módulo de Inteligencia Artificial Explicable (XAI) con árbol de decisión y justificación formal."""

    def __init__(self, rules: TableRules, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.rules = rules
        self.engine = CompositionDependentEngine(rules)
        self.shoe = CompositionShoe.from_decks(rules.decks)

        self._init_ui()

    def update_rules(self, new_rules: TableRules) -> None:
        self.rules = new_rules
        self.engine = CompositionDependentEngine(new_rules)
        self.shoe = CompositionShoe.from_decks(new_rules.decks)
        self.run_xai_audit()

    def set_scenario(self, player_cards: Tuple[int, ...], upcard: int) -> None:
        self.run_xai_audit()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        ctrl_frame = QFrame(self)
        ctrl_frame.setStyleSheet("background-color: #1A1D24; border: 1px solid #2B2F3A; border-radius: 6px; padding: 8px;")
        c_layout = QHBoxLayout(ctrl_frame)

        c_layout.addWidget(QLabel("Mano Jugador:"))
        self.combo_hand = QComboBox()
        self.combo_hand.addItems([
            "16 Duro [10, 6]", "16 Duro [4, 5, 7]", "12 Duro [10, 2]", "12 Duro [3, 4, 5]",
            "Par de 8s [8, 8]", "Par de Ases [A, A]", "15 Duro [10, 5]", "11 Duro [6, 5]"
        ])
        c_layout.addWidget(self.combo_hand)

        c_layout.addWidget(QLabel("Carta Crupier:"))
        self.combo_upcard = QComboBox()
        self.combo_upcard.addItems(["10", "A", "9", "8", "7", "6", "5", "4", "3", "2"])
        c_layout.addWidget(self.combo_upcard)

        self.btn_run = QPushButton("Auditar Mano (XAI)")
        self.btn_run.setStyleSheet("background-color: #00E676; color: #0F1117; font-weight: bold; padding: 6px 16px; border-radius: 4px;")
        self.btn_run.clicked.connect(self.run_xai_audit)
        c_layout.addWidget(self.btn_run)

        layout.addWidget(ctrl_frame)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")

        content_w = QWidget()
        self.content_layout = QVBoxLayout(content_w)
        self.content_layout.setSpacing(12)

        self.table_tree = QTableWidget()
        self.table_tree.setColumnCount(4)
        self.table_tree.setHorizontalHeaderLabels(["Acción Legal", "Valor Esperado (EV)", "Diferencia vs Óptima", "Estado"])
        self.table_tree.setStyleSheet("""
            QTableWidget {
                background-color: #14171F; gridline-color: #2B2F3A;
                font-family: Consolas; font-size: 12px; color: #FFFFFF;
            }
            QHeaderView::section {
                background-color: #1A1D24; color: #90A4AE; font-weight: bold; border: 1px solid #2B2F3A;
            }
        """)
        self.table_tree.setFixedHeight(170)
        self.table_tree.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        #la linea de Arriba es para que no se pueda editar la tabla, da error porque no se puede editar, pero si se puede seleccionar, y eso es lo que queremos
        #
        self.content_layout.addWidget(self.table_tree)

        self.txt_proof = QTextEdit()
        self.txt_proof.setReadOnly(True)
        self.txt_proof.setStyleSheet("""
            QTextEdit {
                background-color: #0A0C10; color: #CFD8DC; font-family: Consolas;
                font-size: 12px; border: 1px solid #2B2F3A; border-radius: 6px; padding: 12px; line-height: 160%;
            }
        """)
        self.txt_proof.setMinimumHeight(240)
        self.content_layout.addWidget(self.txt_proof)

        scroll.setWidget(content_w)
        layout.addWidget(scroll, 1)

        self.run_xai_audit()

    def run_xai_audit(self) -> None:
        hand_text = self.combo_hand.currentText()
        up_text = self.combo_upcard.currentText()

        hand_map = {
            "16 Duro [10, 6]": (10, 6),
            "16 Duro [4, 5, 7]": (4, 5, 7),
            "12 Duro [10, 2]": (10, 2),
            "12 Duro [3, 4, 5]": (3, 4, 5),
            "Par de 8s [8, 8]": (8, 8),
            "Par de Ases [A, A]": (1, 1),
            "15 Duro [10, 5]": (10, 5),
            "11 Duro [6, 5]": (6, 5),
        }
        player_cards = hand_map[hand_text]
        upcard = 1 if up_text == "A" else int(up_text)

        shoe = CompositionShoe.from_decks(self.rules.decks).remove(upcard)
        for c in player_cards:
            shoe = shoe.remove(c)

        eval_cd = self.engine.evaluate_decision(player_cards, upcard, shoe)

        options = [
            ("Stand", eval_cd.ev_stand),
            ("Hit", eval_cd.ev_hit),
            ("Double", eval_cd.ev_double),
            ("Split", eval_cd.ev_split),
            ("Surrender", eval_cd.ev_surrender),
        ]
        valid_options = [(act, ev) for act, ev in options if ev is not None]
        valid_options.sort(key=lambda item: item[1], reverse=True)

        self.table_tree.setRowCount(len(valid_options))
        for idx, (act_name, ev_val) in enumerate(valid_options):
            diff = ev_val - eval_cd.optimal_ev
            is_best = (idx == 0)

            item_act = QTableWidgetItem(act_name)
            item_ev = QTableWidgetItem(f"{ev_val:+.4f}")
            item_diff = QTableWidgetItem("0.0000 (ÓPTIMA)" if is_best else f"{diff:+.4f}")
            item_status = QTableWidgetItem("RECOMENDADA" if is_best else "SUB-ÓPTIMA")

            if is_best:
                for it in (item_act, item_ev, item_diff, item_status):
                    it.setForeground(QColor("#00E676"))
                    it.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
            else:
                item_diff.setForeground(QColor("#FF5252"))

            self.table_tree.setItem(idx, 0, item_act)
            self.table_tree.setItem(idx, 1, item_ev)
            self.table_tree.setItem(idx, 2, item_diff)
            self.table_tree.setItem(idx, 3, item_status)

        dist = eval_cd.dealer_distribution
        p_bust = dist.get(DealerEngine.BUST, 0.0) * 100.0
        p_20 = dist.get(20, 0.0) * 100.0

        proof_text = (
            f"=== DEMOSTRACIÓN FORMAL DE OPTIMIZACIÓN CUANTITATIVA ===\n\n"
            f"1. ESTADO DEL ZAPATO Y CONDICIONAMIENTO:\n"
            f"   - Crupier muestra: {up_text} | Mano evaluada: {player_cards}\n"
            f"   - Reglas de mesa activas: S17={not self.rules.dealer_hits_soft_17}, Peek={self.rules.is_hole_card_game}, DAS={self.rules.allow_das}\n"
            f"   - Probabilidad exacta de pasarse del Crupier (Bust Rate): {p_bust:.2f}%\n"
            f"   - Probabilidad de total 20 del Crupier: {p_20:.2f}%\n\n"
            f"2. INDUCCIÓN HACIA ATRÁS (BACKWARD INDUCTION):\n"
            f"   - La acción '{eval_cd.optimal_action.name}' maximiza el retorno financiero esperado: EV = {eval_cd.optimal_ev:+.4f}.\n"
            f"   - Stand EV rinde: {eval_cd.ev_stand:+.4f}. Se deduce por sumatoria directa U(total, d) sobre la fdp terminal.\n"
            f"   - Hit EV rinde: {eval_cd.ev_hit:+.4f}. Resuelto por backward induction sobre el cono de absorción local.\n\n"
            f"3. JUSTIFICACIÓN MATEMÁTICA Y EFECTO COMPOSICIÓN (GRIFFIN):\n"
            f"   - La mano evaluada contiene cartas que alteran la densidad del mazo residual.\n"
            f"   - Toda decisión alternativa a '{eval_cd.optimal_action.name}' impone una penalización inmediata de capital "
            f"     degradando la tasa de crecimiento exponencial en la rampa de Kelly."
        )
        self.txt_proof.setText(proof_text)
