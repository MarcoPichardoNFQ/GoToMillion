from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum, auto
from typing import Dict, Tuple, Optional, List
from core.rules import TableRules
from core.shoe import CompositionShoe, SHIFTS, MASKS, CARDS_DATA, pack_shoe
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
    Soporta backward induction en uint64, reglas ENHC con OBO riguroso,
    aproximación de poda de Griffin y resolución combinatoria exacta de Split.
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
        obo_refund = prob_dealer_bj if (not self.rules.is_hole_card_game and self.rules.allow_obo) else 0.0
        
        if total_cards == 0:
            return -2.0 + obo_refund

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

        ev += obo_refund
        return ev

    def _ev_split_ace_branch(
        self,
        packed_shoe: int,
        total_cards: int,
        resplits_left: int,
        stand_table: Tuple[float, ...],
        prob_dealer_bj: float = 0.0
    ) -> float:
        """
        Aproximación marginal de Peter Griffin para As dividido.
        Evalúa una rama asumiendo que el crupier roba del zapato precomputado en stand_table.
        """
        if total_cards == 0:
            return stand_table[12]

        obo_refund = prob_dealer_bj if (not self.rules.is_hole_card_game and self.rules.allow_obo) else 0.0
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
                    sub_split += obo_refund
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
        """
        Aproximación marginal de Peter Griffin para pares estándar.
        Reduce la complejidad combinatoria calculando EV_branch y multiplicando por 2.0.
        Nota matemática: Esta técnica es una aproximación asintótica rápida (O(N)),
        no una enumeración exacta, pues omite el cross-hand depletion y la alteración
        del residuo del crupier tras la resolución secuencial de ambas manos.
        """
        state_key = (card, packed_shoe, resplits_left)
        if state_key in split_cache:
            return split_cache[state_key]

        if total_cards == 0:
            return -1.0

        obo_refund = prob_dealer_bj if (not self.rules.is_hole_card_game and self.rules.allow_obo) else 0.0
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
                resplit_val += obo_refund

                if resplit_val > best_opt:
                    best_opt = resplit_val

            branch_ev += prob * best_opt

        split_cache[state_key] = branch_ev
        return branch_ev

    # =========================================================================
    # RESOLUCIÓN COMBINATORIA EXACTA DE SPLIT (SIN APROXIMACIONES MARGINALES)
    # =========================================================================

    def _terminal_dealer_payoff_exact(
        self,
        t1: int,
        bust1: bool,
        bet1: float,
        t2: int,
        bust2: bool,
        bet2: float,
        dealer_upcard: int,
        packed_shoe: int,
        total_cards: int
    ) -> float:
        """Calcula el payoff esperado conjunto exacto de ambas manos contra la fdp terminal del crupier."""
        dist = self.dealer_engine.get_terminal_distribution(dealer_upcard, packed_shoe, total_cards)
        prob_bj = dist.get(DealerEngine.NATURAL_BJ, 0.0)
        p_bust = dist.get(DealerEngine.BUST, 0.0)

        payoff = 0.0
        if not self.rules.is_hole_card_game and prob_bj > 0.0:
            if self.rules.allow_obo:
                payoff += prob_bj * (-1.0)
            else:
                payoff += prob_bj * (-(bet1 + bet2))

        for d in range(17, 22):
            pd = dist.get(d, 0.0)
            if pd == 0.0:
                continue
            po1 = -bet1 if bust1 else (bet1 if t1 > d else (-bet1 if t1 < d else 0.0))
            po2 = -bet2 if bust2 else (bet2 if t2 > d else (-bet2 if t2 < d else 0.0))
            payoff += pd * (po1 + po2)

        if p_bust > 0.0:
            po1 = -bet1 if bust1 else bet1
            po2 = -bet2 if bust2 else bet2
            payoff += p_bust * (po1 + po2)

        return payoff

    def _solve_hand2_exact(
        self,
        t1: int,
        bust1: bool,
        bet1: float,
        tot2: int,
        soft2: bool,
        bet2: float,
        can_double: bool,
        packed_shoe: int,
        total_cards: int,
        dealer_upcard: int,
        cache: Dict[Tuple[int, bool, float, int, bool], float]
    ) -> float:
        state_key = (tot2, soft2, bet2, packed_shoe, can_double)
        if state_key in cache:
            return cache[state_key]

        best_ev = self._terminal_dealer_payoff_exact(
            t1, bust1, bet1, tot2, False, bet2, dealer_upcard, packed_shoe, total_cards
        )

        if can_double and self.rules.allow_das and total_cards > 0:
            d_ev = 0.0
            next_total = total_cards - 1
            for shift, mask, dec_mask, card_val in CARDS_DATA:
                cnt = (packed_shoe >> shift) & mask
                if cnt == 0:
                    continue
                prob = cnt / total_cards
                next_packed = packed_shoe - dec_mask
                new_soft = soft2
                if card_val == 1:
                    if not soft2 and tot2 + 11 <= 21:
                        new_tot = tot2 + 11
                        new_soft = True
                    else:
                        new_tot = tot2 + 1
                else:
                    new_tot = tot2 + card_val

                if new_tot > 21 and new_soft:
                    new_tot -= 10
                    new_soft = False

                is_bust = (new_tot > 21)
                sub = self._terminal_dealer_payoff_exact(
                    t1, bust1, bet1, new_tot, is_bust, 2.0 * bet2, dealer_upcard, next_packed, next_total
                )
                d_ev += prob * sub
            if d_ev > best_ev:
                best_ev = d_ev

        if total_cards > 0:
            h_ev = 0.0
            next_total = total_cards - 1
            for shift, mask, dec_mask, card_val in CARDS_DATA:
                cnt = (packed_shoe >> shift) & mask
                if cnt == 0:
                    continue
                prob = cnt / total_cards
                next_packed = packed_shoe - dec_mask
                new_soft = soft2
                if card_val == 1:
                    if not soft2 and tot2 + 11 <= 21:
                        new_tot = tot2 + 11
                        new_soft = True
                    else:
                        new_tot = tot2 + 1
                else:
                    new_tot = tot2 + card_val

                if new_tot > 21 and new_soft:
                    new_tot -= 10
                    new_soft = False

                if new_tot > 21:
                    sub = self._terminal_dealer_payoff_exact(
                        t1, bust1, bet1, new_tot, True, bet2, dealer_upcard, next_packed, next_total
                    )
                elif new_tot == 21:
                    sub = self._terminal_dealer_payoff_exact(
                        t1, bust1, bet1, 21, False, bet2, dealer_upcard, next_packed, next_total
                    )
                else:
                    sub = self._solve_hand2_exact(
                        t1, bust1, bet1, new_tot, new_soft, bet2, False, next_packed, next_total, dealer_upcard, cache
                    )
                h_ev += prob * sub
            if h_ev > best_ev:
                best_ev = h_ev

        cache[state_key] = best_ev
        return best_ev

    def _dispatch_to_hand2_exact(
        self,
        t1: int,
        bust1: bool,
        bet1: float,
        packed_shoe: int,
        total_cards: int,
        pair_card: int,
        dealer_upcard: int
    ) -> float:
        if total_cards == 0:
            return -bet1

        ev_h2 = 0.0
        next_total = total_cards - 1
        cache2: Dict[Tuple[int, bool, float, int, bool], float] = {}

        for shift, mask, dec_mask, card_val in CARDS_DATA:
            cnt = (packed_shoe >> shift) & mask
            if cnt == 0:
                continue
            prob = cnt / total_cards
            next_packed = packed_shoe - dec_mask

            if pair_card == 1 or card_val == 1:
                is_soft = True
                if pair_card == 1 and card_val == 1:
                    tot = 12
                elif pair_card == 1:
                    tot = 11 + card_val
                else:
                    tot = pair_card + 11
            else:
                is_soft = False
                tot = pair_card + card_val

            sub = self._solve_hand2_exact(
                t1, bust1, bet1, tot, is_soft, 1.0, True, next_packed, next_total, dealer_upcard, cache2
            )
            ev_h2 += prob * sub

        return ev_h2

    def _solve_hand1_exact(
        self,
        tot1: int,
        soft1: bool,
        bet1: float,
        can_double: bool,
        packed_shoe: int,
        total_cards: int,
        pair_card: int,
        dealer_upcard: int,
        cache1: Dict[Tuple[int, bool, float, int, bool], float]
    ) -> float:
        state_key = (tot1, soft1, bet1, packed_shoe, can_double)
        if state_key in cache1:
            return cache1[state_key]

        best_ev = self._dispatch_to_hand2_exact(
            tot1, False, bet1, packed_shoe, total_cards, pair_card, dealer_upcard
        )

        if can_double and self.rules.allow_das and total_cards >= 2:
            d_ev = 0.0
            next_total = total_cards - 1
            for shift, mask, dec_mask, card_val in CARDS_DATA:
                cnt = (packed_shoe >> shift) & mask
                if cnt == 0:
                    continue
                prob = cnt / total_cards
                next_packed = packed_shoe - dec_mask
                new_soft = soft1
                if card_val == 1:
                    if not soft1 and tot1 + 11 <= 21:
                        new_tot = tot1 + 11
                        new_soft = True
                    else:
                        new_tot = tot1 + 1
                else:
                    new_tot = tot1 + card_val

                if new_tot > 21 and new_soft:
                    new_tot -= 10
                    new_soft = False

                is_bust = (new_tot > 21)
                sub = self._dispatch_to_hand2_exact(
                    new_tot, is_bust, 2.0 * bet1, next_packed, next_total, pair_card, dealer_upcard
                )
                d_ev += prob * sub
            if d_ev > best_ev:
                best_ev = d_ev

        if total_cards >= 2:
            h_ev = 0.0
            next_total = total_cards - 1
            for shift, mask, dec_mask, card_val in CARDS_DATA:
                cnt = (packed_shoe >> shift) & mask
                if cnt == 0:
                    continue
                prob = cnt / total_cards
                next_packed = packed_shoe - dec_mask
                new_soft = soft1
                if card_val == 1:
                    if not soft1 and tot1 + 11 <= 21:
                        new_tot = tot1 + 11
                        new_soft = True
                    else:
                        new_tot = tot1 + 1
                else:
                    new_tot = tot1 + card_val

                if new_tot > 21 and new_soft:
                    new_tot -= 10
                    new_soft = False

                if new_tot > 21:
                    sub = self._dispatch_to_hand2_exact(
                        new_tot, True, bet1, next_packed, next_total, pair_card, dealer_upcard
                    )
                elif new_tot == 21:
                    sub = self._dispatch_to_hand2_exact(
                        21, False, bet1, next_packed, next_total, pair_card, dealer_upcard
                    )
                else:
                    sub = self._solve_hand1_exact(
                        new_tot, new_soft, bet1, False, next_packed, next_total, pair_card, dealer_upcard, cache1
                    )
                h_ev += prob * sub
            if h_ev > best_ev:
                best_ev = h_ev

        cache1[state_key] = best_ev
        return best_ev

    def _evaluate_split_aces_exact(
        self,
        dealer_upcard: int,
        packed_shoe: int,
        total_cards: int
    ) -> float:
        """Resuelve exactamente Split de Ases (1 carta por mano sin hit) condicionando el residuo del crupier."""
        if total_cards < 2:
            return -2.0

        ev_total = 0.0
        next_total1 = total_cards - 1

        for shift1, mask1, dec_mask1, card_val1 in CARDS_DATA:
            cnt1 = (packed_shoe >> shift1) & mask1
            if cnt1 == 0:
                continue
            p1 = cnt1 / total_cards
            packed1 = packed_shoe - dec_mask1
            t1 = 12 if card_val1 == 1 else 11 + card_val1
            next_total2 = next_total1 - 1

            for shift2, mask2, dec_mask2, card_val2 in CARDS_DATA:
                cnt2 = (packed1 >> shift2) & mask2
                if cnt2 == 0:
                    continue
                p2 = cnt2 / next_total1
                packed2 = packed1 - dec_mask2
                t2 = 12 if card_val2 == 1 else 11 + card_val2

                payoff = self._terminal_dealer_payoff_exact(
                    t1, False, 1.0, t2, False, 1.0, dealer_upcard, packed2, next_total2
                )
                ev_total += p1 * p2 * payoff

        return ev_total

    def _evaluate_split_standard_exact(
        self,
        pair_card: int,
        dealer_upcard: int,
        packed_shoe: int,
        total_cards: int
    ) -> float:
        """Resuelve exactamente Split estándar para 2 manos por backward induction secuencial sin reemplazo."""
        if total_cards < 2:
            return -2.0

        ev_split = 0.0
        next_total = total_cards - 1
        cache1: Dict[Tuple[int, bool, float, int, bool], float] = {}

        for shift, mask, dec_mask, card_val in CARDS_DATA:
            cnt = (packed_shoe >> shift) & mask
            if cnt == 0:
                continue
            prob = cnt / total_cards
            next_packed = packed_shoe - dec_mask

            if pair_card == 1 or card_val == 1:
                is_soft = True
                if pair_card == 1 and card_val == 1:
                    tot = 12
                elif pair_card == 1:
                    tot = 11 + card_val
                else:
                    tot = pair_card + 11
            else:
                is_soft = False
                tot = pair_card + card_val

            sub = self._solve_hand1_exact(
                tot, is_soft, 1.0, True, next_packed, next_total, pair_card, dealer_upcard, cache1
            )
            ev_split += prob * sub

        return ev_split

    def evaluate_split_exact(
        self,
        pair_card: int,
        dealer_upcard: int,
        shoe: CompositionShoe
    ) -> float:
        """
        Calcula el EV analítico matemáticamente exacto de Split para 2 manos divididas,
        resolviendo exhaustivamente la extracción secuencial conjunta sin reemplazo
        y acondicionando la distribución final del crupier al residuo exacto.
        """
        if pair_card == 1 and not self.rules.hit_split_aces:
            return self._evaluate_split_aces_exact(
                dealer_upcard, shoe.packed, shoe.total_cards
            )
        else:
            return self._evaluate_split_standard_exact(
                pair_card, dealer_upcard, shoe.packed, shoe.total_cards
            )

    def evaluate_decision(
        self,
        player_cards: Tuple[int, ...],
        dealer_upcard: int,
        shoe: CompositionShoe,
        exact_split: bool = False
    ) -> DecisionEvaluation:
        packed_shoe = shoe.packed
        total_cards = shoe.total_cards

        dealer_dist = self.dealer_engine.get_terminal_distribution(dealer_upcard, packed_shoe, total_cards)
        stand_table = self.build_stand_table(dealer_dist)
        prob_dealer_bj = dealer_dist.get(DealerEngine.NATURAL_BJ, 0.0)
        obo_refund = prob_dealer_bj if (not self.rules.is_hole_card_game and self.rules.allow_obo) else 0.0

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

            if exact_split and self.rules.max_split_hands == 2:
                ev_sp = self.evaluate_split_exact(pair_card, dealer_upcard, shoe)
            else:
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

                ev_sp += obo_refund

        # 5. Surrender
        ev_sur: Optional[float] = None
        if self.rules.allow_late_surrender and len(player_cards) == 2:
            ev_sur = -0.5

        options = [(Action.STAND, ev_s), (Action.HIT, ev_h)]
        if ev_d is not None:
            options.append((Action.DOUBLE, ev_d))
        if ev_sp is not None:
            options.append((Action.SPLIT, ev_sp))
        if ev_sur门 is not None if False else (ev_sur is not None):
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
        counter: CardCounter,
        exact_split: bool = False
    ) -> Tuple[DecisionEvaluation, int, float]:
        """
        Evalúa la decisión óptima por composición exacta y la correlaciona con
        el True Count actual y la ventaja (% Edge) analítica del jugador.
        Retorna: (evaluacion_cd, true_count, player_edge)
        """
        eval_cd = self.evaluate_decision(player_cards, dealer_upcard, shoe, exact_split=exact_split)
        tc = counter.get_true_count(shoe.total_cards)
        edge = AdvantagePlayMetrics.compute_player_edge(tc)
        return eval_cd, tc, edge
