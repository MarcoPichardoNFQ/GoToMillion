from __future__ import annotations
from dataclasses import dataclass
import random
import time
from typing import Dict, List, Optional, Tuple

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

        # Estado del juego
        self.dealer_cards: List[Tuple[int, str, bool]] = []
        self.player_hands: List[PlayerHandState] = []
        self.active_hand_idx: int = 0
        self.in_round: bool = False
        self.insurance_offered: bool = False

        # Estadísticas de entrenamiento acumuladas
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

        # 1. Barra de Estadísticas y Precisión del Usuario
        self.stats_bar = QFrame(self)
        self.stats_bar.setStyleSheet(
            "background-color: #14171F; border-bottom: 1px solid #2B2F3A; padding: 4px;"
        )
        s_layout = QHBoxLayout(self.stats_bar)
        s_layout.setContentsMargins(12, 4, 12, 4)

        self.lbl_stats_global = QLabel("PRECISIÓN: 100.0% (0/0)")
        self.lbl_stats_global.setStyleSheet(
            "color: #00E676; font-family: Consolas; font-weight: bold; font-size: 13px;"
        )
        self.lbl_stats_hard = QLabel("Duras: 0/0")
        self.lbl_stats_soft = QLabel("Blandas: 0/0")
        self.lbl_stats_pairs = QLabel("Pares: 0/0")
        self.lbl_stats_loss = QLabel("Pérdida EV: 0.0000u ($0.00)")
        self.lbl_stats_loss.setStyleSheet(
            "color: #FF5252; font-family: Consolas; font-size: 13px;"
        )

        for lbl in (self.lbl_stats_hard, self.lbl_stats_soft, self.lbl_stats_pairs):
            lbl.setStyleSheet("color: #90A4AE; font-family: Consolas; font-size: 13px;")

        s_layout.addWidget(self.lbl_stats_global)
        s_layout.addSpacing(16)
        s_layout.addWidget(self.lbl_stats_hard)
        s_layout.addWidget(self.lbl_stats_soft)
        s_layout.addWidget(self.lbl_stats_pairs)
        s_layout.addStretch()
        s_layout.addWidget(self.lbl_stats_loss)
        layout.addWidget(self.stats_bar)

        # 2. Mesa Gráfica y Bandeja de Descarte
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

        # 3. Banner de Auditoría Post-Acción Instantánea
        self.banner_frame = QFrame(self)
        self.banner_frame.setFixedHeight(38)
        self.banner_frame.setStyleSheet(
            "background-color: #1A1D24; border: 1px solid #2B2F3A; border-radius: 4px;"
        )
        b_layout = QHBoxLayout(self.banner_frame)
        b_layout.setContentsMargins(12, 0, 12, 0)

        self.lbl_banner = QLabel(
            "DECISION COACH ACTIVO — Realiza una jugada para auditar"
        )
        self.lbl_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_banner.setStyleSheet(
            "color: #90A4AE; font-family: Consolas; font-weight: bold; font-size: 12px;"
        )
        b_layout.addWidget(self.lbl_banner)
        layout.addWidget(self.banner_frame)

        # 4. Botonera de Acciones
        self.controls_bar = QFrame(self)
        self.controls_bar.setStyleSheet(
            "background-color: #14171F; border-top: 1px solid #2B2F3A; padding: 6px;"
        )
        c_layout = QHBoxLayout(self.controls_bar)
        c_layout.setContentsMargins(12, 6, 12, 6)
        c_layout.setSpacing(8)

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
            (
                self.btn_double,
                "#FFD600",
                lambda: self.handle_user_action(Action.DOUBLE),
            ),
            (self.btn_split, "#00E5FF", lambda: self.handle_user_action(Action.SPLIT)),
            (
                self.btn_surrender,
                "#FF9100",
                lambda: self.handle_user_action(Action.SURRENDER),
            ),
            (
                self.btn_insurance,
                "#AB47BC",
                lambda: self.handle_user_action(Action.INSURANCE),
            ),
        ]

        for btn, col, slot in buttons:
            btn.setFixedHeight(34)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #1A1D24;
                    color: {col};
                    border: 1px solid {col};
                    border-radius: 4px;
                    font-family: Consolas;
                    font-weight: bold;
                    padding: 0 12px;
                }}
                QPushButton:hover {{
                    background-color: {col};
                    color: #0F1117;
                }}
                QPushButton:disabled {{
                    background-color: #12141A;
                    color: #455A64;
                    border: 1px solid #2B2F3A;
                }}
            """)
            btn.clicked.connect(slot)
            c_layout.addWidget(btn)

        layout.addWidget(self.controls_bar)
        self._update_button_states()

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("D"), self, self.deal_round)
        QShortcut(QKeySequence("H"), self, lambda: self.handle_user_action(Action.HIT))
        QShortcut(
            QKeySequence("S"), self, lambda: self.handle_user_action(Action.STAND)
        )
        QShortcut(
            QKeySequence("2"), self, lambda: self.handle_user_action(Action.DOUBLE)
        )
        QShortcut(
            QKeySequence("P"), self, lambda: self.handle_user_action(Action.SPLIT)
        )
        QShortcut(
            QKeySequence("R"), self, lambda: self.handle_user_action(Action.SURRENDER)
        )
        QShortcut(
            QKeySequence("I"), self, lambda: self.handle_user_action(Action.INSURANCE)
        )

    def reset_shoe_and_counter(self) -> None:
        self.shoe = CompositionShoe.from_decks(self.rules.decks)
        self.counter.reset()
        self.discard_tray.set_discard_state(0)

    def draw_card(self, face_up: bool = True) -> Tuple[int, str, bool]:
        if (
            self.shoe.is_cut_card_reached(self.rules.penetration)
            or self.shoe.total_cards < 15
        ):
            self.reset_shoe_and_counter()

        val = random.choices(range(1, 11), weights=self.shoe.counts)[0]
        suit = random.choice(self.suits)
        self.shoe = self.shoe.remove(val)
        if face_up:
            self.counter.update(val)
        self.discard_tray.set_discard_state(
            self.shoe.initial_total_cards - self.shoe.total_cards
        )
        return (val, suit, face_up)

    def deal_round(self) -> None:
        if self.in_round:
            return

        self.in_round = True
        self.insurance_offered = False

        c1_p = self.draw_card(True)
        c1_d = self.draw_card(True)
        c2_p = self.draw_card(True)
        c2_d = self.draw_card(False)

        self.dealer_cards = [c1_d, c2_d]
        self.player_hands = [PlayerHandState(cards=[c1_p, c2_p], bet=self.base_bet)]
        self.active_hand_idx = 0

        self.table_view.set_dealer_cards(self.dealer_cards)
        self._refresh_table_display()

        if c1_d[0] == 1:
            self.insurance_offered = True

        dealer_has_bj = (c1_d[0] == 1 and c2_d[0] == 10) or (
            c1_d[0] == 10 and c2_d[0] == 1
        )
        player_has_bj = self.player_hands[0].is_blackjack

        if self.rules.is_hole_card_game and (dealer_has_bj or player_has_bj):
            self.dealer_cards[1] = (c2_d[0], c2_d[1], True)
            self.counter.update(c2_d[0])
            self.table_view.set_dealer_cards(self.dealer_cards)
            self._settle_all_hands()
            return

        self._evaluate_and_update_hud()
        self._update_button_states()

    def _refresh_table_display(self) -> None:
        hands_tuples = [[c for c in h.cards] for h in self.player_hands]
        self.table_view.set_player_hands(hands_tuples, active_idx=self.active_hand_idx)

    def _evaluate_and_update_hud(self) -> DecisionEvaluation:
        cur_hand = self.player_hands[self.active_hand_idx]
        eval_cd, tc, edge = self.engine.evaluate_hand_with_counting(
            cur_hand.values_tuple, self.dealer_cards[0][0], self.shoe, self.counter
        )
        bet_rec = AdvantagePlayMetrics.recommend_bet(
            bankroll=self.bankroll,
            true_count=tc,
            base_edge=edge - (tc * 0.005),
            kelly_fraction=KellyFraction.HALF,
        )
        self.hud.update_telemetry(
            rc=self.counter.running_count,
            tc=tc,
            edge=edge,
            bet_rec=bet_rec,
            shoe_counts=self.shoe.counts,
            total_cards=self.shoe.total_cards,
            eval_cd=eval_cd,
        )
        return eval_cd

    def handle_user_action(self, user_action: Action) -> None:
        if not self.in_round:
            return

        cur_hand = self.player_hands[self.active_hand_idx]
        eval_cd = self.engine.evaluate_decision(
            cur_hand.values_tuple, self.dealer_cards[0][0], self.shoe
        )

        opt_act = eval_cd.optimal_action
        opt_ev = eval_cd.optimal_ev

        ev_map = {
            Action.STAND: eval_cd.ev_stand,
            Action.HIT: eval_cd.ev_hit,
            Action.DOUBLE: eval_cd.ev_double,
            Action.SPLIT: eval_cd.ev_split,
            Action.SURRENDER: eval_cd.ev_surrender,
            Action.INSURANCE: 0.0,
        }

        user_ev = ev_map.get(user_action, -1.0)
        user_ev = user_ev if user_ev is not None else -1.0
        ev_loss = max(0.0, opt_ev - user_ev)

        is_optimal = user_action == opt_act
        self._record_decision_stats(cur_hand, is_optimal, ev_loss)

        if is_optimal:
            self.lbl_banner.setText("DECISIÓN ÓPTIMA (+0.00 EV)")
            self.banner_frame.setStyleSheet(
                "background-color: #162B20; border: 1px solid #00E676; border-radius: 4px;"
            )
            self.lbl_banner.setStyleSheet(
                "color: #00E676; font-family: Consolas; font-weight: bold; font-size: 12px;"
            )
        else:
            dollar_loss = ev_loss * cur_hand.bet
            self.lbl_banner.setText(
                f"ERROR: Óptima era {opt_act.name}. Coste: -{ev_loss:.4f}u (-${dollar_loss:.2f} EV)"
            )
            self.banner_frame.setStyleSheet(
                "background-color: #2B1616; border: 1px solid #FF5252; border-radius: 4px;"
            )
            self.lbl_banner.setStyleSheet(
                "color: #FF5252; font-family: Consolas; font-weight: bold; font-size: 12px;"
            )

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
            c1 = cur_hand.cards[0]
            c2 = cur_hand.cards[1]
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
        self.table_view.set_dealer_cards(self.dealer_cards)

        any_alive = any(not (h.is_bust or h.is_surrendered) for h in self.player_hands)

        if any_alive:
            while True:
                d_tot = self._dealer_total()
                d_soft = self._dealer_is_soft()

                if d_tot < 17:
                    self.dealer_cards.append(self.draw_card(True))
                    self.table_view.set_dealer_cards(self.dealer_cards)
                elif d_tot == 17 and d_soft and self.rules.dealer_hits_soft_17:
                    self.dealer_cards.append(self.draw_card(True))
                    self.table_view.set_dealer_cards(self.dealer_cards)
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
        self.in_round = False
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

        pct_global = (self.stats_optimal_decisions / self.stats_total_decisions) * 100.0
        self.lbl_stats_global.setText(
            f"PRECISIÓN: {pct_global:.1f}% ({self.stats_optimal_decisions}/{self.stats_total_decisions})"
        )
        self.lbl_stats_global.setStyleSheet(
            "color: #00E676; font-family: Consolas; font-weight: bold; font-size: 13px;"
            if pct_global >= 90.0
            else "color: #FF5252; font-family: Consolas; font-weight: bold; font-size: 13px;"
        )

        h_pct = (self.stats_hard_opt / max(1, self.stats_hard_total)) * 100.0
        s_pct = (self.stats_soft_opt / max(1, self.stats_soft_total)) * 100.0
        p_pct = (self.stats_pairs_opt / max(1, self.stats_pairs_total)) * 100.0

        self.lbl_stats_hard.setText(
            f"Duras: {self.stats_hard_opt}/{self.stats_hard_total} ({h_pct:.0f}%)"
        )
        self.lbl_stats_soft.setText(
            f"Blandas: {self.stats_soft_opt}/{self.stats_soft_total} ({s_pct:.0f}%)"
        )
        self.lbl_stats_pairs.setText(
            f"Pares: {self.stats_pairs_opt}/{self.stats_pairs_total} ({p_pct:.0f}%)"
        )

        dollar_loss = self.stats_total_ev_loss * self.base_bet
        self.lbl_stats_loss.setText(
            f"Pérdida EV: -{self.stats_total_ev_loss:.4f}u (-${dollar_loss:.2f})"
        )

    def _update_button_states(self) -> None:
        if not self.in_round:
            self.btn_deal.setEnabled(True)
            self.btn_hit.setEnabled(False)
            self.btn_stand.setEnabled(False)
            self.btn_double.setEnabled(False)
            self.btn_split.setEnabled(False)
            self.btn_surrender.setEnabled(False)
            self.btn_insurance.setEnabled(False)
            return

        self.btn_deal.setEnabled(False)
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
