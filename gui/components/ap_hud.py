from __future__ import annotations
from typing import Dict, Optional, Tuple
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QBrush, QPen
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
    QScrollArea, QSizePolicy
)
from core.ap_metrics import AdvantagePlayMetrics, KellyFraction, BetRecommendation
from core.combinatorial import DecisionEvaluation, Action
from core.dealer import DealerEngine


class TelemetryMetricCard(QFrame):
    """Widget métrico con etiqueta superior y valor destacado."""

    def __init__(self, title: str, initial_value: str = "--", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background-color: #1A1D24;
                border: 1px solid #2B2F3A;
                border-radius: 6px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        self.lbl_title = QLabel(title.upper())
        self.lbl_title.setStyleSheet("color: #90A4AE; font-size: 13px; font-weight: bold; border: none;")
        self.lbl_value = QLabel(initial_value)
        self.lbl_value.setStyleSheet("color: #FFFFFF; font-size: 20px; font-family: Consolas; font-weight: bold; border: none;")

        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_value)

    def set_value(self, text: str, color_hex: str = "#FFFFFF") -> None:
        self.lbl_value.setText(text)
        self.lbl_value.setStyleSheet(f"color: {color_hex}; font-size: 20px; font-family: Consolas; font-weight: bold; border: none;")


class DecisionAuditWidget(QFrame):
    """Bloque de auditoría cuantitativa: Acción óptima, tabla de EVs y fdp del crupier."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #14171F;
                border: 1px solid #2B2F3A;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                font-family: Consolas;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        lbl_section = QLabel("DECISION ENGINE AUDIT")
        lbl_section.setStyleSheet("color: #2979FF; font-size: 17px; font-weight: bold; letter-spacing: 0.5px;")
        layout.addWidget(lbl_section)

        # Banner Acción Óptima
        self.lbl_optimal = QLabel("OPTIMAL: --")
        self.lbl_optimal.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_optimal.setStyleSheet("""
            background-color: #162B20;
            color: #00E676;
            font-size: 15px;
            font-weight: bold;
            padding: 6px;
            border: 1px solid #00E676;
            border-radius: 4px;
        """)
        layout.addWidget(self.lbl_optimal)

        # Tabla de EV por acción
        self.ev_labels: Dict[str, Tuple[QLabel, QLabel]] = {}
        grid_ev = QGridLayout()
        grid_ev.setSpacing(4)

        actions = ["Stand", "Hit", "Double", "Split", "Surrender"]
        for idx, act in enumerate(actions):
            l_act = QLabel(act)
            l_act.setStyleSheet("color: #CFD8DC; font-size: 13px;")
            l_val = QLabel("--")
            l_val.setAlignment(Qt.AlignmentFlag.AlignRight)
            l_val.setStyleSheet("color: #90A4AE; font-size: 13px;")
            grid_ev.addWidget(l_act, idx, 0)
            grid_ev.addWidget(l_val, idx, 1)
            self.ev_labels[act] = (l_act, l_val)

        layout.addLayout(grid_ev)

        # Separador horizontal
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #2B2F3A; max-height: 1px;")
        layout.addWidget(line)

        # FDP Crupier
        lbl_dealer = QLabel("PROBABILIDADES CRUPIER")
        lbl_dealer.setStyleSheet("color: #90A4AE; font-size: 12px; font-weight: bold;")
        layout.addWidget(lbl_dealer)

        self.dealer_prob_labels: Dict[str, QLabel] = {}
        grid_d = QGridLayout()
        grid_d.setSpacing(3)

        outcomes = ["Bust", "17", "18", "19", "20", "21", "BJ"]
        for idx, out in enumerate(outcomes):
            row = idx // 2
            col = (idx % 2) * 2
            lbl_o = QLabel(f"{out}:")
            lbl_o.setStyleSheet("color: #78909C; font-size: 12px;")
            lbl_v = QLabel("--%")
            lbl_v.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: bold;")
            grid_d.addWidget(lbl_o, row, col)
            grid_d.addWidget(lbl_v, row, col + 1)
            self.dealer_prob_labels[out] = lbl_v

        layout.addLayout(grid_d)

    def update_audit(self, eval_cd: DecisionEvaluation) -> None:
        opt_action = eval_cd.optimal_action.name
        self.lbl_optimal.setText(f"OPTIMAL: {opt_action}  ({eval_cd.optimal_ev:+.4f})")

        ev_map = {
            "Stand": eval_cd.ev_stand,
            "Hit": eval_cd.ev_hit,
            "Double": eval_cd.ev_double,
            "Split": eval_cd.ev_split,
            "Surrender": eval_cd.ev_surrender,
        }

        for act_name, (l_act, l_val) in self.ev_labels.items():
            ev_val = ev_map[act_name]
            is_optimal = (act_name.upper() == opt_action)

            if ev_val is None:
                l_val.setText("N/A")
                l_val.setStyleSheet("color: #546E7A; font-size: 13px;")
                l_act.setStyleSheet("color: #546E7A; font-size: 13px;")
            else:
                l_val.setText(f"{ev_val:+.4f}")
                if is_optimal:
                    l_act.setStyleSheet("color: #00E676; font-size: 13px; font-weight: bold;")
                    l_val.setStyleSheet("color: #00E676; font-size: 13px; font-weight: bold;")
                else:
                    l_act.setStyleSheet("color: #CFD8DC; font-size: 13px;")
                    l_val.setStyleSheet("color: #90A4AE; font-size: 13px;")

        dist = eval_cd.dealer_distribution
        prob_mapping = {
            "Bust": dist.get(DealerEngine.BUST, 0.0),
            "17": dist.get(17, 0.0),
            "18": dist.get(18, 0.0),
            "19": dist.get(19, 0.0),
            "20": dist.get(20, 0.0),
            "21": dist.get(21, 0.0),
            "BJ": dist.get(DealerEngine.NATURAL_BJ, 0.0),
        }

        for out_name, lbl_v in self.dealer_prob_labels.items():
            val = prob_mapping[out_name] * 100.0
            lbl_v.setText(f"{val:.1f}%")
            if out_name == "Bust":
                lbl_v.setStyleSheet("color: #00E676; font-size: 12px; font-weight: bold;" if val >= 25.0 else "color: #FFFFFF; font-size: 12px;")


class DetailedShoeStatsWidget(QFrame):
    """Muestra el conteo exacto de cartas repartidas y restantes, más indicadores CD avanzados."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #14171F;
                border: 1px solid #2B2F3A;
                border-radius: 6px;
            }
            QLabel { font-family: Consolas; border: none; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        lbl_title = QLabel("COMPOSICIÓN EXACTA (CD)")
        lbl_title.setStyleSheet("color: #00E5FF; font-size: 14px; font-weight: bold;")
        layout.addWidget(lbl_title)

        # Indicadores avanzados
        self.lbl_p10 = QLabel("P(10): --%")
        self.lbl_ace_surplus = QLabel("Ases: --")
        
        h_indicators = QHBoxLayout()
        self.lbl_p10.setStyleSheet("color: #CFD8DC; font-size: 12px; font-weight: bold;")
        self.lbl_ace_surplus.setStyleSheet("color: #CFD8DC; font-size: 12px; font-weight: bold;")
        h_indicators.addWidget(self.lbl_p10)
        h_indicators.addWidget(self.lbl_ace_surplus)
        layout.addLayout(h_indicators)

        # Separador
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #2B2F3A; max-height: 1px;")
        layout.addWidget(line)

        # Tabla de cartas
        grid = QGridLayout()
        grid.setSpacing(4)
        
        # Headers
        h1 = QLabel("Carta")
        h2 = QLabel("Salieron")
        h3 = QLabel("Quedan")
        for h in (h1, h2, h3):
            h.setStyleSheet("color: #78909C; font-size: 11px; font-weight: bold;")
        grid.addWidget(h1, 0, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(h2, 0, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(h3, 0, 2, alignment=Qt.AlignmentFlag.AlignCenter)

        self.card_labels = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10-K"]
        self.dealt_labels: List[QLabel] = []
        self.rem_labels: List[QLabel] = []

        for row, card_name in enumerate(self.card_labels, start=1):
            l_name = QLabel(card_name)
            l_name.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: bold;")
            l_dealt = QLabel("0")
            l_dealt.setStyleSheet("color: #FF5252; font-size: 12px;")
            l_rem = QLabel("0")
            l_rem.setStyleSheet("color: #00E676; font-size: 12px;")
            
            grid.addWidget(l_name, row, 0, alignment=Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(l_dealt, row, 1, alignment=Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(l_rem, row, 2, alignment=Qt.AlignmentFlag.AlignCenter)
            
            self.dealt_labels.append(l_dealt)
            self.rem_labels.append(l_rem)

        layout.addLayout(grid)

    def update_composition(self, shoe_counts: Tuple[int, ...], total_cards: int, decks: int) -> None:
        if total_cards == 0:
            return

        # Calcular probabilidad de 10 (Umbral del Seguro es 33.3%)
        tens_rem = shoe_counts[9]
        p_10 = (tens_rem / total_cards) * 100.0
        color_p10 = "#00E676" if p_10 >= 33.33 else "#CFD8DC"
        self.lbl_p10.setText(f"P(10): {p_10:.1f}%")
        self.lbl_p10.setStyleSheet(f"color: {color_p10}; font-size: 12px; font-weight: bold;")

        # Excedente de Ases
        aces_rem = shoe_counts[0]
        expected_aces = (total_cards / 52.0) * 4.0
        ace_surplus = aces_rem - expected_aces
        color_ace = "#00E676" if ace_surplus > 0 else "#FF5252"
        self.lbl_ace_surplus.setText(f"Exceso Ases: {ace_surplus:+.1f}")
        self.lbl_ace_surplus.setStyleSheet(f"color: {color_ace}; font-size: 12px; font-weight: bold;")

        # Actualizar filas de cartas (0=A, 1..8=2..9, 9=10-K)
        initial_counts = [4 * decks] * 9 + [16 * decks]
        
        for i in range(10):
            initial = initial_counts[i]
            rem = shoe_counts[i]
            dealt = initial - rem
            
            self.dealt_labels[i].setText(str(dealt))
            self.rem_labels[i].setText(str(rem))


class ShoeCompositionBars(QWidget):
    """Histograma compacto del residuo de cartas: Ases, Bajas (2-6), Neutras (7-9) y Dieces (10s)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(65)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.ratios = {"Aces": 1.0, "Low (2-6)": 1.0, "Mid (7-9)": 1.0, "Tens (10-K)": 1.0}

    def update_composition(self, counts: Tuple[int, ...], total_cards: int) -> None:
        if total_cards == 0:
            return

        exp_a = 4.0 / 52.0
        exp_low = 20.0 / 52.0
        exp_mid = 12.0 / 52.0
        exp_tens = 16.0 / 52.0

        act_a = counts[0] / total_cards
        act_low = sum(counts[1:6]) / total_cards
        act_mid = sum(counts[6:9]) / total_cards
        act_tens = counts[9] / total_cards

        self.ratios["Aces"] = act_a / exp_a
        self.ratios["Low (2-6)"] = act_low / exp_low
        self.ratios["Mid (7-9)"] = act_mid / exp_mid
        self.ratios["Tens (10-K)"] = act_tens / exp_tens
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height()) - 16.0
        categories = list(self.ratios.keys())
        col_w = w / len(categories)

        for i, cat in enumerate(categories):
            ratio = self.ratios[cat]
            bar_h = min(h, h * (ratio / 1.5) * 0.75)
            x = i * col_w + 6.0
            y = h - bar_h

            if cat in ("Aces", "Tens (10-K)"):
                color = QColor("#00E676") if ratio >= 1.0 else QColor("#FF5252")
            else:
                color = QColor("#FF5252") if ratio > 1.0 else QColor("#00E676")

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(QRectF(x, y, col_w - 12.0, bar_h), 3.0, 3.0)

            painter.setPen(QColor("#90A4AE"))
            painter.setFont(QFont("Consolas", 14))
            painter.drawText(QRectF(i * col_w, h + 2, col_w, 14), Qt.AlignmentFlag.AlignCenter, cat)


class APHudWidget(QWidget):
    """Panel lateral de telemetría analítica, auditoría y dimensionamiento de capital."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(310)
        self.setStyleSheet("background-color: #0F1117;")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: #0F1117; width: 6px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #2B2F3A; min-height: 20px; border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover { background: #455A64; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QLabel("AP ANALYTICS HUD")
        header.setStyleSheet("color: #2979FF; font-size: 15px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(header)

        # Bloque Conteo
        grid_count = QGridLayout()
        grid_count.setSpacing(8)
        self.card_rc = TelemetryMetricCard("Running Count", "0")
        self.card_tc = TelemetryMetricCard("True Count", "0")
        grid_count.addWidget(self.card_rc, 0, 0)
        grid_count.addWidget(self.card_tc, 0, 1)
        layout.addLayout(grid_count)

        # Ventaja del Jugador
        self.card_edge = TelemetryMetricCard("Player Advantage (% Edge)", "-0.50%")
        layout.addWidget(self.card_edge)

        # Apuesta Kelly
        self.card_bet = TelemetryMetricCard("Recommended Stake (Kelly)", "$10.00")
        layout.addWidget(self.card_bet)

        # Bloque de Auditoría de Decisión
        self.audit_widget = DecisionAuditWidget(self)
        layout.addWidget(self.audit_widget)

        # Composición Detallada (Nuevo Widget)
        self.detailed_stats = DetailedShoeStatsWidget(self)
        layout.addWidget(self.detailed_stats)

        # Densidad de Residuo
        lbl_dens = QLabel("DENSIDAD DE GRUPOS (vs ESPERADO)")
        lbl_dens.setStyleSheet("color: #90A4AE; font-size: 13px; font-weight: bold; margin-top: 4px;")
        layout.addWidget(lbl_dens)

        self.shoe_bars = ShoeCompositionBars(self)
        layout.addWidget(self.shoe_bars)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def update_telemetry(
        self,
        rc: float,
        tc: int,
        edge: float,
        bet_rec: BetRecommendation,
        shoe_counts: Tuple[int, ...],
        total_cards: int,
        eval_cd: Optional[DecisionEvaluation] = None,
        decks: int = 6  # Añadido con default seguro para calcular las extraídas
    ) -> None:
        self.card_rc.set_value(f"{rc:+.1f}" if isinstance(rc, float) else f"{rc:+d}")
        tc_color = "#00E676" if tc > 0 else ("#FF5252" if tc < 0 else "#FFFFFF")
        self.card_tc.set_value(f"{tc:+d}", tc_color)

        edge_pct = edge * 100.0
        edge_color = "#00E676" if edge > 0.0 else "#FF5252"
        self.card_edge.set_value(f"{edge_pct:+.2f}%", edge_color)

        if bet_rec.should_wong_out:
            self.card_bet.set_value("WONG OUT ($0)", "#FFD600")
        else:
            self.card_bet.set_value(f"${bet_rec.recommended_stake:.2f}", "#00E676" if edge > 0 else "#FFFFFF")

        self.shoe_bars.update_composition(shoe_counts, total_cards)
        self.detailed_stats.update_composition(shoe_counts, total_cards, decks)

        if eval_cd is not None:
            self.audit_widget.update_audit(eval_cd)