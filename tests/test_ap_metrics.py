from __future__ import annotations
import math
import unittest

from core.rules import TableRules
from core.shoe import CompositionShoe
from core.combinatorial import CompositionDependentEngine, Action, DecisionEvaluation
from core.counting import CardCounter, CountingSystem, RoundingMode
from core.ap_metrics import AdvantagePlayMetrics, KellyFraction


class TestAPMetricsSuite(unittest.TestCase):
    def test_01_split_limits_and_zero_division_guard(self) -> None:
        shoe = CompositionShoe.from_decks(6).remove_cards([6, 8, 8])

        rules_no_split = TableRules(decks=6, max_split_hands=1)
        eval_no_split = CompositionDependentEngine(rules_no_split).evaluate_decision((8, 8), 6, shoe)
        self.assertIsNone(eval_no_split.ev_split)
        self.assertNotEqual(eval_no_split.optimal_action, Action.SPLIT)

        rules_single_split = TableRules(decks=6, max_split_hands=2)
        eval_single_split = CompositionDependentEngine(rules_single_split).evaluate_decision((8, 8), 6, shoe)
        self.assertIsNotNone(eval_single_split.ev_split)

        rules_multi_split = TableRules(decks=6, max_split_hands=4)
        eval_multi_split = CompositionDependentEngine(rules_multi_split).evaluate_decision((8, 8), 6, shoe)
        self.assertGreaterEqual(eval_multi_split.ev_split, eval_single_split.ev_split)

        shoe_empty = CompositionShoe.from_counts((0,) * 10)
        rules_american = TableRules(decks=6, is_hole_card_game=True, blackjack_payout=1.5)
        eval_empty = CompositionDependentEngine(rules_american).evaluate_decision((1, 10), 10, shoe_empty)
        self.assertEqual(eval_empty.optimal_action, Action.STAND)
        self.assertAlmostEqual(eval_empty.optimal_ev, 1.5, places=9)

    def test_02_obo_rule_behavior_in_enhc(self) -> None:
        rules_pure_enhc = TableRules(
            decks=6, is_hole_card_game=False, allow_obo=False, allow_late_surrender=False, allow_rsa=False
        )
        engine_pure = CompositionDependentEngine(rules_pure_enhc)

        rules_obo = TableRules(
            decks=6, is_hole_card_game=False, allow_obo=True, allow_late_surrender=False, allow_rsa=False
        )
        engine_obo = CompositionDependentEngine(rules_obo)

        shoe_double = CompositionShoe.from_decks(6).remove_cards([10, 9, 2])
        eval_double_pure = engine_pure.evaluate_decision((9, 2), 10, shoe_double)
        eval_double_obo = engine_obo.evaluate_decision((9, 2), 10, shoe_double)

        self.assertIsNotNone(eval_double_pure.ev_double)
        self.assertIsNotNone(eval_double_obo.ev_double)

        prob_dealer_bj_double = eval_double_pure.dealer_distribution[210]
        self.assertGreater(prob_dealer_bj_double, 0.05)
        diff_double = eval_double_obo.ev_double - eval_double_pure.ev_double
        self.assertAlmostEqual(diff_double, prob_dealer_bj_double, places=6)

        shoe_split = CompositionShoe.from_decks(6).remove_cards([10, 1, 1])
        eval_split_pure = engine_pure.evaluate_decision((1, 1), 10, shoe_split)
        eval_split_obo = engine_obo.evaluate_decision((1, 1), 10, shoe_split)

        self.assertIsNotNone(eval_split_pure.ev_split)
        self.assertIsNotNone(eval_split_obo.ev_split)

        prob_dealer_bj_split = eval_split_pure.dealer_distribution[210]
        self.assertGreater(prob_dealer_bj_split, 0.05)
        diff_split = eval_split_obo.ev_split - eval_split_pure.ev_split
        self.assertAlmostEqual(diff_split, prob_dealer_bj_split, places=6)

    def test_03_card_counter_true_count_and_ace_surplus(self) -> None:
        counter_floor = CardCounter(system=CountingSystem.HI_LO, rounding_mode=RoundingMode.FLOOR, deck_resolution=0.5)
        counter_trunc = CardCounter(system=CountingSystem.HI_LO, rounding_mode=RoundingMode.TRUNCATE, deck_resolution=0.5)

        counter_floor._running_count = -3.0
        counter_trunc._running_count = -3.0
        self.assertEqual(counter_floor.get_true_count(104), -2)
        self.assertEqual(counter_trunc.get_true_count(104), -1)

        counter_round = CardCounter(system=CountingSystem.HI_LO, rounding_mode=RoundingMode.ROUND, deck_resolution=0.5)
        counter_floor._running_count = 3.6
        counter_trunc._running_count = 3.6
        counter_round._running_count = 3.6
        self.assertEqual(counter_floor.get_true_count(104), 1)
        self.assertEqual(counter_trunc.get_true_count(104), 1)
        self.assertEqual(counter_round.get_true_count(104), 2)

        counter_aces = CardCounter(system=CountingSystem.OMEGA_II)
        self.assertAlmostEqual(counter_aces.get_ace_surplus(312, 6), 0.0, places=6)

        for _ in range(52):
            counter_aces.update(10)
        self.assertAlmostEqual(counter_aces.get_ace_surplus(260, 6), 4.0, places=6)

    def test_04_fractional_kelly_sizing_and_limits(self) -> None:
        bankroll = 10_000.0

        bet_neg = AdvantagePlayMetrics.recommend_bet(
            bankroll=bankroll, true_count=0, min_bet=10.0, max_bet=150.0, allow_wong_out=False
        )
        self.assertEqual(bet_neg.recommended_stake, 10.0)

        bet_wong = AdvantagePlayMetrics.recommend_bet(
            bankroll=bankroll, true_count=0, min_bet=10.0, max_bet=150.0, allow_wong_out=True
        )
        self.assertEqual(bet_wong.recommended_stake, 0.0)
        self.assertTrue(bet_wong.should_wong_out)

        bet_pos = AdvantagePlayMetrics.recommend_bet(
            bankroll=bankroll,
            true_count=4,
            kelly_fraction=KellyFraction.HALF,
            variance=1.32,
            min_bet=10.0,
            max_bet=150.0,
            chip_unit=5.0,
        )
        self.assertEqual(bet_pos.recommended_stake, 55.0)

        bet_max = AdvantagePlayMetrics.recommend_bet(
            bankroll=100_000.0, true_count=4, min_bet=10.0, max_bet=150.0, chip_unit=5.0
        )
        self.assertEqual(bet_max.recommended_stake, 150.0)

    def test_05_evaluate_hand_with_counting_integration(self) -> None:
        rules = TableRules(decks=6)
        engine = CompositionDependentEngine(rules)
        counter = CardCounter(system=CountingSystem.HI_LO, rounding_mode=RoundingMode.FLOOR)

        cards_played = [2, 3, 4, 5, 6, 2, 3, 4, 5, 6]
        counter.update_multiple(cards_played)

        shoe = CompositionShoe.from_decks(6).remove_cards(cards_played)
        eval_cd, tc, edge = engine.evaluate_hand_with_counting((10, 6), 10, shoe, counter)

        self.assertIsInstance(eval_cd, DecisionEvaluation)
        self.assertIsInstance(tc, int)
        self.assertIsInstance(edge, float)
        self.assertGreater(tc, 0)
        self.assertGreater(edge, -0.005)

    def test_06_schlesinger_canonical_n0_and_score(self) -> None:
        schlesinger_game_data = [
            (-2, 0.185, -0.0145, 1.0),
            (-1, 0.134, -0.0095, 1.0),
            (0,  0.230, -0.0045, 1.0),
            (1,  0.165,  0.0005, 1.0),
            (2,  0.115,  0.0055, 2.0),
            (3,  0.072,  0.0105, 4.0),
            (4,  0.044,  0.0155, 8.0),
            (5,  0.027,  0.0205, 12.0),
            (6,  0.028,  0.0260, 12.0),
        ]

        metrics = AdvantagePlayMetrics.evaluate_game_spread(
            tc_distribution=schlesinger_game_data, bankroll=10_000.0, base_variance=1.32
        )

        self.assertAlmostEqual(metrics.score, 1_000_000.0 / metrics.n_zero, places=6)
        self.assertTrue(10_000 < metrics.n_zero < 60_000)
        self.assertTrue(15.0 < metrics.score < 100.0)
        self.assertAlmostEqual(metrics.risk_of_ruin, 0.1353, places=2)

    def test_07_obo_split_das_invariant(self) -> None:
        rules_pure = TableRules(decks=1, is_hole_card_game=False, allow_obo=False)
        rules_obo = TableRules(decks=1, is_hole_card_game=False, allow_obo=True)
        engine_pure = CompositionDependentEngine(rules_pure)
        engine_obo = CompositionDependentEngine(rules_obo)

        counts = [0] * 10
        counts[0] = 1
        counts[9] = 1
        shoe = CompositionShoe(tuple(counts))

        eval_pure = engine_pure.evaluate_decision((5, 5), 10, shoe)
        eval_obo = engine_obo.evaluate_decision((5, 5), 10, shoe)

        self.assertAlmostEqual(eval_obo.ev_double - eval_pure.ev_double, 0.5, places=6)
        self.assertAlmostEqual(eval_obo.ev_split - eval_pure.ev_split, 0.5, places=6)