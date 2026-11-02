from __future__ import annotations
import random
import time
import unittest

from core.rules import TableRules
from core.shoe import CompositionShoe, pack_shoe, unpack_shoe
from core.dealer import DealerEngine
from core.combinatorial import CompositionDependentEngine, Action


class TestAPMasterSuite(unittest.TestCase):
    def test_01_cold_cache_latency_full_split_sla(self) -> None:
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
        evaluation = engine.evaluate_decision((8, 8), 10, shoe)
        elapsed = time.perf_counter() - t0
        self.assertIsNotNone(evaluation.ev_double)
        self.assertIsNotNone(evaluation.ev_split)
        self.assertIsNotNone(evaluation.ev_surrender)
        self.assertLess(elapsed, 0.010)

    def test_02_natural_blackjack_payouts_and_dealer_peek(self) -> None:
        rules_32 = TableRules(decks=6, blackjack_payout=1.5, is_hole_card_game=True)
        engine_32 = CompositionDependentEngine(rules_32)
        shoe_neutral = CompositionShoe.from_decks(6).remove_cards([6, 1, 10])
        eval_32 = engine_32.evaluate_decision((1, 10), 6, shoe_neutral)
        self.assertEqual(eval_32.optimal_action, Action.STAND)
        self.assertIsNone(eval_32.ev_hit)
        self.assertAlmostEqual(eval_32.optimal_ev, 1.5, places=9)

        rules_65 = TableRules(decks=6, blackjack_payout=1.2, is_hole_card_game=True)
        engine_65 = CompositionDependentEngine(rules_65)
        eval_65 = engine_65.evaluate_decision((1, 10), 6, shoe_neutral)
        self.assertAlmostEqual(eval_65.optimal_ev, 1.2, places=9)

        shoe_up10 = CompositionShoe.from_decks(6).remove_cards([10, 1, 10])
        prob_dealer_ace = shoe_up10.counts[0] / shoe_up10.total_cards
        expected_ev = (1.0 - prob_dealer_ace) * 1.5
        eval_peek = engine_32.evaluate_decision((1, 10), 10, shoe_up10)
        self.assertAlmostEqual(eval_peek.optimal_ev, expected_ev, places=9)

    def test_03_hole_card_peek_conditioning_effect(self) -> None:
        rules_am = TableRules(decks=6, is_hole_card_game=True)
        dealer_am = DealerEngine(rules_am)
        rules_enhc = TableRules(decks=6, is_hole_card_game=False)
        dealer_enhc = DealerEngine(rules_enhc)

        shoe = CompositionShoe.from_decks(6).remove(10)
        dist_am = dealer_am.get_terminal_distribution(10, shoe.packed, shoe.total_cards)
        dist_enhc = dealer_enhc.get_terminal_distribution(10, shoe.packed, shoe.total_cards)
        self.assertEqual(dist_am[DealerEngine.NATURAL_BJ], 0.0)
        self.assertGreater(dist_enhc[DealerEngine.NATURAL_BJ], 0.05)
        self.assertNotAlmostEqual(dist_am[21], dist_enhc[21], places=3)

    def test_04_resplit_aces_differential(self) -> None:
        shoe = CompositionShoe.from_decks(6).remove_cards([6, 1, 1])
        rules_no_rsa = TableRules(decks=6, allow_rsa=False, hit_split_aces=False)
        rules_rsa = TableRules(decks=6, allow_rsa=True, hit_split_aces=False)
        ev_no_rsa = CompositionDependentEngine(rules_no_rsa).evaluate_decision((1, 1), 6, shoe).ev_split
        ev_rsa = CompositionDependentEngine(rules_rsa).evaluate_decision((1, 1), 6, shoe).ev_split
        self.assertIsNotNone(ev_no_rsa)
        self.assertIsNotNone(ev_rsa)
        self.assertGreater(ev_rsa - ev_no_rsa, 0.10)

        rules_hit_no_rsa = TableRules(decks=6, allow_rsa=False, hit_split_aces=True)
        rules_hit_rsa = TableRules(decks=6, allow_rsa=True, hit_split_aces=True)
        ev_hit_no_rsa = CompositionDependentEngine(rules_hit_no_rsa).evaluate_decision((1, 1), 6, shoe).ev_split
        ev_hit_rsa = CompositionDependentEngine(rules_hit_rsa).evaluate_decision((1, 1), 6, shoe).ev_split
        self.assertIsNotNone(ev_hit_no_rsa)
        self.assertIsNotNone(ev_hit_rsa)
        self.assertGreater(ev_hit_rsa, ev_hit_no_rsa)

    def test_05_insurance_edge_and_threshold(self) -> None:
        rules = TableRules(decks=6)
        engine = CompositionDependentEngine(rules)
        shoe_neutral = CompositionShoe.from_decks(6).remove(1)
        ins_neutral = engine.evaluate_insurance(shoe_neutral)
        self.assertFalse(ins_neutral.is_positive_ev)
        self.assertAlmostEqual(ins_neutral.ev_insurance, 1.5 * (96.0 / 311.0) - 0.5, places=6)

        rich_counts = (6, 6, 6, 6, 6, 6, 6, 6, 12, 40)
        shoe_rich = CompositionShoe.from_counts(rich_counts)
        ins_rich = engine.evaluate_insurance(shoe_rich)
        self.assertTrue(ins_rich.is_positive_ev)
        self.assertAlmostEqual(ins_rich.prob_ten, 0.40, places=6)
        self.assertAlmostEqual(ins_rich.ev_insurance, 0.10, places=6)

    def test_06_surrender_frontiers_american_vs_enhc(self) -> None:
        shoe_88 = CompositionShoe.from_decks(6).remove_cards([10, 8, 8])
        rules_am = TableRules(decks=6, allow_late_surrender=True, allow_das=True, is_hole_card_game=True)
        eval_88_am = CompositionDependentEngine(rules_am).evaluate_decision((8, 8), 10, shoe_88)
        self.assertEqual(eval_88_am.ev_surrender, -0.50)
        self.assertGreater(eval_88_am.ev_split, -0.50)
        self.assertEqual(eval_88_am.optimal_action, Action.SPLIT)

        shoe_16 = CompositionShoe.from_decks(6).remove_cards([10, 10, 6])
        eval_16 = CompositionDependentEngine(rules_am).evaluate_decision((10, 6), 10, shoe_16)
        self.assertEqual(eval_16.ev_surrender, -0.50)
        self.assertLess(eval_16.ev_stand, -0.50)
        self.assertLess(eval_16.ev_hit, -0.50)
        self.assertEqual(eval_16.optimal_action, Action.SURRENDER)

        rules_enhc = TableRules(decks=6, allow_late_surrender=True, allow_das=False, is_hole_card_game=False)
        eval_enhc = CompositionDependentEngine(rules_enhc).evaluate_decision((8, 8), 10, shoe_88)
        self.assertEqual(eval_enhc.ev_surrender, -0.50)
        self.assertLess(eval_enhc.ev_split, -0.50)
        self.assertEqual(eval_enhc.optimal_action, Action.SURRENDER)

    def test_07_cd_sensitivity_16_vs_10_griffin(self) -> None:
        rules = TableRules(decks=1, dealer_hits_soft_17=False, allow_late_surrender=False)
        engine = CompositionDependentEngine(rules)

        shoe_a = CompositionShoe.from_decks(1).remove_cards([10, 10, 6])
        eval_a = engine.evaluate_decision((10, 6), 10, shoe_a)
        self.assertGreater(eval_a.ev_hit, eval_a.ev_stand)
        self.assertEqual(eval_a.optimal_action, Action.HIT)

        engine.clear_cache()
        shoe_b = CompositionShoe.from_decks(1).remove_cards([10, 4, 5, 7])
        eval_b = engine.evaluate_decision((4, 5, 7), 10, shoe_b)
        self.assertGreater(eval_b.ev_stand, eval_b.ev_hit)
        self.assertEqual(eval_b.optimal_action, Action.STAND)

    def test_08_cd_sensitivity_12_vs_4_griffin(self) -> None:
        rules = TableRules(decks=1, dealer_hits_soft_17=False, allow_late_surrender=False)
        engine = CompositionDependentEngine(rules)

        shoe_a = CompositionShoe.from_decks(1).remove_cards([4, 10, 2])
        eval_a = engine.evaluate_decision((10, 2), 4, shoe_a)
        self.assertGreater(eval_a.ev_hit, eval_a.ev_stand)
        self.assertEqual(eval_a.optimal_action, Action.HIT)

        engine.clear_cache()
        shoe_b = CompositionShoe.from_decks(1).remove_cards([4, 3, 4, 5])
        eval_b = engine.evaluate_decision((3, 4, 5), 4, shoe_b)
        self.assertGreater(eval_b.ev_stand, eval_b.ev_hit)
        self.assertEqual(eval_b.optimal_action, Action.STAND)

    def test_09_extreme_shoes_and_edge_cases(self) -> None:
        rules = TableRules(decks=1, dealer_hits_soft_17=False)
        engine = CompositionDependentEngine(rules)

        counts_no_tens = (4, 4, 4, 4, 4, 4, 4, 4, 4, 0)
        shoe_no_tens = CompositionShoe.from_counts(counts_no_tens)
        eval_no_tens = engine.evaluate_decision((10, 6), 10, shoe_no_tens)
        self.assertTrue(-1.0 <= eval_no_tens.optimal_ev <= 1.0)

        engine.clear_cache()
        counts_tens_aces = (8, 0, 0, 0, 0, 0, 0, 0, 0, 24)
        shoe_tens_aces = CompositionShoe.from_counts(counts_tens_aces)
        dealer = DealerEngine(rules)
        dist_tens_aces = dealer.get_terminal_distribution(10, shoe_tens_aces.packed, shoe_tens_aces.total_cards)
        self.assertEqual(dist_tens_aces[DealerEngine.BUST], 0.0)
        self.assertAlmostEqual(sum(dist_tens_aces.values()), 1.0, places=9)

        engine.clear_cache()
        counts_single = (0, 0, 0, 0, 0, 0, 1, 0, 0, 0)
        shoe_single = CompositionShoe.from_counts(counts_single)
        eval_single = engine.evaluate_decision((10, 2), 6, shoe_single)
        self.assertIsNotNone(eval_single.optimal_action)
        self.assertTrue(-2.0 <= eval_single.optimal_ev <= 2.0)

    def test_10_bijective_64bit_hash(self) -> None:
        rng = random.Random(42)
        for _ in range(100_000):
            sample = tuple(rng.randint(0, 32) for _ in range(9)) + (rng.randint(0, 128),)
            packed = pack_shoe(sample)
            unpacked = unpack_shoe(packed)
            self.assertEqual(sample, unpacked)
