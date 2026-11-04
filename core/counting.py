from __future__ import annotations
from enum import Enum, auto
import math
from typing import Dict, Iterable, Tuple

class CountingSystem(Enum):
    """Sistemas de conteo de cartas estándar para Advantage Play."""
    HI_LO = auto()
    ZEN_COUNT = auto()
    OMEGA_II = auto()
    WONG_HALVES = auto()

class RoundingMode(Enum):
    """Modo de aproximación de True Count a enteros."""
    FLOOR = auto()     # math.floor: convención canónica de Don Schlesinger en BJA
    ROUND = auto()     # Redondeo simétrico estándar
    TRUNCATE = auto()  # Truncado hacia cero (int)


# Tablas de ponderación por carta (1..10, donde 1 es As y 10 es 10/J/Q/K)
COUNTING_WEIGHTS: Dict[CountingSystem, Tuple[float, ...]] = {
    #                              A,   2,   3,   4,   5,   6,   7,   8,    9,    10
    CountingSystem.HI_LO:       (-1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0,  0.0, -1.0),
    CountingSystem.ZEN_COUNT:   (-1.0, 1.0, 1.0, 2.0, 2.0, 2.0, 1.0, 0.0,  0.0, -2.0),
    CountingSystem.OMEGA_II:    ( 0.0, 1.0, 1.0, 2.0, 2.0, 2.0, 1.0, 0.0, -1.0, -2.0),
    CountingSystem.WONG_HALVES: (-1.0, 0.5, 1.0, 1.0, 1.5, 1.0, 0.5, 0.0, -0.5, -1.0),
}


class CardCounter:
    """
    Motor de conteo multinivel con soporte para valores continuos,
    conteo lateral de Ases y quantización configurable de zapato.
    """
    __slots__ = (
        "_system",
        "_rounding_mode",
        "_deck_resolution",
        "_weights",
        "_running_count",
        "_aces_seen",
        "_cards_seen",
    )

    def __init__(
        self,
        system: CountingSystem = CountingSystem.WONG_HALVES,
        rounding_mode: RoundingMode = RoundingMode.FLOOR,
        deck_resolution: float = 0.5,
    ) -> None:
        if deck_resolution <= 0.0:
            raise ValueError(f"deck_resolution debe ser > 0: {deck_resolution}")
        self._system: CountingSystem = system
        self._rounding_mode: RoundingMode = rounding_mode
        self._deck_resolution: float = deck_resolution
        self._weights: Tuple[float, ...] = COUNTING_WEIGHTS[system]
        self._running_count: float = 0.0
        self._aces_seen: int = 0
        self._cards_seen: int = 0

    @property
    def system(self) -> CountingSystem:
        return self._system

    @property
    def rounding_mode(self) -> RoundingMode:
        return self._rounding_mode

    @property
    def deck_resolution(self) -> float:
        return self._deck_resolution

    @property
    def running_count(self) -> float:
        return self._running_count

    @property
    def aces_seen(self) -> int:
        return self._aces_seen

    @property
    def cards_seen(self) -> int:
        return self._cards_seen

    def reset(self) -> None:
        """Reinicia el estado del contador."""
        self._running_count = 0.0
        self._aces_seen = 0
        self._cards_seen = 0

    def update(self, card: int) -> float:
        """Actualiza el estado con una sola carta (1..10) y devuelve el nuevo RC."""
        if not (1 <= card <= 10):
            raise ValueError(f"Valor de carta inválido: {card}. Debe ser 1..10")
        self._running_count += self._weights[card - 1]
        self._cards_seen += 1
        if card == 1:
            self._aces_seen += 1
        return self._running_count

    def update_multiple(self, cards: Iterable[int]) -> float:
        """Actualiza con una secuencia de cartas y devuelve el nuevo RC."""
        for c in cards:
            self.update(c)
        return self._running_count

    def estimate_decks_remaining(self, cards_remaining: int) -> float:
        """
        Calcula los mazos restantes redondeados a la resolución especificada.
        Garantiza un mínimo físico de una resolución de mazo para evitar divisiones críticas.
        """
        raw_decks = max(cards_remaining, 1) / 52.0
        quantized = round(raw_decks / self._deck_resolution) * self._deck_resolution
        return max(self._deck_resolution, quantized)

    def get_raw_true_count(self, cards_remaining: int) -> float:
        """Calcula el True Count como flotante continuo sin discretizar."""
        decks_rem = self.estimate_decks_remaining(cards_remaining)
        return self._running_count / decks_rem

    def get_true_count(self, cards_remaining: int) -> int:
        """Calcula el True Count discretizado según el RoundingMode seleccionado."""
        raw_tc = self.get_raw_true_count(cards_remaining)
        if self._rounding_mode == RoundingMode.FLOOR:
            return math.floor(raw_tc)
        elif self._rounding_mode == RoundingMode.TRUNCATE:
            return int(raw_tc)
        elif self._rounding_mode == RoundingMode.ROUND:
            return round(raw_tc)
        raise ValueError(f"Modo de redondeo desconocido: {self._rounding_mode}")

    def get_ace_surplus(self, cards_remaining: int, total_decks: int) -> float:
        """
        Calcula el excedente o déficit analítico de Ases en relación a la densidad esperada:
        Ace Surplus = Aces Restantes Reales - (Decks Restantes * 4.0)
        Un valor positivo indica superávit de Ases (favorable para el jugador).
        """
        aces_remaining = (total_decks * 4) - self._aces_seen
        decks_remaining = self.estimate_decks_remaining(cards_remaining)
        return float(aces_remaining) - (decks_remaining * 4.0)
