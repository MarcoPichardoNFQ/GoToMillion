from __future__ import annotations
from typing import Dict, Tuple
from core.rules import TableRules
from core.shoe import SHIFTS, MASKS, CARDS_DATA

class DealerEngine:
    """
    Motor combinatorio exacto de la distribución terminal del crupier.
    Distingue Blackjack natural (BJ=210) de 21 multi-carta (21).
    Optimizado para recursión directa sobre uint64 sin desempaquetar.
    """
    BUST = 22
    NATURAL_BJ = 210

    def __init__(self, rules: TableRules) -> None:
        self.rules = rules
        self._cache: Dict[Tuple[int, bool, int], Dict[int, float]] = {}

    def clear_cache(self) -> None:
        self._cache.clear()

    def get_dealer_expansion(
        self,
        total: int,
        is_soft: bool,
        packed_shoe: int,
        total_cards: int
    ) -> Dict[int, float]:
        """Expande recursivamente el árbol de robo del crupier."""
        state_key = (total, is_soft, packed_shoe)
        if state_key in self._cache:
            return self._cache[state_key]

        if total >= 17:
            if not is_soft or not self.rules.dealer_hits_soft_17 or total > 17:
                if total <= 21:
                    return {total: 1.0}
                return {self.BUST: 1.0}

        if total_cards == 0:
            return {self.BUST: 1.0}

        res: Dict[int, float] = {17: 0.0, 18: 0.0, 19: 0.0, 20: 0.0, 21: 0.0, self.BUST: 0.0}
        next_total = total_cards - 1

        for shift, mask, dec_mask, card_val in CARDS_DATA:
            cnt = (packed_shoe >> shift) & mask
            if cnt == 0:
                continue

            prob = cnt / total_cards
            next_packed = packed_shoe - dec_mask

            new_soft = is_soft
            if card_val == 1:
                if not is_soft and (total + 11 <= 21):
                    new_tot = total + 11
                    new_soft = True
                else:
                    new_tot = total + 1
            else:
                new_tot = total + card_val

            if new_tot > 21 and new_soft:
                new_tot -= 10
                new_soft = False

            if new_tot > 21:
                res[self.BUST] += prob
            else:
                sub_dist = self.get_dealer_expansion(new_tot, new_soft, next_packed, next_total)
                for k, v in sub_dist.items():
                    res[k] += prob * v

        self._cache[state_key] = res
        return res

    def get_terminal_distribution(
        self,
        upcard: int,
        packed_shoe: int,
        total_cards: int
    ) -> Dict[int, float]:
        """Calcula la fdp terminal normalizada del crupier condicionada a la carta visible."""
        res = {17: 0.0, 18: 0.0, 19: 0.0, 20: 0.0, 21: 0.0, self.BUST: 0.0, self.NATURAL_BJ: 0.0}
        if total_cards == 0:
            res[self.BUST] = 1.0
            return res

        next_total = total_cards - 1

        if self.rules.is_hole_card_game:
            if upcard == 1:
                ten_count = (packed_shoe >> SHIFTS[9]) & MASKS[9]
                non_ten_total = total_cards - ten_count
                if non_ten_total == 0:
                    res[self.BUST] = 1.0
                    return res

                for i in range(9):
                    shift, mask, dec_mask, card_val = CARDS_DATA[i]
                    cnt = (packed_shoe >> shift) & mask
                    if cnt == 0:
                        continue
                    prob = cnt / non_ten_total
                    next_packed = packed_shoe - dec_mask
                    hand_tot = 12 if card_val == 1 else (11 + card_val)
                    sub = self.get_dealer_expansion(hand_tot, True, next_packed, next_total)
                    for k, v in sub.items():
                        res[k] += prob * v
                return res

            elif upcard == 10:
                ace_count = (packed_shoe >> SHIFTS[0]) & MASKS[0]
                non_ace_total = total_cards - ace_count
                if non_ace_total == 0:
                    res[self.BUST] = 1.0
                    return res

                for i in range(1, 10):
                    shift, mask, dec_mask, card_val = CARDS_DATA[i]
                    cnt = (packed_shoe >> shift) & mask
                    if cnt == 0:
                        continue
                    prob = cnt / non_ace_total
                    next_packed = packed_shoe - dec_mask
                    hand_tot = 10 + card_val
                    sub = self.get_dealer_expansion(hand_tot, False, next_packed, next_total)
                    for k, v in sub.items():
                        res[k] += prob * v
                return res

            else:
                for shift, mask, dec_mask, card_val in CARDS_DATA:
                    cnt = (packed_shoe >> shift) & mask
                    if cnt == 0:
                        continue
                    prob = cnt / total_cards
                    next_packed = packed_shoe - dec_mask

                    if card_val == 1:
                        hand_tot = upcard + 11
                        is_soft = True
                    else:
                        hand_tot = upcard + card_val
                        is_soft = False

                    sub = self.get_dealer_expansion(hand_tot, is_soft, next_packed, next_total)
                    for k, v in sub.items():
                        res[k] += prob * v
                return res
        else:
            # Regla ENHC
            for shift, mask, dec_mask, card_val in CARDS_DATA:
                cnt = (packed_shoe >> shift) & mask
                if cnt == 0:
                    continue
                prob = cnt / total_cards
                next_packed = packed_shoe - dec_mask

                if (upcard == 1 and card_val == 10) or (upcard == 10 and card_val == 1):
                    res[self.NATURAL_BJ] += prob
                    continue

                if upcard == 1:
                    hand_tot = 12 if card_val == 1 else (11 + card_val)
                    is_soft = True
                elif card_val == 1:
                    hand_tot = upcard + 11
                    is_soft = True
                else:
                    hand_tot = upcard + card_val
                    is_soft = False

                sub = self.get_dealer_expansion(hand_tot, is_soft, next_packed, next_total)
                for k, v in sub.items():
                    res[k] += prob * v
            return res
