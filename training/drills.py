from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
import math
import random
from typing import Dict, List, Optional, Tuple

from core.rules import TableRules
from core.shoe import CompositionShoe
from core.counting import CardCounter, CountingSystem, RoundingMode
from core.combinatorial import Action


class DeviationType(Enum):
    ILLUSTRIOUS_18 = auto()
    FAB_4 = auto()


@dataclass(frozen=True, slots=True)
class DeviationScenario:
    scenario_id: str
    hand_name: str
    player_cards: Tuple[int, ...]
    dealer_upcard: int
    index_tc: int
    comparison: str  # '>=' o '<='
    basic_action: Action
    deviation_action: Action
    deviation_type: DeviationType
    explanation: str


# Catálogo canónico completo de Don Schlesinger: Illustrious 18 (incluyendo Seguro #1) y Fab 4
DEVIATION_CATALOG: Tuple[DeviationScenario, ...] = (
    # Illustrious 18 (18 Escenarios)
    DeviationScenario("I18_00", "Insurance vs A", (10, 10), 1, 3, ">=", Action.STAND, Action.INSURANCE, DeviationType.ILLUSTRIOUS_18, "Tomar seguro con TC >= +3 (Índice #1 de Don Schlesinger)"),
    DeviationScenario("I18_01", "16 vs 10", (10, 6), 10, 0, ">=", Action.HIT, Action.STAND, DeviationType.ILLUSTRIOUS_18, "Plantarse 16 vs 10 con TC >= 0"),
    DeviationScenario("I18_02", "15 vs 10", (10, 5), 10, 4, ">=", Action.HIT, Action.STAND, DeviationType.ILLUSTRIOUS_18, "Plantarse 15 vs 10 con TC >= +4"),
    DeviationScenario("I18_03", "10,10 vs 5", (10, 10), 5, 5, ">=", Action.STAND, Action.SPLIT, DeviationType.ILLUSTRIOUS_18, "Dividir dieces vs 5 con TC >= +5"),
    DeviationScenario("I18_04", "10,10 vs 6", (10, 10), 6, 4, ">=", Action.STAND, Action.SPLIT, DeviationType.ILLUSTRIOUS_18, "Dividir dieces vs 6 con TC >= +4"),
    DeviationScenario("I18_05", "10 vs 10", (6, 4), 10, 4, ">=", Action.HIT, Action.DOUBLE, DeviationType.ILLUSTRIOUS_18, "Doblar 10 vs 10 con TC >= +4"),
    DeviationScenario("I18_06", "12 vs 3", (9, 3), 3, 2, ">=", Action.HIT, Action.STAND, DeviationType.ILLUSTRIOUS_18, "Plantarse 12 vs 3 con TC >= +2"),
    DeviationScenario("I18_07", "12 vs 2", (10, 2), 2, 3, ">=", Action.HIT, Action.STAND, DeviationType.ILLUSTRIOUS_18, "Plantarse 12 vs 2 con TC >= +3"),
    DeviationScenario("I18_08", "11 vs A", (6, 5), 1, 1, ">=", Action.HIT, Action.DOUBLE, DeviationType.ILLUSTRIOUS_18, "Doblar 11 vs As con TC >= +1"),
    DeviationScenario("I18_09", "9 vs 2", (7, 2), 2, 1, ">=", Action.HIT, Action.DOUBLE, DeviationType.ILLUSTRIOUS_18, "Doblar 9 vs 2 con TC >= +1"),
    DeviationScenario("I18_10", "10 vs A", (7, 3), 1, 4, ">=", Action.HIT, Action.DOUBLE, DeviationType.ILLUSTRIOUS_18, "Doblar 10 vs As con TC >= +4"),
    DeviationScenario("I18_11", "9 vs 7", (5, 4), 7, 3, ">=", Action.HIT, Action.DOUBLE, DeviationType.ILLUSTRIOUS_18, "Doblar 9 vs 7 con TC >= +3"),
    DeviationScenario("I18_12", "16 vs 9", (10, 6), 9, 5, ">=", Action.HIT, Action.STAND, DeviationType.ILLUSTRIOUS_18, "Plantarse 16 vs 9 con TC >= +5"),
    DeviationScenario("I18_13", "13 vs 2", (10, 3), 2, -1, ">=", Action.HIT, Action.STAND, DeviationType.ILLUSTRIOUS_18, "Plantarse 13 vs 2 con TC >= -1"),
    DeviationScenario("I18_14", "12 vs 4", (8, 4), 4, 0, ">=", Action.HIT, Action.STAND, DeviationType.ILLUSTRIOUS_18, "Plantarse 12 vs 4 con TC >= 0"),
    DeviationScenario("I18_15", "12 vs 5", (7, 5), 5, -2, ">=", Action.HIT, Action.STAND, DeviationType.ILLUSTRIOUS_18, "Plantarse 12 vs 5 con TC >= -2"),
    DeviationScenario("I18_16", "12 vs 6", (10, 2), 6, -1, ">=", Action.HIT, Action.STAND, DeviationType.ILLUSTRIOUS_18, "Plantarse 12 vs 6 con TC >= -1"),
    DeviationScenario("I18_17", "13 vs 3", (9, 4), 3, -2, ">=", Action.HIT, Action.STAND, DeviationType.ILLUSTRIOUS_18, "Plantarse 13 vs 3 con TC >= -2"),
    # Fab 4 (Late Surrender - 4 Escenarios)
    DeviationScenario("F4_01", "15 vs 10", (10, 5), 10, 0, ">=", Action.HIT, Action.SURRENDER, DeviationType.FAB_4, "Rendirse 15 vs 10 con TC >= 0"),
    DeviationScenario("F4_02", "14 vs 10", (9, 5), 10, 3, ">=", Action.HIT, Action.SURRENDER, DeviationType.FAB_4, "Rendirse 14 vs 10 con TC >= +3"),
    DeviationScenario("F4_03", "15 vs 9", (10, 5), 9, 2, ">=", Action.HIT, Action.SURRENDER, DeviationType.FAB_4, "Rendirse 15 vs 9 con TC >= +2"),
    DeviationScenario("F4_04", "15 vs A", (8, 7), 1, 1, ">=", Action.HIT, Action.SURRENDER, DeviationType.FAB_4, "Rendirse 15 vs As con TC >= +1"),
)


@dataclass(frozen=True, slots=True)
class DeckEstimationResult:
    actual_cards_remaining: int
    actual_decks_remaining: float
    user_estimated_decks: float
    deck_error: float
    running_count: float
    actual_true_count: int
    erroneous_true_count: int
    tc_distortion: int
    is_acceptable: bool


class DeckEstimationDrill:
    """Entrenador para calibración visual de residuo de zapato y bandeja de descarte."""

    def __init__(self, total_decks: int = 6, resolution: float = 0.5) -> None:
        self.total_decks: int = total_decks
        self.resolution: float = resolution
        self.total_cards: int = total_decks * 52

    def generate_trial(self, min_cards_dealt: int = 20, max_cards_dealt: int = 260) -> Tuple[int, int, float]:
        cards_dealt = random.randint(min_cards_dealt, max_cards_dealt)
        cards_remaining = self.total_cards - cards_dealt
        exact_decks = cards_remaining / 52.0
        return cards_dealt, cards_remaining, exact_decks

    def evaluate_estimate(
        self,
        cards_remaining: int,
        user_estimate: float,
        sample_rc: float,
        rounding_mode: RoundingMode = RoundingMode.FLOOR
    ) -> DeckEstimationResult:
        actual_decks = cards_remaining / 52.0
        deck_error = abs(user_estimate - actual_decks)

        actual_tc_float = sample_rc / max(0.25, actual_decks)
        erroneous_tc_float = sample_rc / max(0.25, user_estimate)

        if rounding_mode == RoundingMode.FLOOR:
            actual_tc = math.floor(actual_tc_float)
            erroneous_tc = math.floor(erroneous_tc_float)
        elif rounding_mode == RoundingMode.TRUNCATE:
            actual_tc = int(actual_tc_float)
            erroneous_tc = int(erroneous_tc_float)
        elif rounding_mode == RoundingMode.ROUND:
            actual_tc = round(actual_tc_float)
            erroneous_tc = round(erroneous_tc_float)
        else:
            raise ValueError(f"Modo de redondeo no soportado: {rounding_mode}")

        tc_distortion = abs(erroneous_tc - actual_tc)
        is_acceptable = deck_error <= (self.resolution / 2.0)

        return DeckEstimationResult(
            actual_cards_remaining=cards_remaining,
            actual_decks_remaining=actual_decks,
            user_estimated_decks=user_estimate,
            deck_error=deck_error,
            running_count=sample_rc,
            actual_true_count=actual_tc,
            erroneous_true_count=erroneous_tc,
            tc_distortion=tc_distortion,
            is_acceptable=is_acceptable
        )


@dataclass(frozen=True, slots=True)
class SpeedCountCard:
    val: int
    suit: str
    weight: float


class SpeedCountDrill:
    """Entrenador de alta cadencia para conteo contrarreloj y cancelación de pares."""

    DECK_WEIGHTS: Tuple[int, ...] = (4, 4, 4, 4, 4, 4, 4, 4, 4, 16)
    RANKS: Tuple[int, ...] = tuple(range(1, 11))
    LOW_RANKS: Tuple[int, ...] = (2, 3, 4, 5, 6)
    LOW_WEIGHTS: Tuple[int, ...] = (4, 4, 4, 4, 4)
    HIGH_RANKS: Tuple[int, ...] = (1, 10)
    HIGH_WEIGHTS: Tuple[int, ...] = (4, 16)
    NEUTRAL_RANKS: Tuple[int, ...] = (7, 8, 9)
    NEUTRAL_WEIGHTS: Tuple[int, ...] = (4, 4, 4)

    def __init__(self, system: CountingSystem = CountingSystem.HI_LO) -> None:
        self.counter = CardCounter(system=system)
        self.system = system
        self._suits = ("♠", "♥", "♦", "♣")

    def reset(self) -> None:
        self.counter.reset()

    def generate_single_card(self) -> SpeedCountCard:
        val = random.choices(self.RANKS, weights=self.DECK_WEIGHTS)[0]
        suit = random.choice(self._suits)
        self.counter.update(val)
        weight = self.counter._weights[val - 1]
        return SpeedCountCard(val=val, suit=suit, weight=weight)

    def generate_pair(self, cancelable_probability: float = 0.5) -> Tuple[SpeedCountCard, SpeedCountCard]:
        if random.random() < cancelable_probability:
            # 80% pares (+1 y -1), 20% pares neutros (0 y 0)
            if random.random() < 0.8:
                low_val = random.choices(self.LOW_RANKS, weights=self.LOW_WEIGHTS)[0]
                high_val = random.choices(self.HIGH_RANKS, weights=self.HIGH_WEIGHTS)[0]
                c1_val, c2_val = (low_val, high_val) if random.random() < 0.5 else (high_val, low_val)
            else:
                c1_val = random.choices(self.NEUTRAL_RANKS, weights=self.NEUTRAL_WEIGHTS)[0]
                c2_val = random.choices(self.NEUTRAL_RANKS, weights=self.NEUTRAL_WEIGHTS)[0]
        else:
            c1_val = random.choices(self.RANKS, weights=self.DECK_WEIGHTS)[0]
            c2_val = random.choices(self.RANKS, weights=self.DECK_WEIGHTS)[0]

        s1 = random.choice(self._suits)
        s2 = random.choice(self._suits)

        self.counter.update(c1_val)
        self.counter.update(c2_val)

        w1 = self.counter._weights[c1_val - 1]
        w2 = self.counter._weights[c2_val - 1]

        return SpeedCountCard(c1_val, s1, w1), SpeedCountCard(c2_val, s2, w2)


@dataclass(frozen=True, slots=True)
class DeviationTrial:
    scenario: DeviationScenario
    simulated_tc: int
    correct_action: Action
    is_deviation: bool


class IndexDeviationDrill:
    """Generador de escenarios en los límites críticos de True Count."""

    def __init__(self, scenarios: Tuple[DeviationScenario, ...] = DEVIATION_CATALOG) -> None:
        self.scenarios = scenarios

    def generate_trial(self) -> DeviationTrial:
        scenario = random.choice(self.scenarios)
        offset = random.choice((-2, -1, 0, 1, 2))
        simulated_tc = scenario.index_tc + offset

        if scenario.comparison == ">=":
            is_deviation = simulated_tc >= scenario.index_tc
        else:
            is_deviation = simulated_tc <= scenario.index_tc

        correct_action = scenario.deviation_action if is_deviation else scenario.basic_action
        return DeviationTrial(
            scenario=scenario,
            simulated_tc=simulated_tc,
            correct_action=correct_action,
            is_deviation=is_deviation
        )
