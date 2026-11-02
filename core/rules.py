from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class TableRules:
    """
    Reglas de mesa inmutables con soporte integral para Advantage Play (AP),
    variantes internacionales (American Peek vs ENHC) y reglas de pago especial (OBO).
    """
    decks: int = 6
    penetration: float = 0.75
    dealer_hits_soft_17: bool = False  # False = S17, True = H17
    is_hole_card_game: bool = True     # True = American Peek, False = ENHC
    allow_obo: bool = False            # True = Original Bets Only en ENHC (ej. Australia/UK)
    blackjack_payout: float = 1.5      # 1.5 = 3:2, 1.2 = 6:5, 1.0 = 1:1
    allow_das: bool = True             # Double After Split
    allow_rsa: bool = True             # Resplit Aces
    hit_split_aces: bool = False       # Hit permitido tras dividir Ases
    allow_late_surrender: bool = True  # Late Surrender frente a no-BJ
    max_split_hands: int = 4           # Límite de manos divididas concurrentes

    def __post_init__(self) -> None:
        if not (1 <= self.decks <= 8):
            raise ValueError(f"Decks fuera de rango [1, 8]: {self.decks}")
        if not (0.10 <= self.penetration <= 0.95):
            raise ValueError(f"Penetración fuera de rango [0.10, 0.95]: {self.penetration}")
        if self.blackjack_payout not in (1.5, 1.2, 1.0):
            raise ValueError(f"Blackjack payout inválido: {self.blackjack_payout}. Use 1.5, 1.2 o 1.0")
        if self.max_split_hands < 1:
            raise ValueError(f"max_split_hands debe ser >= 1: {self.max_split_hands}")
        if self.is_hole_card_game and self.allow_obo:
            raise ValueError("allow_obo solo aplica en juegos sin carta oculta previa (ENHC: is_hole_card_game=False)")
