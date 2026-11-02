from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum, auto
from typing import Dict, Tuple, Optional, List
from core.rules import TableRules
from core.shoe import CompositionShoe, SHIFTS, MASKS, CARDS_DATA
from core.dealer import DealerEngine
from core.counting import CardCounter
from core.ap_metrics import AdvantagePlayMetrics

class Action(IntEnum):
    STAND = auto()
    HIT = auto()
    DOUBLE = auto()
    SPLIT = auto()
    SURRENDER = auto()
    INSURANCE = auto()

@dataclass(frozen=True, slots=True)
class DecisionEvaluation:
    ev_stand: float
    ev_hit: Optional[float]
    ev_double: Optional[float]
    ev_split: Optional[float]
    ev_surrender: Optional[float]
    optimal_action: Action
    optimal_ev: float
    dealer_distribution: Dict[int, float]

@dataclass(frozen=True, slots=True)
class InsuranceEvaluation:
    ev_insurance: float
    prob_ten: float
    is_positive_ev: bool

class CompositionDependentEngine:
    """
    Motor CD de alto rendimiento para Advantage Play.
    Soporta backward induction en uint64, reglas ENHC con OBO riguroso y correlación con conteo.
    """
    def __init__(self, rules: TableRules) -> None:
        self.rules = rules
        self.dealer_engine = DealerEngine(rules)

    def clear_cache(self) -> None:
        self.dealer_engine.clear_cache()

    def evaluate_insurance(self, shoe: CompositionShoe) -> InsuranceEvaluation:
        """Calcula el EV exacto de la apuesta de Seguro."""
        if shoe.total_cards == 0:
            return InsuranceEvaluation(ev_insurance=-0.5, prob_ten=0.0, is_positive_ev=False)

        prob_ten = shoe.counts[9] / shoe.total_cards
        ev = 1.5 * prob_ten - 0.5
        return InsuranceEvaluation(
            ev_insurance=ev,
            prob_ten=prob_ten,
            is_positive_ev=(ev > 0.0)
        )

    @staticmethod
    def build_stand_table(dealer_dist: Dict[int, float]) -> Tuple[float, ...]:
        """Precomputa la tabla O(1) de pagos esperados de Stand para totales de 0 a 21."""
        bust_prob = dealer_dist.get(DealerEngine.BUST, 0.0)
        bj_prob = dealer_dist.get(DealerEngine.NATURAL_BJ, 0.0)

        table: List[float] = [0.0] * 22
        for t in range(4, 22):
            ev = -bj_prob + bust_prob
            for d in range(17, 22):
                p = dealer_dist.get(d, 0.0)
                if t > d:
                    ev += p
                elif t < d:
                    ev -= p
            table[t] = ev
        return tuple(table)

    def _ev_hit_tree(
        self,
        player_total: int,
        is_soft: bool,
        packed_shoe: int,
        total_cards: int,
        stand_table: Tuple[float, ...],
        hit_cache: Dict[Tuple[int, bool, int], float]
    ) -> float:
        """Backward induction del cono local de Hit sobre uint64."""
        state_key = (player_total, is_soft, packed_shoe)
        if state_key in hit_cache:
            return hit_cache[state_key]

        if total_cards == 0:
            return -1.0

        ev = 0.0
        next_total = total_cards - 1

        for shift, mask, dec_mask, card_val in CARDS_DATA:
            cnt = (packed_shoe >> shift) & mask
            if cnt == 0:
                continue

            prob = cnt / total_cards
            next_packed = packed_shoe - dec_mask

            new_soft = is_soft
            if card_val == 1:
                if not is_soft and (player_total + 11 <= 21):
                    new_tot = player_total + 11
                    new_soft = True
                else:
                    new_tot = player_total + 1
            else:
                new_tot = player_total + card_val

            if new_tot > 21 and new_soft:
                new_tot -= 10
                new_soft = False

            if new_tot > 21:
                ev += prob * (-1.0)
            elif new_tot == 21:
                ev += prob * stand_table[21]
            else:
                s_ev = stand_table[new_tot]
                h_ev = self._ev_hit_tree(new_tot, new_soft, next_packed, next_total, stand_table, hit_cache)
                ev += prob * (s_ev if s_ev > h_ev else h_ev)

        hit_cache[state_key] = ev
        return ev

    def _ev_double_step(
        self,
        player_total: int,
        is_soft: bool,
        packed_shoe: int,
        total_cards: int,
        stand_table: Tuple[float, ...],
        prob_dealer_bj: float = 0.0
    ) -> float:
        """
        Cálculo de Double. Bajo ENHC + OBO, el jugador solo pierde su unidad original
        (-1.0 en vez de -2.0) si el crupier finaliza con Blackjack natural.
        """
        if total_cards == 0:
            base_loss = -2.0
            if not self.rules.is_hole_card_game and self.rules.allow_obo and prob_dealer_bj > 0.0:
                base_loss += prob_dealer_bj
            return base_loss

        ev = 0.0
        for shift, mask, _, card_val in CARDS_DATA:
            cnt = (packed_shoe >> shift) & mask
            if cnt == 0:
                continue

            prob = cnt / total_cards
            new_soft = is_soft
            if card_val == 1:
                if not is_soft and (player_total + 11 <= 21):
                    new_tot = player_total + 11
                else:
                    new_tot = player_total + 1
            else:
                new_tot = player_total + card_val

            if new_tot > 21 and new_soft:
                new_tot -= 10

            if new_tot > 21:
                ev += prob * (-2.0)
            else:
                ev += prob * (2.0 * stand_table[new_tot])

        # En OBO, frente a BJ natural del crupier, se reintegra la segunda unidad apostada
        if not self.rules.is_hole_card_game and self.rules.allow_obo and prob_dealer_bj > 0.0:
            ev += prob_dealer_bj

        return ev

    def _ev_split_ace_branch(
        self,
        packed_shoe: int,
        total_cards: int,
        resplits_left: int,
        stand_table: Tuple[float, ...],
        prob_dealer_bj: float = 0.0
    ) -> float:
        """Resuelve una rama de As dividido considerando recursivamente allow_rsa y OBO."""
        if total_cards == 0:
            return stand_table[12]

        branch_ev = 0.0
        next_total = total_cards - 1

        for shift, mask, dec_mask, card_val in CARDS_DATA:
            cnt = (packed_shoe >> shift) & mask
            if cnt == 0:
                continue

            prob = cnt / total_cards
            next_packed = packed_shoe - dec_mask

            if card_val == 1:
                s12 = stand_table[12]
                if self.rules.allow_rsa and resplits_left > 0:
                    sub_split = 2.0 * self._ev_split_ace_branch(
                        next_packed, next_total, resplits_left - 1, stand_table, prob_dealer_bj=prob_dealer_bj
                    )
                    if not self.rules.is_hole_card_game and self.rules.allow_obo and prob_dealer_bj > 0.0:
                        sub_split += prob_dealer_bj
                    branch_ev += prob * (sub_split if sub_split > s12 else s12)
                else:
                    branch_ev += prob * s12
            else:
                hand_tot = 11 + card_val
                branch_ev += prob * stand_table[hand_tot]

        return branch_ev

    def _ev_split_standard_branch(
        self,
        card: int,
        packed_shoe: int,
        total_cards: int,
        resplits_left: int,
        stand_table: Tuple[float, ...],
        hit_cache: Dict[Tuple[int, bool, int], float],
        split_cache: Dict[Tuple[int, int, int], float],
        prob_dealer_bj: float = 0.0
    ) -> float:
        """Resuelve una rama estándar de división con soporte DAS, RSA y OBO recursivo."""
        state_key = (card, packed_shoe, resplits_left)
        if state_key in split_cache:
            return split_cache[state_key]

        if total_cards == 0:
            return -1.0

        branch_ev = 0.0
        next_total = total_cards - 1

        for shift, mask, dec_mask, card_val in CARDS_DATA:
            cnt = (packed_shoe >> shift) & mask
            if cnt == 0:
                continue

            prob = cnt / total_cards
            next_packed = packed_shoe - dec_mask

            if card == 1 or card_val == 1:
                is_soft = True
                if card == 1 and card_val == 1:
                    hand_total = 12
                elif card == 1:
                    hand_total = 11 + card_val
                else:
                    hand_total = card + 11
            else:
                is_soft = False
                hand_total = card + card_val

            s_ev = stand_table[hand_total]
            h_ev = self._ev_hit_tree(hand_total, is_soft, next_packed, next_total, stand_table, hit_cache)
            best_opt = s_ev if s_ev > h_ev else h_ev

            if self.rules.allow_das:
                d_ev = self._ev_double_step(
                    hand_total, is_soft, next_packed, next_total, stand_table, prob_dealer_bj=prob_dealer_bj
                )
                if d_ev > best_opt:
                    best_opt = d_ev

            if card_val == card and resplits_left > 0 and (card != 1 or self.rules.allow_rsa):
                resplit_val = 2.0 * self._ev_split_standard_branch(
                    card, next_packed, next_total, resplits_left - 1, stand_table,
                    hit_cache, split_cache, prob_dealer_bj=prob_dealer_bj
                )
                if not self.rules.is_hole_card_game and self.rules.allow_obo and prob_dealer_bj > 0.0:
                    resplit_val += prob_dealer_bj

                if resplit_val > best_opt:
                    best_opt = resplit_val

            branch_ev += prob * best_opt

        split_cache[state_key] = branch_ev
        return branch_ev

    def evaluate_decision(
        self,
        player_cards: Tuple[int, ...],
        dealer_upcard: int,
        shoe: CompositionShoe
    ) -> DecisionEvaluation:
        """Punto de entrada de alta eficiencia para auditoría y HUD."""
        packed_shoe = shoe.packed
        total_cards = shoe.total_cards

        dealer_dist = self.dealer_engine.get_terminal_distribution(dealer_upcard, packed_shoe, total_cards)
        stand_table = self.build_stand_table(dealer_dist)
        prob_dealer_bj = dealer_dist.get(DealerEngine.NATURAL_BJ, 0.0)

        # Evaluación de Blackjack Natural
        is_player_natural_bj = (
            len(player_cards) == 2 and
            ((player_cards[0] == 1 and player_cards[1] == 10) or
             (player_cards[0] == 10 and player_cards[1] == 1))
        )

        if is_player_natural_bj:
            payout = self.rules.blackjack_payout
            if total_cards == 0:
                bj_ev = payout
            elif self.rules.is_hole_card_game:
                if dealer_upcard in (1, 10):
                    prob_bj = (
                        ((packed_shoe >> SHIFTS[9]) & MASKS[9]) / total_cards if dealer_upcard == 1
                        else ((packed_shoe >> SHIFTS[0]) & MASKS[0]) / total_cards
                    )
                    bj_ev = (1.0 - prob_bj) * payout
                else:
                    bj_ev = payout
            else:
                bj_ev = (1.0 - prob_dealer_bj) * payout

            return DecisionEvaluation(
                ev_stand=bj_ev,
                ev_hit=None,
                ev_double=None,
                ev_split=None,
                ev_surrender=None,
                optimal_action=Action.STAND,
                optimal_ev=bj_ev,
                dealer_distribution=dealer_dist
            )

        # Cálculo de valor de mano estándar
        hard_sum = 0
        aces = 0
        for c in player_cards:
            if c == 1:
                aces += 1
                hard_sum += 11
            else:
                hard_sum += c

        while hard_sum > 21 and aces > 0:
            hard_sum -= 10
            aces -= 1

        is_soft = (aces > 0)
        player_total = hard_sum

        # 1. Stand
        ev_s = stand_table[player_total]

        # 2. Hit
        hit_cache: Dict[Tuple[int, bool, int], float] = {}
        ev_h = self._ev_hit_tree(player_total, is_soft, packed_shoe, total_cards, stand_table, hit_cache)

        # 3. Double
        ev_d: Optional[float] = None
        if len(player_cards) == 2 and total_cards > 0:
            ev_d = self._ev_double_step(
                player_total, is_soft, packed_shoe, total_cards, stand_table, prob_dealer_bj=prob_dealer_bj
            )

        # 4. Split
        ev_sp: Optional[float] = None
        can_split = (
            len(player_cards) == 2
            and player_cards[0] == player_cards[1]
            and self.rules.max_split_hands >= 2
        )
        if can_split and total_cards >= 2:
            resplits_left = self.rules.max_split_hands - 2
            pair_card = player_cards[0]

            if pair_card == 1 and not self.rules.hit_split_aces:
                ev_single_branch = self._ev_split_ace_branch(
                    packed_shoe, total_cards, resplits_left, stand_table, prob_dealer_bj=prob_dealer_bj
                )
                ev_sp = 2.0 * ev_single_branch
            else:
                split_cache: Dict[Tuple[int, int, int], float] = {}
                ev_single_branch = self._ev_split_standard_branch(
                    pair_card, packed_shoe, total_cards, resplits_left, stand_table,
                    hit_cache, split_cache, prob_dealer_bj=prob_dealer_bj
                )
                ev_sp = 2.0 * ev_single_branch

            # Reintegro de la unidad de la segunda mano en OBO ante Blackjack natural
            if not self.rules.is_hole_card_game and self.rules.allow_obo and prob_dealer_bj > 0.0:
                ev_sp += prob_dealer_bj

        # 5. Surrender
        ev_sur: Optional[float] = None
        if self.rules.allow_late_surrender and len(player_cards) == 2:
            ev_sur = -0.5

        options = [(Action.STAND, ev_s), (Action.HIT, ev_h)]
        if ev_d is not None:
            options.append((Action.DOUBLE, ev_d))
        if ev_sp is not None:
            options.append((Action.SPLIT, ev_sp))
        if ev_sur is not None:
            options.append((Action.SURRENDER, ev_sur))

        best_action, best_ev = max(options, key=lambda item: item[1])

        return DecisionEvaluation(
            ev_stand=ev_s,
            ev_hit=ev_h,
            ev_double=ev_d,
            ev_split=ev_sp,
            ev_surrender=ev_sur,
            optimal_action=best_action,
            optimal_ev=best_ev,
            dealer_distribution=dealer_dist
        )

    def evaluate_hand_with_counting(
        self,
        player_cards: Tuple[int, ...],
        dealer_upcard: int,
        shoe: CompositionShoe,
        counter: CardCounter
    ) -> Tuple[DecisionEvaluation, int, float]:
        """
        Evalúa la decisión óptima por composición exacta y la correlaciona con
        el True Count actual y la ventaja (% Edge) analítica del jugador.
        Retorna: (evaluacion_cd, true_count, player_edge)
        """
        eval_cd = self.evaluate_decision(player_cards, dealer_upcard, shoe)
        tc = counter.get_true_count(shoe.total_cards)
        edge = AdvantagePlayMetrics.compute_player_edge(tc)
        return eval_cd, tc, edge
