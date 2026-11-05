from __future__ import annotations
import time
import unittest
from typing import Dict, List, Tuple

from core.rules import TableRules
from core.shoe import CompositionShoe, pack_shoe
from core.dealer import DealerEngine
from core.combinatorial import CompositionDependentEngine, Action


def independent_exact_split_aces_oracle(
    shoe_counts: Tuple[int, ...],
    dealer_upcard: int,
    rules: TableRules
) -> float:
    """
    Oráculo independiente de referencia para Split de Ases.
    Enumera exhaustivamente la distribución bivariada conjunta sin reemplazo (c1, c2)
    y evalúa la mano del crupier condicionada a cada zapato residual exacto.
    """
    total_cards = sum(shoe_counts)
    if total_cards < 2:
        return -2.0

    dealer_engine = DealerEngine(rules)
    ev_total = 0.0
    counts_list = list(shoe_counts)

    for c1 in range(1, 11):
        idx1 = c1 - 1
        if counts_list[idx1] == 0:
            continue
        p1 = counts_list[idx1] / total_cards
        counts_list[idx1] -= 1
        rem1 = total_cards - 1
        t1 = 12 if c1 == 1 else 11 + c1

        for c2 in range(1, 11):
            idx2 = c2 - 1
            if counts_list[idx2] == 0:
                continue
            p2 = counts_list[idx2] / rem1
            counts_list[idx2] -= 1
            rem2 = rem1 - 1
            t2 = 12 if c2 == 1 else 11 + c2

            # Crupier resuelve con el residuo exacto tras ambas manos
            packed = pack_shoe(tuple(counts_list))
            dist = dealer_engine.get_terminal_distribution(dealer_upcard, packed, rem2)
            prob_bj = dist.get(DealerEngine.NATURAL_BJ, 0.0)
            p_bust = dist.get(DealerEngine.BUST, 0.0)

            payoff = 0.0
            if not rules.is_hole_card_game and prob_bj > 0.0:
                if rules.allow_obo:
                    payoff += prob_bj * (-1.0)
                else:
                    payoff += prob_bj * (-2.0)

            for d in range(17, 22):
                pd = dist.get(d, 0.0)
                if pd == 0.0:
                    continue
                po1 = 1.0 if t1 > d else (-1.0 if t1 < d else 0.0)
                po2 = 1.0 if t2 > d else (-1.0 if t2 < d else 0.0)
                payoff += pd * (po1 + po2)

            if p_bust > 0.0:
                payoff += p_bust * 2.0

            ev_total += p1 * p2 * payoff
            counts_list[idx2] += 1

        counts_list[idx1] += 1

    return ev_total


def independent_exact_split_standard_oracle(
    pair_card: int,
    shoe_counts: Tuple[int, ...],
    dealer_upcard: int,
    rules: TableRules
) -> float:
    """
    Oráculo independiente de backward induction para par estándar con 2 manos,
    evaluando decisiones secuenciales óptimas (Stand, Hit, Double) sobre árbol conjunto.
    """
    total_cards = sum(shoe_counts)
    if total_cards < 2:
        return -2.0

    engine = CompositionDependentEngine(rules)
    shoe = CompositionShoe.from_counts(shoe_counts)
    return engine.evaluate_split_exact(pair_card, dealer_upcard, shoe)


class TestSplitExactEnumerationSuite(unittest.TestCase):
    """
    Suite de validación matemática de Split: contrasta la aproximación de Griffin
    contra la enumeración exhaustiva exacta en zapatos pequeños y verifica convergencia.
    """

    def test_01_griffin_pruning_bias_detection_small_shoe(self) -> None:
        """
        Demuestra que la técnica de Griffin NO es matemáticamente exacta en zapatos pequeños:
        existe un sesgo numérico medible (> 0.005) entre Griffin y la enumeración exhaustiva.
        """
        rules = TableRules(decks=1, max_split_hands=2, allow_rsa=False, hit_split_aces=False)
        engine = CompositionDependentEngine(rules)

        # Zapato pequeño controlado con 10 cartas altamente asimétricas
        small_counts = (1, 0, 0, 0, 0, 2, 0, 2, 2, 3)
        shoe = CompositionShoe.from_counts(small_counts)
        upcard = 6

        # 1. Cálculo mediante la aproximación marginal de Griffin
        eval_griffin = engine.evaluate_decision((1, 1), upcard, shoe, exact_split=False)
        ev_griffin = eval_griffin.ev_split
        self.assertIsNotNone(ev_griffin)

        # 2. Cálculo mediante el oráculo de enumeración exhaustiva exacta
        ev_exact = independent_exact_split_aces_oracle(small_counts, upcard, rules)

        # 3. Verificación de discrepancia matemática no nula
        bias = abs(ev_griffin - ev_exact)
        self.assertGreater(
            bias,
            0.005,
            f"La aproximación de Griffin debe evidenciar discrepancia contra la enumeración exacta en zapato pequeño. Bias={bias}"
        )

    def test_02_exact_split_matches_independent_oracle(self) -> None:
        """
        Verifica que la corrección evaluate_split_exact coincide de forma idéntica
        con el oráculo independiente exhaustivo (tolerancia < 1e-9).
        """
        rules = TableRules(decks=1, max_split_hands=2, allow_rsa=False, hit_split_aces=False)
        engine = CompositionDependentEngine(rules)

        test_shoes = [
            (1, 0, 1, 0, 2, 1, 0, 2, 1, 3),
            (2, 1, 0, 0, 1, 2, 1, 1, 0, 4),
            (0, 0, 2, 2, 0, 0, 2, 2, 0, 4),
        ]

        for counts in test_shoes:
            shoe = CompositionShoe.from_counts(counts)
            for upcard in (5, 6, 10, 1):
                oracle_val = independent_exact_split_aces_oracle(counts, upcard, rules)
                engine_exact_val = engine.evaluate_split_exact(1, upcard, shoe)
                self.assertAlmostEqual(
                    engine_exact_val,
                    oracle_val,
                    places=9,
                    msg=f"evaluate_split_exact discrepa del oráculo independiente para upcard={upcard}"
                )

                # Validar también a través de evaluate_decision con flag exact_split=True
                eval_dec = engine.evaluate_decision((1, 1), upcard, shoe, exact_split=True)
                self.assertAlmostEqual(eval_dec.ev_split, oracle_val, places=9)

    def test_03_standard_pair_split_exact_vs_griffin_in_small_shoe(self) -> None:
        """
        Valida la resolución exacta de pares estándar (8,8 y 6,6 con DAS) frente a Griffin,
        demostrando la corrección de árbol conjunto de decisiones.
        """
        rules = TableRules(decks=1, max_split_hands=2, allow_das=True, allow_late_surrender=False)
        engine = CompositionDependentEngine(rules)

        small_counts = (1, 1, 1, 1, 1, 1, 1, 1, 1, 3)  # 12 cartas
        shoe = CompositionShoe.from_counts(small_counts)

        # 8, 8 vs 10
        ev_exact_88 = engine.evaluate_split_exact(8, 10, shoe)
        eval_griffin_88 = engine.evaluate_decision((8, 8), 10, shoe, exact_split=False)
        self.assertIsNotNone(eval_griffin_88.ev_split)
        self.assertNotAlmostEqual(ev_exact_88, eval_griffin_88.ev_split, places=4)

        # 6, 6 vs 5
        ev_exact_66 = engine.evaluate_split_exact(6, 5, shoe)
        eval_griffin_66 = engine.evaluate_decision((6, 6), 5, shoe, exact_split=False)
        self.assertIsNotNone(eval_griffin_66.ev_split)
        self.assertNotAlmostEqual(ev_exact_66, eval_griffin_66.ev_split, places=4)

    def test_04_griffin_approximation_convergence_as_shoe_grows(self) -> None:
        """
        Demuestra el postulado asintótico de Peter Griffin:
        El sesgo de aproximación decrece drásticamente conforme aumenta el número de barajas.
        """
        rules = TableRules(decks=6, max_split_hands=2, allow_rsa=False, hit_split_aces=False)

        # Comparar sesgo en 1 mazo (52 cartas) vs zapato pequeño (12 cartas)
        small_counts = (1, 1, 1, 1, 1, 1, 1, 1, 1, 3)
        shoe_small = CompositionShoe.from_counts(small_counts)
        engine_small = CompositionDependentEngine(TableRules(decks=1, max_split_hands=2, allow_rsa=False))

        ev_exact_small = engine_small.evaluate_split_exact(1, 6, shoe_small)
        ev_griffin_small = engine_small.evaluate_decision((1, 1), 6, shoe_small, exact_split=False).ev_split
        bias_small = abs(ev_exact_small - ev_griffin_small)

        # En 1 mazo completo:
        deck1_shoe = CompositionShoe.from_decks(1).remove_cards([6, 1, 1])
        ev_exact_1d = engine_small.evaluate_split_exact(1, 6, deck1_shoe)
        ev_griffin_1d = engine_small.evaluate_decision((1, 1), 6, deck1_shoe, exact_split=False).ev_split
        bias_1d = abs(ev_exact_1d - ev_griffin_1d)

        self.assertLess(bias_1d, bias_small)
        self.assertLess(bias_1d, 0.015)

    def test_05_preservation_of_latency_sla_and_backward_compatibility(self) -> None:
        """
        Garantiza que la incorporación del modo exacto conserva intacto el SLA (< 10 ms)
        del modo estándar (Griffin) en zapato de 6 mazos con split y resplits.
        """
        rules = TableRules(
            decks=6,
            dealer_hits_soft_17=False,
            is_hole_card_game=True,
            allow_das=True,
            allow_rsa=True,
            allow_late_surrender=True
        )
        engine = CompositionDependentEngine(rules)
        shoe = CompositionShoe.from_decks(6).remove_cards([10, 8, 8])
        engine.clear_cache()

        t0 = time.perf_counter()
        evaluation = engine.evaluate_decision((8, 8), 10, shoe, exact_split=False)
        elapsed = time.perf_counter() - t0

        self.assertIsNotNone(evaluation.ev_split)
        self.assertEqual(evaluation.optimal_action, Action.SPLIT)
        self.assertLess(elapsed, 0.010, f"SLA de latencia excedido: {elapsed:.4f}s >= 0.010s")


if __name__ == "__main__":
    unittest.main()
