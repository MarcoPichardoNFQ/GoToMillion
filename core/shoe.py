from __future__ import annotations
from typing import Tuple, Iterable, Optional

# Constantes binarias para empaquetado inyectivo uint64:
# Denominaciones 1..9 ocupan 6 bits (máx 63 >= 32 cartas).
# Denominación 10 ocupa 8 bits (máx 255 >= 128 cartas).
SHIFTS: Tuple[int, ...] = tuple(6 * i if i < 9 else 54 for i in range(10))
MASKS: Tuple[int, ...] = tuple(0x3F if i < 9 else 0xFF for i in range(10))
DECREMENT_MASKS: Tuple[int, ...] = tuple((1 << (6 * i)) if i < 9 else (1 << 54) for i in range(10))
CARDS_DATA: Tuple[Tuple[int, int, int, int], ...] = tuple(
    (SHIFTS[i], MASKS[i], DECREMENT_MASKS[i], i + 1) for i in range(10)
)


def pack_shoe(counts: Tuple[int, ...]) -> int:
    """Empaqueta 10 denominaciones en un entero uint64."""
    packed = 0
    for i in range(9):
        packed |= (counts[i] & 0x3F) << (6 * i)
    packed |= (counts[9] & 0xFF) << 54
    return packed


def unpack_shoe(packed: int) -> Tuple[int, ...]:
    """Desempaqueta un uint64 a una tupla inmutable de 10 enteros."""
    counts = [0] * 10
    for i in range(9):
        counts[i] = (packed >> (6 * i)) & 0x3F
    counts[9] = (packed >> 54) & 0xFF
    return tuple(counts)


class CompositionShoe:
    """
    Representación finita y determinista de la composición del zapato sin reemplazo.
    Mantiene la memoria del volumen inicial de cartas para cálculos de penetración.
    """
    __slots__ = ("_counts", "_total_cards", "_packed", "_initial_total_cards")

    def __init__(self, counts: Tuple[int, ...], initial_total_cards: Optional[int] = None) -> None:
        if len(counts) != 10:
            raise ValueError(f"Se requieren 10 denominaciones, recibidas: {len(counts)}")
        self._counts: Tuple[int, ...] = counts
        self._total_cards: int = sum(counts)
        self._packed: int = pack_shoe(counts)
        self._initial_total_cards: int = self._total_cards if initial_total_cards is None else initial_total_cards

    @classmethod
    def from_decks(cls, decks: int) -> CompositionShoe:
        base = [4 * decks] * 9 + [16 * decks]
        return cls(tuple(base))

    @classmethod
    def from_counts(cls, counts: Iterable[int], initial_total_cards: Optional[int] = None) -> CompositionShoe:
        c_tuple = tuple(counts)
        return cls(c_tuple, initial_total_cards=initial_total_cards)

    @property
    def counts(self) -> Tuple[int, ...]:
        return self._counts

    @property
    def total_cards(self) -> int:
        return self._total_cards

    @property
    def initial_total_cards(self) -> int:
        return self._initial_total_cards

    @property
    def packed(self) -> int:
        return self._packed

    def prob(self, card: int) -> float:
        if self._total_cards == 0:
            return 0.0
        return self._counts[card - 1] / self._total_cards

    def is_cut_card_reached(self, penetration: float) -> bool:
        """Determina si el zapato residual cruzó la tarjeta de corte."""
        return self._total_cards <= self._initial_total_cards * (1.0 - penetration)

    def remove(self, card: int) -> CompositionShoe:
        idx = card - 1
        if self._counts[idx] <= 0:
            raise ValueError(f"Sin cartas disponibles para la denominación {card}")
        new_counts = list(self._counts)
        new_counts[idx] -= 1
        return CompositionShoe(tuple(new_counts), initial_total_cards=self._initial_total_cards)

    def remove_cards(self, cards: Iterable[int]) -> CompositionShoe:
        new_counts = list(self._counts)
        for c in cards:
            idx = c - 1
            if new_counts[idx] <= 0:
                raise ValueError(f"Sin cartas disponibles para extraer la carta {c}")
            new_counts[idx] -= 1
        return CompositionShoe(tuple(new_counts), initial_total_cards=self._initial_total_cards)

    def __hash__(self) -> int:
        return self._packed

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CompositionShoe):
            return False
        return self._packed == other._packed

    def __repr__(self) -> str:
        return (
            f"CompositionShoe(total={self._total_cards}/{self._initial_total_cards}, "
            f"counts={self._counts})"
        )
