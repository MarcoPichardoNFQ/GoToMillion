from __future__ import annotations
from dataclasses import dataclass
import random
import time
from typing import Dict, List, Optional, Tuple, Any

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QGridLayout,
    QSizePolicy,
    QDoubleSpinBox
)
from core.ap_metrics import AdvantagePlayMetrics, KellyFraction

from core.rules import TableRules
from core.shoe import CompositionShoe
from core.combinatorial import CompositionDependentEngine, DecisionEvaluation, Action
from core.counting import CardCounter
from gui.components.table_view import BlackjackTableView, DiscardTrayWidget
from gui.components.ap_hud import APHudWidget


@dataclass
class PlayerHandState:
    cards: List[Tuple[int, str, bool]]
    bet: float
    is_settled: bool = False
    is_doubled: bool = False
    is_surrendered: bool = False
    result_text: str = ""
    net_payout: float = 0.0

    @property
    def values_tuple(self) -> Tuple[int, ...]:
        return tuple(c[0] for c in self.cards)

    @property
    def total(self) -> int:
        h = 0
        a = 0
        for c in self.cards:
            if c[0] == 1:
                a += 1
                h += 11
            else:
                h += c[0]
        while h > 21 and a > 0:
            h -= 10
            a -= 1
        return h

    @property
    def is_soft(self) -> bool:
        h = sum(11 if c[0] == 1 else c[0] for c in self.cards)
        return any(c[0] == 1 for c in self.cards) and h <= 21

    @property
    def is_blackjack(self) -> bool:
        return (
            len(self.cards) == 2
            and self.total == 21
            and any(c[0] == 1 for c in self.cards)
            and any(c[0] == 10 for c in self.cards)
        )

    @property
    def is_bust(self) -> bool:
        return self.total > 21


class TableViewController(QWidget):
    """
    Controlador interactivo de mesa de Blackjack con Decision Coach en tiempo real,
    auditoría cuantitativa de EV, panel de precisión acumulada y atajos de teclado.
    """

    state_changed = pyqtSignal()

    def __init__(
        self,
        rules: TableRules,
        shoe: CompositionShoe,
        counter: CardCounter,
        engine: CompositionDependentEngine,
        hud: APHudWidget,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.rules = rules
        self.shoe = shoe
        self.counter = counter
        self.engine = engine
        self.hud = hud

        self.suits = ("♠", "♥", "♦", "♣")
        self.base_bet: float = 25.0
        self.bankroll: float = 10_000.0
        
        self.peak_bankroll: float = 10_000.0
        self.max_drawdown: float = 0.0

        # Estado del juego
        self.dealer_cards: List[Tuple[int, str, bool]] = []
        self.player_hands: List[PlayerHandState] = []
        self.active_hand_idx: int = 0
        self.in_round: bool = False
        self.insurance_offered: bool = False
        
        self.rounds_played: int = 0
        self.session_profit: float = 0.0
        
        self.current_round_data: Dict[str, Any] = {}

        # Estadísticas de entrenamiento
        self.stats_total_decisions: int = 0
        self.stats_optimal_decisions: int = 0
        self.stats_hard_total: int = 0
        self.stats_hard_opt: int = 0
        self.stats_soft_total: int = 0
        self.stats_soft_opt: int = 0
        self.stats_pairs_total: int = 0
        self.stats_pairs_opt: int = 0
        self.stats_total_ev_loss: float = 0.0

        self._build_ui()
        self._setup_shortcuts()
        self.reset_shoe_and_counter()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # BARRA SUPERIOR DE ESTADÍSTICAS
        self.stats_bar = QFrame(self)
        self.stats_bar.setStyleSheet(
            "background-color: #14171F; border-bottom: 1px solid #2B2F3A; padding: 4px;"
        )
        s_layout = QHBoxLayout(self.stats_bar)
        s_layout.setContentsMargins(12, 4, 12, 4)

        self.lbl_stats_global = QLabel("PRECISIÓN: 100.0% (0/0)")
        self.lbl_stats_global.setStyleSheet("color: #00E676; font-family: Consolas; font-weight: bold; font-size: 13px;")
        
        self.lbl_stats_rounds = QLabel("Rondas: 0")
        self.lbl_stats_rounds.setStyleSheet("color: #2979FF; font-family: Consolas; font-weight: bold; font-size: 13px;")
        
        self.lbl_stats_hard = QLabel("Duras: 0/0")
        self.lbl_stats_soft = QLabel("Blandas: 0/0")
        self.lbl_stats_pairs = QLabel("Pares: 0/0")
        for lbl in (self.lbl_stats_hard, self.lbl_stats_soft, self.lbl_stats_pairs):
            lbl.setStyleSheet("color: #90A4AE; font-family: Consolas; font-size: 13px;")
        
        self.lbl_stats_peak = QLabel("Peak: $10000 | DD: 0.0%")
        self.lbl_stats_peak.setStyleSheet("color: #AB47BC; font-family: Consolas; font-weight: bold; font-size: 13px;")

        self.lbl_stats_profit = QLabel("Balance: $0.00")
        self.lbl_stats_profit.setStyleSheet("color: #CFD8DC; font-family: Consolas; font-weight: bold; font-size: 13px;")

        self.lbl_stats_loss = QLabel("Pérdida EV: 0.0000u ($0.00)")
        self.lbl_stats_loss.setStyleSheet("color: #FF5252; font-family: Consolas; font-size: 13px;")

        s_layout.addWidget(self.lbl_stats_global)
        s_layout.addSpacing(12)
        s_layout.addWidget(self.lbl_stats_rounds)
        s_layout.addSpacing(12)
        s_layout.addWidget(self.lbl_stats_hard)
        s_layout.addWidget(self.lbl_stats_soft)
        s_layout.addWidget(self.lbl_stats_pairs)
        s_layout.addSpacing(16)
        s_layout.addWidget(self.lbl_stats_peak)
        s_layout.addStretch()
        s_layout.addWidget(self.lbl_stats_profit)
        s_layout.addSpacing(12)
        s_layout.addWidget(self.lbl_stats_loss)
        layout.addWidget(self.stats_bar)

        # MESA Y DESCARTE
        table_container = QWidget()
        tc_layout = QHBoxLayout(table_container)
        tc_layout.setContentsMargins(0, 0, 0, 0)
        tc_layout.setSpacing(0)

        self.table_view = BlackjackTableView(self)
        self.discard_tray = DiscardTrayWidget(
            total_decks=self.rules.decks, penetration=self.rules.penetration
        )
        tc_layout.addWidget(self.table_view, 1)
        tc_layout.addWidget(self.discard_tray)
        layout.addWidget(table_container, 1)

        # PANEL DESPLEGABLE DE REFERENCIA DE ESTRATEGIA (OCULTO POR DEFECTO)
        self.strategy_panel = QFrame(self)
        self.strategy_panel.setVisible(False)
        self.strategy_panel.setStyleSheet(
            "background-color: #0F1D2B; border: 1px solid #2979FF; border-radius: 4px;"
        )
        sp_layout = QVBoxLayout(self.strategy_panel)
        sp_layout.setContentsMargins(12, 12, 12, 12)
        
        lbl_strat_title = QLabel("📚 REFERENCIA DE ESTRATEGIA (POSICIÓN EN MATRIZ)")
        lbl_strat_title.setStyleSheet("color: #2979FF; font-weight: bold; font-size: 13px; border: none;")
        self.lbl_strat_hand = QLabel("Tu Mano: -- | Total: --")
        self.lbl_strat_dealer = QLabel("Carta Crupier: --")
        self.lbl_strat_action = QLabel("🎯 Acción Óptima en Matriz (CD): --")
        
        for l in [self.lbl_strat_hand, self.lbl_strat_dealer, self.lbl_strat_action]:
            l.setStyleSheet("color: #CFD8DC; font-family: Consolas; font-size: 13px; border: none;")
            sp_layout.addWidget(l)
        sp_layout.insertWidget(0, lbl_strat_title)
        
        layout.addWidget(self.strategy_panel)

        # BANNER DE INFORMACIÓN Y COACH
        self.banner_frame = QFrame(self)
        self.banner_frame.setFixedHeight(38)
        self.banner_frame.setStyleSheet(
            "background-color: #1A1D24; border: 1px solid #2B2F3A; border-radius: 4px;"
        )
        b_layout = QHBoxLayout(self.banner_frame)
        b_layout.setContentsMargins(12, 0, 12, 0)

        self.lbl_banner = QLabel("DECISION COACH ACTIVO — Realiza una jugada para auditar")
        self.lbl_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_banner.setStyleSheet(
            "color: #90A4AE; font-family: Consolas; font-weight: bold; font-size: 12px; border: none;"
        )
        b_layout.addWidget(self.lbl_banner, 1)

        self.btn_toggle_strategy = QPushButton("📖 Mostrar Estrategia")
        self.btn_toggle_strategy.setCheckable(True)
        self.btn_toggle_strategy.setStyleSheet("""
            QPushButton { 
                background-color: #1A1D24; color: #2979FF; border: 1px solid #2979FF; 
                border-radius: 4px; padding: 4px 10px; font-weight: bold; font-size: 11px;
            }
            QPushButton:checked { background-color: #2979FF; color: #FFFFFF; }
            QPushButton:hover { background-color: #2979FF; color: #FFFFFF; }
        """)
        self.btn_toggle_strategy.clicked.connect(self._toggle_strategy)
        b_layout.addWidget(self.btn_toggle_strategy)

        layout.addWidget(self.banner_frame)

        # BOTONERA DE ACCIONES
        self.controls_bar = QFrame(self)
        self.controls_bar.setStyleSheet(
            "background-color: #14171F; border-top: 1px solid #2B2F3A; padding: 6px;"
        )
        c_layout = QHBoxLayout(self.controls_bar)
        c_layout.setContentsMargins(12, 6, 12, 6)
        c_layout.setSpacing(8)

        # CONFIGURADOR DE APUESTA
        lbl_bet = QLabel("Apuesta:")
        lbl_bet.setStyleSheet("color: #CFD8DC; font-family: Consolas; font-weight: bold;")
        self.spin_bet = QDoubleSpinBox()
        self.spin_bet.setRange(1.0, 10_000.0)
        self.spin_bet.setValue(25.0)
        self.spin_bet.setSingleStep(5.0)
        self.spin_bet.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #0A0C10; color: #FFD600; font-family: Consolas; font-weight: bold;
                border: 1px solid #2B2F3A; border-radius: 4px; padding: 4px; font-size: 14px;
            }
        """)
        c_layout.addWidget(lbl_bet)
        c_layout.addWidget(self.spin_bet)
        c_layout.addSpacing(16)

        self.btn_deal = QPushButton("Deal [D]")
        self.btn_hit = QPushButton("Hit [H]")
        self.btn_stand = QPushButton("Stand [S]")
        self.btn_double = QPushButton("Double [2]")
        self.btn_split = QPushButton("Split [P]")
        self.btn_surrender = QPushButton("Surrender [R]")
        self.btn_insurance = QPushButton("Insurance [I]")

        buttons = [
            (self.btn_deal, "#2979FF", self.deal_round),
            (self.btn_hit, "#00E676", lambda: self.handle_user_action(Action.HIT)),
            (self.btn_stand, "#FF5252", lambda: self.handle_user_action(Action.STAND)),
            (self.btn_double, "#FFD600", lambda: self.handle_user_action(Action.DOUBLE)),
            (self.btn_split, "#00E5FF", lambda: self.handle_user_action(Action.SPLIT)),
            (self.btn_surrender, "#FF9100", lambda: self.handle_user_action(Action.SURRENDER)),
            (self.btn_insurance, "#AB47BC", lambda: self.handle_user_action(Action.INSURANCE)),
        ]

        for btn, col, slot in buttons:
            btn.setFixedHeight(34)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #1A1D24; color: {col}; border: 1px solid {col};
                    border-radius: 4px; font-family: Consolas; font-weight: bold; padding: 0 12px;
                }}
                QPushButton:hover {{ background-color: {col}; color: #0F1117; }}
                QPushButton:disabled {{ background-color: #12141A; color: #455A64; border: 1px solid #2B2F3A; }}
            """)
            btn.clicked.connect(slot)
            c_layout.addWidget(btn)

        layout.addWidget(self.controls_bar)
        self._update_button_states()

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("D"), self, self.deal_round)
        QShortcut(QKeySequence("H"), self, lambda: self.handle_user_action(Action.HIT))
        QShortcut(QKeySequence("S"), self, lambda: self.handle_user_action(Action.STAND))
        QShortcut(QKeySequence("2"), self, lambda: self.handle_user_action(Action.DOUBLE))
        QShortcut(QKeySequence("P"), self, lambda: self.handle_user_action(Action.SPLIT))
        QShortcut(QKeySequence("R"), self, lambda: self.handle_user_action(Action.SURRENDER))
        QShortcut(QKeySequence("I"), self, lambda: self.handle_user_action(Action.INSURANCE))

    def _toggle_strategy(self, checked: bool) -> None:
        self.strategy_panel.setVisible(checked)
        self.btn_toggle_strategy.setText("📖 Ocultar Estrategia" if checked else "📖 Mostrar Estrategia")

    def full_reset(self) -> None:
        self.stats_total_decisions = 0
        self.stats_optimal_decisions = 0
        self.stats_hard_total = 0
        self.stats_hard_opt = 0
        self.stats_soft_total = 0
        self.stats_soft_opt = 0
        self.stats_pairs_total = 0
        self.stats_pairs_opt = 0
        self.stats_total_ev_loss = 0.0
        
        self.rounds_played = 0
        self.session_profit = 0.0
        self.peak_bankroll = self.bankroll
        self.max_drawdown = 0.0
        
        self.in_round = False
        self.dealer_cards.clear()
        self.player_hands.clear()
        self.table_view.set_dealer_cards([])
        self.table_view.set_player_hands([])
        self.table_view.history_overlay.setRowCount(0)
        
        self.lbl_banner.setText("DECISION COACH ACTIVO — Realiza una jugada para auditar")
        self.banner_frame.setStyleSheet("background-color: #1A1D24; border: 1px solid #2B2F3A; border-radius: 4px;")
        self.lbl_banner.setStyleSheet("color: #90A4AE; font-family: Consolas; font-weight: bold; font-size: 12px; border: none;")
        
        self.lbl_stats_global.setText("PRECISIÓN: 100.0% (0/0)")
        self.lbl_stats_global.setStyleSheet("color: #00E676; font-family: Consolas; font-weight: bold; font-size: 13px;")
        self.lbl_stats_rounds.setText("Rondas: 0")
        self.lbl_stats_hard.setText("Duras: 0/0")
        self.lbl_stats_soft.setText("Blandas: 0/0")
        self.lbl_stats_pairs.setText("Pares: 0/0")
        self.lbl_stats_loss.setText("Pérdida EV: 0.0000u ($0.00)")
        
        self._update_profit_display()
        
        self.lbl_strat_hand.setText("Tu Mano: -- | Total: --")
        self.lbl_strat_dealer.setText("Carta Crupier: --")
        self.lbl_strat_action.setText("🎯 Acción Óptima en Matriz (CD): --")
        
        self.reset_shoe_and_counter()
        self._update_button_states()
        
        bet_rec = AdvantagePlayMetrics.recommend_bet(
            bankroll=self.bankroll, true_count=0, base_edge=-0.005, kelly_fraction=KellyFraction.HALF
        )
        self.hud.update_telemetry(0.0, 0, -0.005, bet_rec, self.shoe.counts, self.shoe.total_cards, None, self.rules.decks)

    def _update_profit_display(self) -> None:
        if self.session_profit > 0:
            color = "#00E676"
            text = f"Balance: +${self.session_profit:.2f}"
        elif self.session_profit < 0:
            color = "#FF5252"
            text = f"Balance: -${abs(self.session_profit):.2f}"
        else:
            color = "#CFD8DC"
            text = f"Balance: $0.00"
            
        self.lbl_stats_profit.setText(text)
        self.lbl_stats_profit.setStyleSheet(f"color: {color}; font-family: Consolas; font-weight: bold; font-size: 13px;")
        self.lbl_stats_peak.setText(f"Peak: ${self.peak_bankroll:.0f} | DD: {self.max_drawdown:.1f}%")

    def reset_shoe_and_counter(self) -> None:
        self.shoe = CompositionShoe.from_decks(self.rules.decks)
        self.counter.reset()
        self.discard_tray.set_discard_state(0)
        self.discard_tray.total_decks = self.rules.decks

    def draw_card(self, face_up: bool = True) -> Tuple[int, str, bool]:
        if self.shoe.is_cut_card_reached(self.rules.penetration) or self.shoe.total_cards < 15:
            self.reset_shoe_and_counter()

        val = random.choices(range(1, 11), weights=self.shoe.counts)[0]
        suit = random.choice(self.suits)
        self.shoe = self.shoe.remove(val)
        if face_up:
            self.counter.update(val)
        self.discard_tray.set_discard_state(self.shoe.initial_total_cards - self.shoe.total_cards)
        return (val, suit, face_up)

    def _evaluate_and_update_hud_internal(self) -> Tuple[DecisionEvaluation, int, float, BetRecommendation]:
        cur_hand = self.player_hands[self.active_hand_idx]
        known_counts = list(self.shoe.counts)
        if self.in_round and len(self.dealer_cards) == 2 and not self.dealer_cards[1][2]:
            hole_val = self.dealer_cards[1][0]
            known_counts[hole_val - 1] += 1
            
        known_shoe = CompositionShoe(tuple(known_counts), initial_total_cards=self.shoe.initial_total_cards)
        eval_cd, tc, edge = self.engine.evaluate_hand_with_counting(
            cur_hand.values_tuple, self.dealer_cards[0][0], known_shoe, self.counter
        )
        bet_rec = AdvantagePlayMetrics.recommend_bet(
            bankroll=self.bankroll, true_count=tc, base_edge=edge - (tc * 0.005), kelly_fraction=KellyFraction.HALF
        )
        self.hud.update_telemetry(
            rc=self.counter.running_count, tc=tc, edge=edge, bet_rec=bet_rec, 
            shoe_counts=known_shoe.counts, total_cards=known_shoe.total_cards, eval_cd=eval_cd, decks=self.rules.decks
        )
        
        if self.active_hand_idx < len(self.player_hands):
            prefix = "Blanda (Soft)" if cur_hand.is_soft else "Dura (Hard)"
            if len(cur_hand.cards) == 2 and cur_hand.cards[0][0] == cur_hand.cards[1][0]:
                prefix = "Par (Pair)"
            dealer_up = self.dealer_cards[0][0]
            up_str = "A" if dealer_up == 1 else str(dealer_up)
            
            self.lbl_strat_hand.setText(f"Tu Mano: {prefix} | Total: {cur_hand.total}")
            self.lbl_strat_dealer.setText(f"Carta Crupier: {up_str}")
            self.lbl_strat_action.setText(f"🎯 Acción Óptima en Matriz (CD): {eval_cd.optimal_action.name}")
        
        return eval_cd, tc, edge, bet_rec

    def _evaluate_and_update_hud(self) -> DecisionEvaluation:
        eval_cd, _, _, _ = self._evaluate_and_update_hud_internal()
        return eval_cd

    def deal_round(self) -> None:
        if self.in_round:
            return

        self.base_bet = self.spin_bet.value()
        self.in_round = True
        self.insurance_offered = False
        self.rounds_played += 1
        self.lbl_stats_rounds.setText(f"Rondas: {self.rounds_played}")

        c1_p = self.draw_card(True)
        c1_d = self.draw_card(True)
        c2_p = self.draw_card(True)
        c2_d = self.draw_card(False)

        self.dealer_cards = [c1_d, c2_d]
        self.player_hands = [PlayerHandState(cards=[c1_p, c2_p], bet=self.base_bet)]
        self.active_hand_idx = 0

        self._refresh_table_display()

        if c1_d[0] == 1:
            self.insurance_offered = True

        eval_cd, tc, edge, bet_rec = self._evaluate_and_update_hud_internal()
        
        self.current_round_data = {
            'tc': tc,
            'rec_bet': bet_rec.recommended_stake,
            'ev_multiplier': eval_cd.optimal_ev,
            'error': False,
            'first_action': None,
            'initial_hand': self.player_hands[0].total
        }

        dealer_has_bj = (c1_d[0] == 1 and c2_d[0] == 10) or (c1_d[0] == 10 and c2_d[0] == 1)
        player_has_bj = self.player_hands[0].is_blackjack

        if self.rules.is_hole_card_game and (dealer_has_bj or player_has_bj):
            self.dealer_cards[1] = (c2_d[0], c2_d[1], True)
            self.counter.update(c2_d[0])
            self._refresh_table_display()
            self._settle_all_hands()
            return

        self._update_button_states()

    def _get_dealer_visible_total_str(self) -> str:
        visible = [c for c in self.dealer_cards if c[2]]
        if not visible:
            return ""
        h = sum(11 if c[0] == 1 else c[0] for c in visible)
        a = sum(1 for c in visible if c[0] == 1)
        while h > 21 and a > 0:
            h -= 10
            a -= 1
        is_soft = (a > 0 and any(c[0]==1 for c in visible))
        if is_soft:
            raw = sum(c[0] for c in visible)
            if h != raw + 10:
                is_soft = False
        prefix = "Suave " if is_soft else ""
        return f"{prefix}{h}"

    def _refresh_table_display(self) -> None:
        dealer_str = self._get_dealer_visible_total_str()
        self.table_view.set_dealer_cards(self.dealer_cards, dealer_str)
        
        totals = []
        for h in self.player_hands:
            if h.is_bust:
                totals.append(f"BUST ({h.total})")
                continue
            prefix = "Suave " if h.is_soft else "Dura "
            if len(h.cards) == 2 and h.cards[0][0] == h.cards[1][0]:
                prefix = "Par "
            totals.append(f"{prefix}{h.total}")
            
        hands_tuples = [[c for c in h.cards] for h in self.player_hands]
        self.table_view.set_player_hands(hands_tuples, active_idx=self.active_hand_idx, totals=totals)

    def handle_user_action(self, user_action: Action) -> None:
        if not self.in_round:
            return
            
        if not self.current_round_data.get('first_action'):
            self.current_round_data['first_action'] = user_action.name

        cur_hand = self.player_hands[self.active_hand_idx]
        
        known_counts = list(self.shoe.counts)
        if len(self.dealer_cards) == 2 and not self.dealer_cards[1][2]:
            hole_val = self.dealer_cards[1][0]
            known_counts[hole_val - 1] += 1
        known_shoe = CompositionShoe(tuple(known_counts), initial_total_cards=self.shoe.initial_total_cards)
        
        eval_cd = self.engine.evaluate_decision(cur_hand.values_tuple, self.dealer_cards[0][0], known_shoe)
        opt_act = eval_cd.optimal_action

        ev_map = {
            Action.STAND: eval_cd.ev_stand, Action.HIT: eval_cd.ev_hit, Action.DOUBLE: eval_cd.ev_double,
            Action.SPLIT: eval_cd.ev_split, Action.SURRENDER: eval_cd.ev_surrender, Action.INSURANCE: 0.0,
        }

        user_ev = ev_map.get(user_action, -1.0)
        user_ev = user_ev if user_ev is not None else -1.0
        ev_loss = max(0.0, eval_cd.optimal_ev - user_ev)
        is_optimal = user_action == opt_act
        
        if not is_optimal:
            self.current_round_data['error'] = True

        self._record_decision_stats(cur_hand, is_optimal, ev_loss)

        if is_optimal:
            self.lbl_banner.setText("DECISIÓN ÓPTIMA (+0.00 EV)")
            self.banner_frame.setStyleSheet("background-color: #162B20; border: 1px solid #00E676; border-radius: 4px;")
            self.lbl_banner.setStyleSheet("color: #00E676; font-family: Consolas; font-weight: bold; font-size: 12px; border: none;")
        else:
            dollar_loss = ev_loss * cur_hand.bet
            self.lbl_banner.setText(f"ERROR: Óptima era {opt_act.name}. Coste: -{ev_loss:.4f}u (-${dollar_loss:.2f} EV)")
            self.banner_frame.setStyleSheet("background-color: #2B1616; border: 1px solid #FF5252; border-radius: 4px;")
            self.lbl_banner.setStyleSheet("color: #FF5252; font-family: Consolas; font-weight: bold; font-size: 12px; border: none;")

        if user_action == Action.HIT:
            cur_hand.cards.append(self.draw_card(True))
            if cur_hand.is_bust:
                cur_hand.is_settled = True
                self._advance_to_next_hand()
        elif user_action == Action.STAND:
            cur_hand.is_settled = True
            self._advance_to_next_hand()
        elif user_action == Action.DOUBLE:
            cur_hand.is_doubled = True
            cur_hand.bet *= 2.0
            cur_hand.cards.append(self.draw_card(True))
            cur_hand.is_settled = True
            self._advance_to_next_hand()
        elif user_action == Action.SPLIT:
            c1, c2 = cur_hand.cards[0], cur_hand.cards[1]
            h1 = PlayerHandState(cards=[c1, self.draw_card(True)], bet=cur_hand.bet)
            h2 = PlayerHandState(cards=[c2, self.draw_card(True)], bet=cur_hand.bet)
            self.player_hands[self.active_hand_idx] = h1
            self.player_hands.insert(self.active_hand_idx + 1, h2)
        elif user_action == Action.SURRENDER:
            cur_hand.is_surrendered = True
            cur_hand.is_settled = True
            self._advance_to_next_hand()
        elif user_action == Action.INSURANCE:
            self.insurance_offered = False

        self._refresh_table_display()
        if self.in_round:
            self._evaluate_and_update_hud()
        self._update_button_states()

    def _advance_to_next_hand(self) -> None:
        self.active_hand_idx += 1
        if self.active_hand_idx >= len(self.player_hands):
            self._play_dealer_turn()

    def _play_dealer_turn(self) -> None:
        h_card = self.dealer_cards[1]
        self.dealer_cards[1] = (h_card[0], h_card[1], True)
        self.counter.update(h_card[0])
        self._refresh_table_display()

        any_alive = any(not (h.is_bust or h.is_surrendered) for h in self.player_hands)

        if any_alive:
            while True:
                d_tot = self._dealer_total()
                d_soft = self._dealer_is_soft()

                if d_tot < 17:
                    self.dealer_cards.append(self.draw_card(True))
                    self._refresh_table_display()
                elif d_tot == 17 and d_soft and self.rules.dealer_hits_soft_17:
                    self.dealer_cards.append(self.draw_card(True))
                    self._refresh_table_display()
                else:
                    break

        self._settle_all_hands()

    def _dealer_total(self) -> int:
        h = sum(11 if c[0] == 1 else c[0] for c in self.dealer_cards)
        a = sum(1 for c in self.dealer_cards if c[0] == 1)
        while h > 21 and a > 0:
            h -= 10
            a -= 1
        return h

    def _dealer_is_soft(self) -> bool:
        h = sum(11 if c[0] == 1 else c[0] for c in self.dealer_cards)
        return any(c[0] == 1 for c in self.dealer_cards) and h <= 21

    def _settle_all_hands(self) -> None:
        d_tot = self._dealer_total()
        d_bj = len(self.dealer_cards) == 2 and d_tot == 21

        total_net = 0.0
        for h in self.player_hands:
            if h.is_surrendered:
                h.net_payout = -0.5 * h.bet
                h.result_text = "SURRENDER (-0.5x)"
            elif h.is_bust:
                h.net_payout = -h.bet
                h.result_text = "BUST (-1.0x)"
            elif h.is_blackjack:
                if d_bj:
                    h.net_payout = 0.0
                    h.result_text = "PUSH BJ (0.0x)"
                else:
                    h.net_payout = self.rules.blackjack_payout * h.bet
                    h.result_text = f"BJ WIN (+{self.rules.blackjack_payout}x)"
            else:
                p_tot = h.total
                if d_bj:
                    h.net_payout = -h.bet
                    h.result_text = "DEALER BJ (-1.0x)"
                elif d_tot > 21:
                    h.net_payout = +h.bet
                    h.result_text = "DEALER BUST (+1.0x)"
                elif p_tot > d_tot:
                    h.net_payout = +h.bet
                    h.result_text = "WIN (+1.0x)"
                elif p_tot < d_tot:
                    h.net_payout = -h.bet
                    h.result_text = "LOSS (-1.0x)"
                else:
                    h.net_payout = 0.0
                    h.result_text = "PUSH (0.0x)"

            total_net += h.net_payout

        self.bankroll += total_net
        self.session_profit += total_net
        
        if self.bankroll > self.peak_bankroll:
            self.peak_bankroll = self.bankroll
        
        dd = ((self.peak_bankroll - self.bankroll) / self.peak_bankroll) * 100.0 if self.peak_bankroll > 0 else 0.0
        if dd > self.max_drawdown:
            self.max_drawdown = dd
            
        self._update_profit_display()
        
        ev_gen = self.base_bet * self.current_round_data.get('ev_multiplier', 0.0)
        tc_start = self.current_round_data.get('tc', 0)
        rec_bet = self.current_round_data.get('rec_bet', 0.0)
        act_str = self.current_round_data.get('first_action', 'N/A')
        err = self.current_round_data.get('error', False)
        h_str = str(self.current_round_data.get('initial_hand', '--'))
        d_str = "A" if self.dealer_cards[0][0] == 1 else str(self.dealer_cards[0][0])
        
        self.table_view.history_overlay.add_round_record(
            self.rounds_played, tc_start, f"${self.base_bet:g}/${rec_bet:g}",
            h_str, d_str, act_str, err, total_net, ev_gen, self.bankroll
        )
        
        self.in_round = False
        self.lbl_strat_hand.setText("Tu Mano: -- | Total: --")
        self.lbl_strat_dealer.setText("Carta Crupier: --")
        self.lbl_strat_action.setText("🎯 Acción Óptima en Matriz (CD): --")
        
        self._update_button_states()

    def _record_decision_stats(
        self, hand: PlayerHandState, is_optimal: bool, ev_loss: float
    ) -> None:
        self.stats_total_decisions += 1
        self.stats_total_ev_loss += ev_loss
        if is_optimal:
            self.stats_optimal_decisions += 1

        is_pair = len(hand.cards) == 2 and hand.cards[0][0] == hand.cards[1][0]
        if is_pair:
            self.stats_pairs_total += 1
            if is_optimal:
                self.stats_pairs_opt += 1
        elif hand.is_soft:
            self.stats_soft_total += 1
            if is_optimal:
                self.stats_soft_opt += 1
        else:
            self.stats_hard_total += 1
            if is_optimal:
                self.stats_hard_opt += 1

        pct_global = (self.stats_optimal_decisions / max(1, self.stats_total_decisions)) * 100.0
        self.lbl_stats_global.setText(
            f"PRECISIÓN: {pct_global:.1f}% ({self.stats_optimal_decisions}/{self.stats_total_decisions})"
        )
        self.lbl_stats_global.setStyleSheet(
            "color: #00E676; font-family: Consolas; font-weight: bold; font-size: 13px;"
            if pct_global >= 90.0 else "color: #FF5252; font-family: Consolas; font-weight: bold; font-size: 13px;"
        )

        h_pct = (self.stats_hard_opt / max(1, self.stats_hard_total)) * 100.0
        s_pct = (self.stats_soft_opt / max(1, self.stats_soft_total)) * 100.0
        p_pct = (self.stats_pairs_opt / max(1, self.stats_pairs_total)) * 100.0

        self.lbl_stats_hard.setText(f"Duras: {self.stats_hard_opt}/{self.stats_hard_total} ({h_pct:.0f}%)")
        self.lbl_stats_soft.setText(f"Blandas: {self.stats_soft_opt}/{self.stats_soft_total} ({s_pct:.0f}%)")
        self.lbl_stats_pairs.setText(f"Pares: {self.stats_pairs_opt}/{self.stats_pairs_total} ({p_pct:.0f}%)")
        dollar_loss = self.stats_total_ev_loss * self.base_bet
        self.lbl_stats_loss.setText(f"Pérdida EV: -{self.stats_total_ev_loss:.4f}u (-${dollar_loss:.2f})")

    def _update_button_states(self) -> None:
        if not self.in_round:
            self.btn_deal.setEnabled(True)
            self.spin_bet.setEnabled(True)
            self.btn_hit.setEnabled(False)
            self.btn_stand.setEnabled(False)
            self.btn_double.setEnabled(False)
            self.btn_split.setEnabled(False)
            self.btn_surrender.setEnabled(False)
            self.btn_insurance.setEnabled(False)
            return

        self.btn_deal.setEnabled(False)
        self.spin_bet.setEnabled(False)
        self.btn_hit.setEnabled(True)
        self.btn_stand.setEnabled(True)

        cur_hand = self.player_hands[self.active_hand_idx]
        can_double = len(cur_hand.cards) == 2 and not cur_hand.is_doubled
        self.btn_double.setEnabled(can_double)

        can_split = (
            len(cur_hand.cards) == 2
            and cur_hand.cards[0][0] == cur_hand.cards[1][0]
            and len(self.player_hands) < self.rules.max_split_hands
        )
        self.btn_split.setEnabled(can_split)

        can_surr = (
            len(cur_hand.cards) == 2
            and self.rules.allow_late_surrender
            and len(self.player_hands) == 1
        )
        self.btn_surrender.setEnabled(can_surr)
        self.btn_insurance.setEnabled(self.insurance_offered)