from __future__ import annotations
from typing import List, Optional, Tuple
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QColor, QFont, QPen, QBrush, QPainter, QLinearGradient, QRadialGradient, QPainterPath
)
from PyQt6.QtWidgets import (
    QWidget, QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsObject,
    QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView
)


class HistoryOverlayWidget(QTableWidget):
    """Tabla histórica flotante (Overlay) semitransparente para auditoría de sesión."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(0, 10, parent)
        self.setHorizontalHeaderLabels([
            "#", "TC", "Apu/Rec", "Mano", "Crupier", "Acción", "⚠️", "Neto $", "EV Gen", "Balance"
        ])
        
        self.setStyleSheet("""
            QTableWidget {
                background-color: rgba(15, 17, 23, 210);
                color: #CFD8DC;
                gridline-color: rgba(43, 47, 58, 150);
                border: 1px solid rgba(43, 47, 58, 200);
                border-radius: 6px;
                font-family: Consolas;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: rgba(26, 29, 36, 220);
                color: #90A4AE;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid #2B2F3A;
            }
            QScrollBar:vertical {
                background: rgba(15, 17, 23, 150); width: 8px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(69, 90, 100, 200); border-radius: 4px;
            }
        """)
        
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        
        # Posición y tamaño fijo sobre el paño
        self.resize(520, 160)
        self.move(10, 10)

    def add_round_record(
        self, rnd: int, tc: int, bet_str: str, hand_str: str, dealer_str: str, 
        action: str, error: bool, net: float, ev_gen: float, balance: float
    ) -> None:
        self.insertRow(0)
        
        def _make_item(text: str, color: str = "#CFD8DC") -> QTableWidgetItem:
            it = QTableWidgetItem(str(text))
            it.setForeground(QColor(color))
            it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            return it
            
        tc_color = "#00E676" if tc > 0 else ("#FF5252" if tc < 0 else "#CFD8DC")
        net_color = "#00E676" if net > 0 else ("#FF5252" if net < 0 else "#CFD8DC")
        ev_color = "#00E676" if ev_gen > 0 else ("#FF5252" if ev_gen < 0 else "#CFD8DC")
        
        self.setItem(0, 0, _make_item(rnd))
        self.setItem(0, 1, _make_item(f"{tc:+d}", tc_color))
        self.setItem(0, 2, _make_item(bet_str, "#FFD600"))
        self.setItem(0, 3, _make_item(hand_str))
        self.setItem(0, 4, _make_item(dealer_str))
        self.setItem(0, 5, _make_item(action))
        self.setItem(0, 6, _make_item("⚠️" if error else "", "#FF5252"))
        self.setItem(0, 7, _make_item(f"{net:+.2f}", net_color))
        self.setItem(0, 8, _make_item(f"{ev_gen:+.2f}", ev_color))
        self.setItem(0, 9, _make_item(f"{balance:.2f}", "#FFFFFF"))


class CardItem(QGraphicsObject):
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
        w, h = float(self.width()), float(self.height())
        tray_rect = QRectF(10.0, 10.0, w - 20.0, h - 20.0)
        painter.setPen(QPen(QColor("#2B2F3A"), 2.0))
        painter.setBrush(QBrush(QColor("#14171F")))
        painter.drawRoundedRect(tray_rect, 4.0, 4.0)
        discard_pct = self.cards_discarded / self.total_cards
        fill_h = tray_rect.height() * discard_pct

        if fill_h > 0.0:
            fill_rect = QRectF(tray_rect.left() + 2.0, tray_rect.bottom() - fill_h, tray_rect.width() - 4.0, fill_h)
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
        painter.drawText(QRectF(0, h - 16, w, 16), Qt.AlignmentFlag.AlignCenter, f"{(self.total_cards - self.cards_discarded) / 52.0:.1f}D Rem")


class BlackjackTableView(QGraphicsView):
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
        self._dealer_total_item = None
        self._player_total_items: List[QGraphicsItem] = []
        self._active_hand_index: int = 0
        
        # Historial Flotante Superpuesto
        self.history_overlay = HistoryOverlayWidget(self)
        
        self._draw_table_felt()

    def _draw_table_felt(self) -> None:
        self.scene.clear()
        self._dealer_cards.clear()
        self._player_hands.clear()
        self._hand_markers.clear()
        self._dealer_total_item = None
        self._player_total_items.clear()

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
        text.setPos(260, 170)
        text.setZValue(-5)

    def set_dealer_cards(self, cards: List[Tuple[int, str, bool]], total_text: str = "") -> None:
        for item in self._dealer_cards:
            self.scene.removeItem(item)
        self._dealer_cards.clear()
        
        if self._dealer_total_item:
            self.scene.removeItem(self._dealer_total_item)
            self._dealer_total_item = None
        if not cards:
            return

        start_x = 420.0 - (len(cards) * 40.0) / 2.0  # Desplazado ligeramente a la derecha para no colisionar con el overlay
        y = 45.0

        for i, (val, suit, face_up) in enumerate(cards):
            card_item = CardItem(val, suit, face_up)
            card_item.setPos(start_x + i * 45.0, y)
            card_item.setZValue(i + 1)
            self.scene.addItem(card_item)
            self._dealer_cards.append(card_item)

        if total_text:
            text = self.scene.addText(total_text)
            text.setDefaultTextColor(QColor("#FFD600"))
            text.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
            text.setPos(start_x + ((len(cards) - 1) * 45.0 + 72.0) / 2.0 - text.boundingRect().width() / 2.0, y - 30.0)
            text.setZValue(100)
            self._dealer_total_item = text

    def set_player_hands(self, hands: List[List[Tuple[int, str, bool]]], active_idx: int = 0, totals: List[str] = None) -> None:
        for marker in self._hand_markers:
            self.scene.removeItem(marker)
        self._hand_markers.clear()

        for item in self._player_total_items:
            self.scene.removeItem(item)
        self._player_total_items.clear()

        for hand in self._player_hands:
            for item in hand:
                self.scene.removeItem(item)
        self._player_hands.clear()
        
        self._active_hand_index = active_idx
        if not hands:
            return

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

            if totals and h_idx < len(totals):
                t_text = self.scene.addText(totals[h_idx])
                t_text.setDefaultTextColor(QColor("#00E676") if h_idx == active_idx else QColor("#90A4AE"))
                t_text.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
                t_text.setPos(center_x - t_text.boundingRect().width() / 2.0, base_y - 30.0)
                t_text.setZValue(100)
                self._player_total_items.append(t_text)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.fitInView(0, 0, 800, 480, Qt.AspectRatioMode.KeepAspectRatio)