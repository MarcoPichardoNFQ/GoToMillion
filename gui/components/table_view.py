from __future__ import annotations
from typing import List, Optional, Tuple
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QColor, QFont, QPen, QBrush, QPainter, QLinearGradient, QRadialGradient, QPainterPath
)
from PyQt6.QtWidgets import (
    QWidget, QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsObject,
    QSizePolicy
)


class CardItem(QGraphicsObject):
    """Renderizado vectorial de cartas en tema dark terminal."""

    WIDTH: float = 72.0
    HEIGHT: float = 100.0
    RADIUS: float = 6.0

    def __init__(self, val: int, suit: str = "♠", face_up: bool = True, parent: Optional[QGraphicsItem] = None) -> None:
        super().__init__(parent)
        self.val: int = val
        self.suit: str = suit
        self.face_up: bool = face_up

    def boundingRect(self) -> QRectF:
        return QRectF(0.0, 0.0, self.WIDTH, self.HEIGHT)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.boundingRect()

        if not self.face_up:
            painter.setPen(QPen(QColor("#2B2F3A"), 1.5))
            painter.setBrush(QBrush(QColor("#1A1D24")))
            painter.drawRoundedRect(rect, self.RADIUS, self.RADIUS)

            inner = rect.adjusted(4.0, 4.0, -4.0, -4.0)
            painter.setPen(QPen(QColor("#2979FF"), 1.0, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(inner, 4.0, 4.0)

            painter.setPen(QPen(QColor("#2979FF")))
            painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "AP")
            return

        painter.setPen(QPen(QColor("#CFD8DC"), 1.2))
        painter.setBrush(QBrush(QColor("#FAFAFA")))
        painter.drawRoundedRect(rect, self.RADIUS, self.RADIUS)

        is_red = self.suit in ("♥", "♦")
        text_color = QColor("#D32F2F") if is_red else QColor("#1A1D24")
        painter.setPen(QPen(text_color))

        rank_str = "A" if self.val == 1 else ("10" if self.val == 10 else str(self.val))
        font_rank = QFont("Helvetica", 11, QFont.Weight.Bold)
        painter.setFont(font_rank)
        painter.drawText(QPointF(6.0, 16.0), rank_str)

        font_suit = QFont("Helvetica", 10)
        painter.setFont(font_suit)
        painter.drawText(QPointF(6.0, 28.0), self.suit)

        font_center = QFont("Helvetica", 22)
        painter.setFont(font_center)
        painter.drawText(rect.adjusted(0, 10, 0, 0), Qt.AlignmentFlag.AlignCenter, self.suit)


class DiscardTrayWidget(QWidget):
    """Visualizador milimétrico de la bandeja de descarte y tarjeta de corte."""

    def __init__(self, total_decks: int = 6, penetration: float = 0.75, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.total_decks = total_decks
        self.penetration = penetration
        self.cards_discarded = 0
        self.total_cards = total_decks * 52
        self.setFixedWidth(80)
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def set_discard_state(self, cards_discarded: int) -> None:
        self.cards_discarded = max(0, min(self.total_cards, cards_discarded))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())

        tray_rect = QRectF(10.0, 10.0, w - 20.0, h - 20.0)
        painter.setPen(QPen(QColor("#2B2F3A"), 2.0))
        painter.setBrush(QBrush(QColor("#14171F")))
        painter.drawRoundedRect(tray_rect, 4.0, 4.0)

        discard_pct = self.cards_discarded / self.total_cards
        fill_h = tray_rect.height() * discard_pct

        if fill_h > 0.0:
            fill_rect = QRectF(
                tray_rect.left() + 2.0,
                tray_rect.bottom() - fill_h,
                tray_rect.width() - 4.0,
                fill_h
            )
            grad = QLinearGradient(fill_rect.topLeft(), fill_rect.topRight())
            grad.setColorAt(0.0, QColor("#37474F"))
            grad.setColorAt(1.0, QColor("#263238"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawRect(fill_rect)

        cut_card_y = tray_rect.bottom() - (tray_rect.height() * self.penetration)
        painter.setPen(QPen(QColor("#FF5252"), 1.8, Qt.PenStyle.DashDotLine))
        painter.drawLine(QPointF(tray_rect.left() - 2.0, cut_card_y), QPointF(tray_rect.right() + 2.0, cut_card_y))

        painter.setPen(QColor("#90A4AE"))
        painter.setFont(QFont("Consolas", 8))
        rem_decks = (self.total_cards - self.cards_discarded) / 52.0
        painter.drawText(QRectF(0, h - 16, w, 16), Qt.AlignmentFlag.AlignCenter, f"{rem_decks:.1f}D Rem")


class BlackjackTableView(QGraphicsView):
    """Mesa interactiva de Blackjack sobre QGraphicsScene libre de fugas de memoria."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setBackgroundBrush(QBrush(QColor("#0F1117")))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSceneRect(0, 0, 800, 480)

        self._dealer_cards: List[CardItem] = []
        self._player_hands: List[List[CardItem]] = [[]]
        self._hand_markers: List[QGraphicsItem] = []
        self._active_hand_index: int = 0
        self._draw_table_felt()

    def _draw_table_felt(self) -> None:
        self.scene.clear()
        self._dealer_cards.clear()
        self._player_hands.clear()
        self._hand_markers.clear()

        path = QPainterPath()
        path.moveTo(40, 60)
        path.cubicTo(200, 20, 600, 20, 760, 60)
        path.lineTo(740, 440)
        path.cubicTo(560, 470, 240, 470, 60, 440)
        path.closeSubpath()

        grad = QRadialGradient(QPointF(400, 240), 400)
        grad.setColorAt(0.0, QColor("#141923"))
        grad.setColorAt(1.0, QColor("#0A0C10"))

        felt_item = self.scene.addPath(path, QPen(QColor("#2B2F3A"), 2.5), QBrush(grad))
        felt_item.setZValue(-10)

        text = self.scene.addText("BLACKJACK PAYS 3 TO 2\nDealer must draw to 16 and stand on all 17s")
        text.setDefaultTextColor(QColor("#455A64"))
        text.setFont(QFont("Trajan Pro", 9, QFont.Weight.Bold))
        text.setPos(260, 150)
        text.setZValue(-5)

    def set_dealer_cards(self, cards: List[Tuple[int, str, bool]]) -> None:
        for item in self._dealer_cards:
            self.scene.removeItem(item)
        self._dealer_cards.clear()

        start_x = 400.0 - (len(cards) * 40.0) / 2.0
        y = 65.0

        for i, (val, suit, face_up) in enumerate(cards):
            card_item = CardItem(val, suit, face_up)
            card_item.setPos(start_x + i * 45.0, y)
            card_item.setZValue(i + 1)
            self.scene.addItem(card_item)
            self._dealer_cards.append(card_item)

    def set_player_hands(self, hands: List[List[Tuple[int, str, bool]]], active_idx: int = 0) -> None:
        for marker in self._hand_markers:
            self.scene.removeItem(marker)
        self._hand_markers.clear()

        for hand in self._player_hands:
            for item in hand:
                self.scene.removeItem(item)
        self._player_hands.clear()
        self._active_hand_index = active_idx

        num_hands = len(hands)
        spacing = 680.0 / (num_hands + 1)

        for h_idx, hand_cards in enumerate(hands):
            hand_items: List[CardItem] = []
            center_x = (h_idx + 1) * spacing + 40.0
            base_y = 280.0

            if h_idx == active_idx and num_hands > 1:
                marker = self.scene.addEllipse(
                    center_x - 12.0, base_y + 115.0, 24.0, 6.0,
                    QPen(QColor("#00E676")), QBrush(QColor("#00E676"))
                )
                marker.setZValue(0)
                self._hand_markers.append(marker)

            for c_idx, (val, suit, face_up) in enumerate(hand_cards):
                card_item = CardItem(val, suit, face_up)
                card_item.setPos(center_x - 36.0 + c_idx * 22.0, base_y + c_idx * 16.0)
                card_item.setZValue(10 + c_idx)
                self.scene.addItem(card_item)
                hand_items.append(card_item)

            self._player_hands.append(hand_items)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.fitInView(0, 0, 800, 480, Qt.AspectRatioMode.KeepAspectRatio)
