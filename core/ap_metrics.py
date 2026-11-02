from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import math
from typing import Dict, List, Optional, Tuple

class KellyFraction(Enum):
    """Fracciones operativas comunes del Criterio de Kelly."""
    FULL = 1.0
    HALF = 0.5
    QUARTER = 0.25

@dataclass(frozen=True, slots=True)
class BetRecommendation:
    """Recomendación cuantitativa de apuesta estructurada."""
    true_count: int
    player_edge: float
    kelly_fraction: float
    unbounded_stake: float
    recommended_stake: float
    should_wong_out: bool

@dataclass(frozen=True, slots=True)
class GamePerformanceMetrics:
    """Analítica global de rendimiento, riesgo y expectativa de sesión."""
    ev_per_hand: float
    variance_per_hand: float
    std_dev_per_hand: float
    n_zero: float
    score: float
    hourly_win_rate_100: float
    risk_of_ruin: float
    optimal_kelly_unit: float


class AdvantagePlayMetrics:
    """
    Motor analítico de finanzas cuantitativas aplicadas a Blackjack.
    Implementa métricas de Don Schlesinger (SCORE, N-0) y Criterio de Kelly.
    """

    @staticmethod
    def compute_player_edge(true_count: int, base_edge: float = -0.005, slope: float = 0.005) -> float:
        """
        Estima la ventaja del jugador: Edge = Base + (TC * Slope).
        Por defecto, para 6D S17 DAS: Base ~ -0.50%, pendiente ~ +0.50% por cada unidad de TC.
        """
        return base_edge + (true_count * slope)

    @staticmethod
    def compute_kelly_fractional(edge: float, variance: float, fraction: float = 1.0) -> float:
        """
        Fracción óptima de Kelly: f* = fraction * (Edge / Variance).
        Si Edge <= 0, f* = 0.0.
        """
        if edge <= 0.0 or variance <= 0.0:
            return 0.0
        return fraction * (edge / variance)

    @classmethod
    def recommend_bet(
        cls,
        bankroll: float,
        true_count: int,
        base_edge: float = -0.005,
        slope: float = 0.005,
        variance: float = 1.32,
        kelly_fraction: KellyFraction = KellyFraction.HALF,
        min_bet: float = 10.0,
        max_bet: float = 120.0,
        chip_unit: float = 5.0,
        allow_wong_out: bool = False,
    ) -> BetRecommendation:
        """Calcula el tamaño monetario de apuesta acotado a los límites de la mesa."""
        if bankroll <= 0.0:
            raise ValueError(f"Bankroll debe ser positivo: {bankroll}")
        if min_bet <= 0.0 or max_bet < min_bet:
            raise ValueError(f"Rango de apuestas inválido: [{min_bet}, {max_bet}]")

        edge = cls.compute_player_edge(true_count, base_edge, slope)
        f_star = cls.compute_kelly_fractional(edge, variance, fraction=kelly_fraction.value)
        unbounded = f_star * bankroll

        should_wong_out = (edge <= 0.0 and allow_wong_out)

        if edge <= 0.0:
            recommended = 0.0 if should_wong_out else min_bet
        else:
            raw_stake = max(min_bet, min(max_bet, unbounded))
            # Ajuste a la denominación física de ficha más cercana
            recommended = round(raw_stake / chip_unit) * chip_unit
            recommended = max(min_bet, min(max_bet, recommended))

        return BetRecommendation(
            true_count=true_count,
            player_edge=edge,
            kelly_fraction=f_star,
            unbounded_stake=unbounded,
            recommended_stake=recommended,
            should_wong_out=should_wong_out,
        )

    @staticmethod
    def compute_n_zero(variance_per_hand: float, ev_per_hand: float) -> float:
        """
        Calcula N-0: manos necesarias para que la ganancia esperada supere 1 desviación estándar.
        N_0 = Variance / (EV^2). Si EV <= 0, N_0 = infinito.
        """
        if ev_per_hand <= 0.0:
            return float("inf")
        if variance_per_hand <= 0.0:
            return 0.0
        return variance_per_hand / (ev_per_hand ** 2)

    @classmethod
    def compute_score(cls, n_zero: float) -> float:
        """
        SCORE de Don Schlesinger: Ganancia esperada por cada 100 manos bajo bankroll estándar
        de $10,000 con riesgo de ruina acotado al 13.53% (Full Kelly).
        SCORE = 1,000,000 / N_0.
        """
        if n_zero <= 0.0 or math.isinf(n_zero):
            return 0.0
        return 1_000_000.0 / n_zero

    @staticmethod
    def compute_risk_of_ruin(bankroll: float, ev_per_hand: float, variance_per_hand: float) -> float:
        """
        Riesgo de Ruina (RoR) analítico continuo: RoR = exp(-2 * EV * Bankroll / Variance).
        Si EV <= 0, RoR = 1.0 (100%).
        """
        if ev_per_hand <= 0.0:
            return 1.0
        if bankroll <= 0.0:
            return 1.0
        if variance_per_hand <= 0.0:
            return 0.0

        exponent = (-2.0 * ev_per_hand * bankroll) / variance_per_hand
        if exponent < -700.0:
            return 0.0
        return math.exp(exponent)

    @classmethod
    def evaluate_game_spread(
        cls,
        tc_distribution: List[Tuple[int, float, float, float]],
        bankroll: float = 10_000.0,
        base_variance: float = 1.32,
    ) -> GamePerformanceMetrics:
        """
        Evalúa un juego completo a partir de la distribución de True Counts.
        tc_distribution: lista de tuplas (true_count, frecuencia, edge_frac, bet_units).
        """
        total_freq = sum(f for _, f, _, _ in tc_distribution)
        if not math.isclose(total_freq, 1.0, rel_tol=1e-3):
            raise ValueError(f"Las frecuencias de TC deben sumar 1.0, suma={total_freq}")

        ev_hand = sum(f * b * e for _, f, e, b in tc_distribution)
        var_hand = sum(f * ((b ** 2) * base_variance + ((b * e - ev_hand) ** 2)) for _, f, e, b in tc_distribution)
        std_dev = math.sqrt(var_hand) if var_hand > 0.0 else 0.0

        n0 = cls.compute_n_zero(var_hand, ev_hand)
        score = cls.compute_score(n0)

        optimal_unit = bankroll * (ev_hand / var_hand) if (var_hand > 0.0 and ev_hand > 0.0) else 0.0
        hourly_win_100 = 100.0 * optimal_unit * ev_hand if optimal_unit > 0.0 else 0.0
        ror = cls.compute_risk_of_ruin(bankroll / optimal_unit, ev_hand, var_hand) if optimal_unit > 0.0 else 1.0

        return GamePerformanceMetrics(
            ev_per_hand=ev_hand,
            variance_per_hand=var_hand,
            std_dev_per_hand=std_dev,
            n_zero=n0,
            score=score,
            hourly_win_rate_100=hourly_win_100,
            risk_of_ruin=ror,
            optimal_kelly_unit=optimal_unit,
        )
