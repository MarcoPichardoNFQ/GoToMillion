from __future__ import annotations
import sys
from collections import deque
from typing import Optional
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import (
	QColor,
	QFont,
	QPainter,
	QPen,
	QBrush,
)
from PyQt6.QtWidgets import (
	QApplication,
	QWidget,
	QVBoxLayout,
	QHBoxLayout,
	QGridLayout,
	QLabel,
	QPushButton,
	QFrame,
	QSpinBox,
	QProgressBar,
	QScrollArea,
	QMessageBox,
	QTableWidget,
	QTableWidgetItem,
	QHeaderView,
	QSizePolicy,
)
# ============================================================
# CONFIGURACIÓN
# ============================================================
APP_NAME = "BLACKJACK SHOE ANALYTICS"
DEFAULT_DECKS = 6
MAX_DECKS = 12
MAX_HISTORY = 5000
RANKS = [
	"A", "2", "3", "4", "5", "6", "7",
	"8", "9", "10", "J", "Q", "K"
]
LOW_CARDS = {"2", "3", "4", "5", "6"}
MEDIUM_CARDS = {"7", "8", "9"}
HIGH_CARDS = {"10", "J", "Q", "K", "A"}
TEN_VALUE_CARDS = {"10", "J", "Q", "K"}
HI_LO_VALUES = {
	"A": -1,
	"2": 1,
	"3": 1,
	"4": 1,
	"5": 1,
	"6": 1,
	"7": 0,
	"8": 0,
	"9": 0,
	"10": -1,
	"J": -1,
	"Q": -1,
	"K": -1,
}
COLORS = {
	"background": "#10151D",
	"panel": "#19212D",
	"panel_light": "#222D3B",
	"border": "#303D4D",
	"text": "#E6EDF5",
	"muted": "#8996A7",
	"green": "#27AE75",
	"blue": "#438FE0",
	"red": "#E05B62",
	"yellow": "#E4B34E",
	"gray": "#8994A5",
	"purple": "#A77CE5",
}
# ============================================================
# FUNCIONES MATEMÁTICAS
# ============================================================
def safe_percentage(numerator, denominator):
	if denominator <= 0:
		return 0.0
	return numerator / denominator * 100.0
def probability_next(remaining, ranks):
	total = sum(remaining.values())
	quantity = sum(
		remaining[rank]
		for rank in ranks
	)
	return safe_percentage(quantity, total)
def calculate_blackjack_probability(remaining):
	"""
	Probabilidad de obtener un As y una carta de valor 10
	en las próximas dos extracciones, sin reemplazo.
	Considera ambos órdenes posibles.
	"""
	total = sum(remaining.values())
	if total < 2:
		return 0.0
	aces = remaining["A"]
	ten_cards = sum(
		remaining[rank]
		for rank in TEN_VALUE_CARDS
	)
	probability = (
		2 * aces * ten_cards
		/ (total * (total - 1))
	)
	return probability * 100
def calculate_expected_hilo(remaining):
	total = sum(remaining.values())
	if total == 0:
		return 0.0
	weighted_sum = sum(
		remaining[rank] * HI_LO_VALUES[rank]
		for rank in RANKS
	)
	return weighted_sum / total
def format_signed(value, decimals=2):
	return f"{value:+.{decimals}f}"
# ============================================================
# UTILIDADES VISUALES
# ============================================================
def make_label(
	text,
	size=11,
	color="text",
	bold=False,
):
	label = QLabel(text)
	label.setFont(
		QFont(
			"Segoe UI",
			size,
			QFont.Weight.Bold if bold else QFont.Weight.Normal,
		)
	)
	label.setStyleSheet(
		f"color: {COLORS.get(color, color)}; background: transparent;"
	)
	return label
def make_panel():
	panel = QFrame()
	panel.setStyleSheet(
		f"""
		QFrame {{
			background-color: {COLORS['panel']};
			border: 1px solid {COLORS['border']};
			border-radius: 10px;
		}}
		"""
	)
	return panel
def make_progress(color):
	bar = QProgressBar()
	bar.setRange(0, 100)
	bar.setValue(0)
	bar.setTextVisible(False)
	bar.setFixedHeight(10)
	bar.setStyleSheet(
		f"""
		QProgressBar {{
			background-color: {COLORS['panel_light']};
			border: none;
			border-radius: 5px;
		}}
		QProgressBar::chunk {{
			background-color: {color};
			border-radius: 5px;
		}}
		"""
	)
	return bar
# ============================================================
# KPI CARD
# ============================================================
class KPICard(QFrame):
	def __init__(
		self,
		title,
		value="0",
		subtitle="",
		color="text",
	):
		super().__init__()
		self.setMinimumHeight(105)
		self.setStyleSheet(
			f"""
			QFrame {{
				background-color: {COLORS['panel']};
				border: 1px solid {COLORS['border']};
				border-radius: 9px;
			}}
			"""
		)
		layout = QVBoxLayout(self)
		layout.setContentsMargins(12, 10, 12, 10)
		layout.setSpacing(4)
		self.title_label = make_label(
			title, 9, "muted", True
		)
		self.value_label = make_label(
			value, 22, color, True
		)
		self.subtitle_label = make_label(
			subtitle, 9, "muted"
		)
		self.subtitle_label.setWordWrap(True)
		layout.addWidget(self.title_label)
		layout.addWidget(self.value_label)
		layout.addWidget(self.subtitle_label)
		layout.addStretch()
	def update_value(self, value, subtitle=None):
		self.value_label.setText(value)
		if subtitle is not None:
			self.subtitle_label.setText(subtitle)
# ============================================================
# GRÁFICA HISTÓRICA
# ============================================================
class HistoryChart(QWidget):
	def __init__(self):
		super().__init__()
		self.setMinimumHeight(230)
		self.setSizePolicy(
			QSizePolicy.Policy.Expanding,
			QSizePolicy.Policy.Preferred,
		)
		self.history = []
	def set_history(self, history):
		self.history = list(history)
		self.update()
	def paintEvent(self, event):
		painter = QPainter(self)
		painter.setRenderHint(
			QPainter.RenderHint.Antialiasing
		)
		painter.fillRect(
			self.rect(),
			QColor(COLORS["panel"])
		)
		width = self.width()
		height = self.height()
		left = 48
		right = width - 15
		top = 18
		bottom = height - 35
		graph_width = right - left
		graph_height = bottom - top
		if graph_width <= 0 or graph_height <= 0:
			return
		if len(self.history) < 2:
			painter.setPen(
				QColor(COLORS["muted"])
			)
			painter.drawText(
				self.rect(),
				Qt.AlignmentFlag.AlignCenter,
				"Registra cartas para visualizar la evolución."
			)
			return
		data = self.history
		if len(data) > 500:
			step = max(1, len(data) // 500)
			data = data[::step]
			if data[-1] != self.history[-1]:
				data.append(self.history[-1])
		running_values = [
			item[0] for item in data
		]
		true_values = [
			item[1] for item in data
		]
		all_values = running_values + true_values
		min_value = min(all_values)
		max_value = max(all_values)
		padding = max(
			1.0,
			(max_value - min_value) * 0.15
		)
		min_value -= padding
		max_value += padding
		value_range = max_value - min_value
		if value_range == 0:
			value_range = 1
		def point(index, value):
			x = left + (
				index / max(1, len(data) - 1)
			) * graph_width
			y = bottom - (
				(value - min_value) / value_range
			) * graph_height
			return QPointF(x, y)
		# Cuadrícula
		painter.setPen(
			QPen(
				QColor(COLORS["border"]),
				1,
				Qt.PenStyle.DashLine
			)
		)
		for i in range(5):
			y = top + i * graph_height / 4
			painter.drawLine(
				int(left),
				int(y),
				int(right),
				int(y)
			)
		# Línea cero
		if min_value <= 0 <= max_value:
			zero_y = bottom - (
				(0 - min_value) / value_range
			) * graph_height
			painter.setPen(
				QPen(
					QColor("#082751"),
					1,
					Qt.PenStyle.DashLine
				)
			)
			painter.drawLine(
				int(left),
				int(zero_y),
				int(right),
				int(zero_y)
			)
		def draw_series(values, color):
			painter.setPen(
				QPen(
					QColor(color),
					2,
					Qt.PenStyle.SolidLine
				)
			)
			for i in range(1, len(values)):
				p1 = point(i - 1, values[i - 1])
				p2 = point(i, values[i])
				painter.drawLine(p1, p2)
			painter.setBrush(
				QBrush(QColor(color))
			)
			painter.setPen(
				Qt.PenStyle.NoPen
			)
			painter.drawEllipse(
				point(len(values) - 1, values[-1]),
				4,
				4
			)
		draw_series(
			running_values,
			COLORS["green"]
		)
		draw_series(
			true_values,
			COLORS["blue"]
		)
		# Etiquetas
		painter.setPen(
			QColor(COLORS["muted"])
		)
		painter.setFont(
			QFont("Segoe UI", 8)
		)
		for i in range(5):
			value = max_value - (
				i * value_range / 4
			)
			y = top + i * graph_height / 4
			painter.drawText(
				2,
				int(y + 4),
				f"{value:.1f}"
			)
		painter.drawText(
			left,
			height - 9,
			"Inicio"
		)
		painter.drawText(
			right - 50,
			height - 9,
			"Actual"
		)
# ============================================================
# CARTA INDIVIDUAL
# ============================================================

# ============================================================
# 1. REEMPLAZAR COMPLETAMENTE LA CLASE CardTile
# ============================================================

class CardTile(QFrame):
	def __init__(self, rank, color, remove_callback, parent=None):
		super().__init__(parent)

		self.rank = rank
		self.accent_color = color
		self.remove_callback = remove_callback
		self.available = True

		self.setObjectName("cardTile")
		self.setFrameShape(QFrame.Shape.StyledPanel)
		self.setCursor(Qt.CursorShape.PointingHandCursor)
		self.setMinimumSize(90, 115)
		self.setMaximumHeight(145)

		layout = QVBoxLayout(self)
		layout.setContentsMargins(5, 8, 5, 8)
		layout.setSpacing(4)

		self.rank_label = QLabel(rank)
		self.rank_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self.rank_label.setStyleSheet("""
			color: #f8fafc;
			font-size: 25px;
			font-weight: bold;
			background: transparent;
			border: none;
		""")

		self.count_label = QLabel("")
		self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self.count_label.setStyleSheet("""
			color: #94a3b8;
			font-size: 11px;
			background: transparent;
			border: none;
		""")

		self.probability_label = QLabel("")
		self.probability_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self.probability_label.setStyleSheet("""
			color: #60a5fa;
			font-size: 12px;
			font-weight: bold;
			background: transparent;
			border: none;
		""")

		# Los QLabel no deben interceptar los clics.
		# Así, cualquier clic dentro del recuadro llega a CardTile.
		for label in (
			self.rank_label,
			self.count_label,
			self.probability_label
		):
			label.setAttribute(
				Qt.WidgetAttribute.WA_TransparentForMouseEvents,
				True
			)

		layout.addWidget(self.rank_label)
		layout.addWidget(self.count_label)
		layout.addWidget(self.probability_label)

		self._apply_style()

	def _apply_style(self):
		if self.available:
			self.setStyleSheet(f"""
				QFrame#cardTile {{
					background-color: #202938;
					border: 1px solid #3b4758;
					border-radius: 9px;
				}}

				QFrame#cardTile:hover {{
					background-color: #2d3b4f;
					border: 2px solid {self.accent_color};
				}}
			""")
		else:
			self.setStyleSheet("""
				QFrame#cardTile {
					background-color: #151b25;
					border: 1px solid #293241;
					border-radius: 9px;
				}
			""")

			self.rank_label.setStyleSheet("""
				color: #475569;
				font-size: 25px;
				font-weight: bold;
				background: transparent;
				border: none;
			""")

			self.count_label.setStyleSheet("""
				color: #475569;
				font-size: 11px;
				background: transparent;
				border: none;
			""")

			self.probability_label.setStyleSheet("""
				color: #475569;
				font-size: 12px;
				font-weight: bold;
				background: transparent;
				border: none;
			""")

	def mousePressEvent(self, event):
		if event.button() == Qt.MouseButton.LeftButton:
			if self.available:
				self.remove_callback(self.rank)
				event.accept()
				return

		super().mousePressEvent(event)

	def update_card(self, remaining, total, probability):
		self.available = remaining > 0

		self.count_label.setText(
			f"{remaining} / {total}"
		)

		self.probability_label.setText(
			f"{probability:.2f}%"
		)

		self.setCursor(
			Qt.CursorShape.PointingHandCursor
			if self.available
			else Qt.CursorShape.ForbiddenCursor
		)

		self._apply_style()
# ============================================================
# APLICACIÓN PRINCIPAL
# ============================================================
class BlackjackShoeAnalytics(QWidget):
	def __init__(self):
		super().__init__()
		self.setWindowTitle(APP_NAME)
		self.resize(1500, 1100)
		self.setMinimumSize(1100, 750)
		self.decks = DEFAULT_DECKS
		# Todos los contenedores de estado se crean
		# ANTES de inicializar el zapato y la interfaz.
		self.initial_counts = {}
		self.remaining_counts = {}
		self.dealt_counts = {}
		self.running_count = 0
		self.moves = []
		self.history = deque(maxlen=MAX_HISTORY)
		self.card_tiles = {}
		self.kpis = {}
		self.group_bars = {}
		# Primero se inicializa el modelo.
		self._initialize_shoe()
		# Después se construyen todos los componentes.
		self._build_interface()
		# Finalmente se actualiza el dashboard.
		self._refresh_dashboard()
	# ========================================================
	# MODELO DE DATOS
	# ========================================================
	def _initialize_shoe(self):
		self.initial_counts = {
			rank: self.decks * 4
			for rank in RANKS
		}
		self.remaining_counts = (
			self.initial_counts.copy()
		)
		self.dealt_counts = {
			rank: 0
			for rank in RANKS
		}
		self.running_count = 0
		self.moves.clear()
		self.history.clear()
		self._record_history()
	@property
	def total_cards(self):
		return sum(
			self.initial_counts.values()
		)
	@property
	def remaining_cards(self):
		return sum(
			self.remaining_counts.values()
		)
	@property
	def dealt_cards(self):
		return sum(
			self.dealt_counts.values()
		)
	@property
	def penetration(self):
		return safe_percentage(
			self.dealt_cards,
			self.total_cards
		)
	@property
	def remaining_decks(self):
		return self.remaining_cards / 52
	@property
	def true_count(self):
		if self.remaining_decks <= 0:
			return 0.0
		return self.running_count / self.remaining_decks
	def _record_history(self):
		self.history.append(
			(
				self.running_count,
				self.true_count
			)
		)
	# ========================================================
	# REGISTRO DE CARTAS
	# ========================================================
	def remove_card(self, rank):
		if rank not in self.remaining_counts:
			return
		if self.remaining_counts[rank] <= 0:
			return
		self.remaining_counts[rank] -= 1
		self.dealt_counts[rank] += 1
		self.running_count += HI_LO_VALUES[rank]
		self.moves.append(rank)
		self._record_history()
		self.validate_state()
		self._refresh_dashboard()
	def undo_last_card(self):
		if not self.moves:
			return
		rank = self.moves.pop()
		self.remaining_counts[rank] += 1
		self.dealt_counts[rank] -= 1
		self.running_count -= HI_LO_VALUES[rank]
		self._record_history()
		self.validate_state()
		self._refresh_dashboard()
	def reset_shoe(self):
		response = QMessageBox.question(
			self,
			"Reiniciar zapato",
			"¿Deseas reiniciar completamente el zapato?",
			QMessageBox.StandardButton.Yes
			| QMessageBox.StandardButton.No
		)
		if response != QMessageBox.StandardButton.Yes:
			return
		self._initialize_shoe()
		self._refresh_dashboard()
	def change_decks(self, value):
		if value == self.decks:
			return
		if self.dealt_cards > 0:
			response = QMessageBox.question(
				self,
				"Cambiar cantidad de mazos",
				"Cambiar la cantidad de mazos reiniciará "
				"el zapato y eliminará el historial.\n\n"
				"¿Deseas continuar?",
				QMessageBox.StandardButton.Yes
				| QMessageBox.StandardButton.No
			)
			if response != QMessageBox.StandardButton.Yes:
				self.deck_selector.blockSignals(True)
				self.deck_selector.setValue(
					self.decks
				)
				self.deck_selector.blockSignals(False)
				return
		self.decks = value
		self._initialize_shoe()
		self._refresh_dashboard()
	# ========================================================
	# CÁLCULO DE INDICADORES
	# ========================================================
	def _calculate_indicators(self):
		remaining = self.remaining_counts
		return {
			"low": probability_next(
				remaining,
				LOW_CARDS
			),
			"medium": probability_next(
				remaining,
				MEDIUM_CARDS
			),
			"high": probability_next(
				remaining,
				HIGH_CARDS
			),
			"ten": probability_next(
				remaining,
				TEN_VALUE_CARDS
			),
			"ace": probability_next(
				remaining,
				{"A"}
			),
			"blackjack": calculate_blackjack_probability(
				remaining
			),
			"expected_hilo": calculate_expected_hilo(
				remaining
			),
		}
	# ========================================================
	# CONSTRUCCIÓN DE INTERFAZ
	# ========================================================
	def _build_interface(self):
		root = QVBoxLayout(self)
		root.setContentsMargins(18, 15, 18, 15)
		root.setSpacing(12)
		root.addWidget(
			self._build_header()
		)
		scroll = QScrollArea()
		scroll.setWidgetResizable(True)
		scroll.setFrameShape(
			QFrame.Shape.NoFrame
		)
		content = QWidget()
		content_layout = QVBoxLayout(content)
		content_layout.setContentsMargins(0, 0, 0, 0)
		content_layout.setSpacing(14)
		content_layout.addWidget(
			self._build_primary_kpis()
		)
		content_layout.addWidget(
			self._build_probability_kpis()
		)
		content_layout.addWidget(
			self._build_history_panel()
		)
		content_layout.addWidget(
			self._build_cards_panel()
		)
		content_layout.addWidget(
			self._build_composition_panel()
		)
		content_layout.addWidget(
			self._build_chart_panel()
		)

		content_layout.addStretch()
		scroll.setWidget(content)
		root.addWidget(scroll)
		self.setStyleSheet(
			f"""
			QWidget {{
				background-color: {COLORS['background']};
				color: {COLORS['text']};
				font-family: 'Segoe UI';
			}}
			QSpinBox {{
				background-color: {COLORS['panel_light']};
				border: 1px solid {COLORS['border']};
				border-radius: 5px;
				padding: 5px;
				color: {COLORS['text']};
				min-width: 55px;
			}}
			QScrollBar:vertical {{
				background: {COLORS['background']};
				width: 9px;
			}}
			QScrollBar::handle:vertical {{
				background: {COLORS['border']};
				border-radius: 4px;
			}}
			"""
		)
	# ========================================================
	# HEADER
	# ========================================================
	def _build_header(self):
		panel = make_panel()
		layout = QHBoxLayout(panel)
		layout.setContentsMargins(16, 12, 16, 12)
		left = QVBoxLayout()
		left.addWidget(
			make_label(
				"BLACKJACK",
				23,
				"text",
				True
			)
		)
		left.addWidget(
			make_label(
				"SHOE COMPOSITION ANALYTICS",
				9,
				"muted",
				True
			)
		)
		layout.addLayout(left)
		layout.addStretch()
		layout.addWidget(
			make_label(
				"MAZOS",
				10,
				"muted",
				True
			)
		)
		self.deck_selector = QSpinBox()
		self.deck_selector.setRange(
			1,
			MAX_DECKS
		)
		self.deck_selector.setValue(
			self.decks
		)
		self.deck_selector.valueChanged.connect(
			self.change_decks
		)
		layout.addWidget(
			self.deck_selector
		)
		undo = QPushButton("↶ DESHACER")
		undo.clicked.connect(
			self.undo_last_card
		)
		undo.setStyleSheet(
			f"""
			QPushButton {{
				background-color: {COLORS['panel_light']};
				border: 1px solid {COLORS['border']};
				padding: 9px 13px;
				border-radius: 6px;
				font-weight: bold;
			}}
			QPushButton:hover {{
				background-color: {COLORS['blue']};
			}}
			"""
		)
		layout.addWidget(undo)
		reset = QPushButton("REINICIAR")
		reset.clicked.connect(
			self.reset_shoe
		)
		reset.setStyleSheet(
			"""
			QPushButton {
				background-color: #512D34;
				border: 1px solid #78414A;
				padding: 9px 13px;
				border-radius: 6px;
				font-weight: bold;
			}
			QPushButton:hover {
				background-color: #E05B62;
			}
			"""
		)
		layout.addWidget(reset)
		return panel
	# ========================================================
	# KPI PRINCIPALES
	# ========================================================
	def _build_primary_kpis(self):
		container = QWidget()
		layout = QGridLayout(container)
		layout.setContentsMargins(0, 0, 0, 0)
		layout.setSpacing(9)
		definitions = [
			("CARTAS RESTANTES", "remaining", "Inventario disponible", "green"),
			("CARTAS RETIRADAS", "dealt", "Cartas registradas", "blue"),
			("PENETRACIÓN", "penetration", "Zapato utilizado", "yellow"),
			("MAZOS RESTANTES", "decks", "Equivalente de mazos", "text"),
			("RUNNING COUNT", "running", "Conteo Hi-Lo", "green"),
			("TRUE COUNT", "true", "Conteo ajustado", "blue"),
		]
		for index, definition in enumerate(definitions):
			title, key, subtitle, color = definition
			card = KPICard(
				title,
				"0",
				subtitle,
				color
			)
			self.kpis[key] = card
			layout.addWidget(
				card,
				index // 3,
				index % 3
			)
		return container
	# ========================================================
	# KPI DE PROBABILIDADES
	# ========================================================
	def _build_probability_kpis(self):
		panel = make_panel()
		outer = QVBoxLayout(panel)
		outer.setContentsMargins(14, 12, 14, 12)
		outer.setSpacing(10)
		outer.addWidget(
			make_label(
				"PROBABILIDADES DE EXTRACCIÓN",
				13,
				"text",
				True
			)
		)
		outer.addWidget(
			make_label(
				"Probabilidades condicionadas a la composición actual del zapato.",
				9,
				"muted"
			)
		)
		grid = QGridLayout()
		grid.setSpacing(9)
		definitions = [
			("PROB. CARTA BAJA", "p_low", "2 al 6", "green"),
			("PROB. CARTA MEDIA", "p_medium", "7 al 9", "gray"),
			("PROB. CARTA ALTA", "p_high", "10 al As", "blue"),
			("PROB. CARTA 10", "p_ten", "10, J, Q o K", "blue"),
			("PROB. AS", "p_ace", "Ases restantes", "yellow"),
			("BLACKJACK EN DOS CARTAS", "p_blackjack", "As + carta de valor 10", "purple"),
			("VALOR ESPERADO HI-LO", "expected_hilo", "Valor medio de la próxima carta", "green"),
		]
		for index, definition in enumerate(definitions):
			title, key, subtitle, color = definition
			card = KPICard(
				title,
				"0.00",
				subtitle,
				color
			)
			self.kpis[key] = card
			grid.addWidget(
				card,
				index // 4,
				index % 4
			)
		outer.addLayout(grid)
		self.probability_note = make_label(
			"Las probabilidades se recalculan después de cada extracción.",
			9,
			"muted"
		)
		outer.addWidget(
			self.probability_note
		)
		return panel
	# ========================================================
	# CARTAS DEL ZAPATO
	# ========================================================
	def _build_cards_panel(self):
		panel = make_panel()
		layout = QVBoxLayout(panel)
		layout.setContentsMargins(15, 15, 15, 15)
		layout.setSpacing(9)
		layout.addWidget(
			make_label(
				"COMPOSICIÓN DEL ZAPATO",
				14,
				"text",
				True
			)
		)
		layout.addWidget(
			make_label(
				"Selecciona una denominación para registrar su salida.",
				10,
				"muted"
			)
		)
		grid = QGridLayout()
		grid.setSpacing(9)
		for index, rank in enumerate(RANKS):
			if rank in LOW_CARDS:
				color = COLORS["green"]
			elif rank in MEDIUM_CARDS:
				color = COLORS["gray"]
			else:
				color = COLORS["blue"]
			tile = CardTile(
				rank,
				color,
				self.remove_card
			)
			self.card_tiles[rank] = tile
			grid.addWidget(
				tile,
				index // 7,
				index % 7
			)
		layout.addLayout(grid)
		legend = QHBoxLayout()
		legend.addWidget(
			make_label(
				"● BAJAS (2-6)",
				9,
				"green",
				True
			)
		)
		legend.addWidget(
			make_label(
				"● MEDIAS (7-9)",
				9,
				"gray",
				True
			)
		)
		legend.addWidget(
			make_label(
				"● ALTAS (10-A)",
				9,
				"blue",
				True
			)
		)
		legend.addStretch()
		layout.addLayout(legend)
		return panel
	# ========================================================
	# COMPOSICIÓN, PROBABILIDADES Y HEATMAP
	# ========================================================
	def _build_composition_panel(self):
		panel = make_panel()
		layout = QVBoxLayout(panel)
		layout.setContentsMargins(15, 15, 15, 15)
		layout.setSpacing(10)
		layout.addWidget(
			make_label(
				"ANÁLISIS DETALLADO POR DENOMINACIÓN",
				14,
				"text",
				True
			)
		)
		layout.addWidget(
			make_label(
				"La probabilidad indica la posibilidad de que la próxima "
				"carta extraída tenga esa denominación.",
				9,
				"muted"
			)
		)
		self.table = QTableWidget(
			len(RANKS),
			6
		)
		self.table.setHorizontalHeaderLabels(
			[
				"DENOMINACIÓN",
				"INICIALES",
				"RETIRADAS",
				"RESTANTES",
				"PROBABILIDAD",
				"DISPONIBILIDAD",
			]
		)
		self.table.verticalHeader().setVisible(False)
		self.table.setEditTriggers(
			QTableWidget.EditTrigger.NoEditTriggers
		)
		self.table.setSelectionMode(
			QTableWidget.SelectionMode.NoSelection
		)
		self.table.horizontalHeader().setSectionResizeMode(
			QHeaderView.ResizeMode.Stretch
		)
		self.table.setMinimumHeight(390)
		self.table.setStyleSheet(
			f"""
			QTableWidget {{
				background-color: {COLORS['panel']};
				color: {COLORS['text']};
				gridline-color: {COLORS['border']};
				border: none;
			}}
			QHeaderView::section {{
				background-color: {COLORS['panel_light']};
				color: {COLORS['muted']};
				padding: 9px;
				border: none;
				font-weight: bold;
			}}
			QTableWidget::item {{
				padding: 5px;
			}}
			"""
		)
		layout.addWidget(self.table)
		self.table_note = make_label(
			"",
			9,
			"muted"
		)
		self.table_note.setWordWrap(True)
		layout.addWidget(self.table_note)
		# Distribución por grupos.
		# Se integra aquí para que todos los componentes
		# de composición se construyan en el mismo lugar.
		layout.addSpacing(12)
		layout.addWidget(
			make_label(
				"DISTRIBUCIÓN DE CARTAS RESTANTES",
				13,
				"text",
				True
			)
		)
		definitions = [
			("Cartas bajas", "low", LOW_CARDS, "green"),
			("Cartas medias", "medium", MEDIUM_CARDS, "gray"),
			("Cartas altas", "high", HIGH_CARDS, "blue"),
		]
		for title, key, group, color in definitions:
			row = QHBoxLayout()
			left = QVBoxLayout()
			left.addWidget(
				make_label(
					title,
					11,
					color,
					True
				)
			)
			count_label = make_label(
				"0 cartas",
				9,
				"muted"
			)
			left.addWidget(count_label)
			progress = make_progress(
				COLORS[color]
			)
			percentage_label = make_label(
				"0.00%",
				11,
				color,
				True
			)
			row.addLayout(left, 2)
			row.addWidget(progress, 5)
			row.addWidget(percentage_label, 1)
			layout.addLayout(row)
			self.group_bars[key] = {
				"group": group,
				"progress": progress,
				"count": count_label,
				"percentage": percentage_label,
			}
		layout.addSpacing(8)
		layout.addWidget(
			make_label(
				"PENETRACIÓN DEL ZAPATO",
				10,
				"muted",
				True
			)
		)
		self.penetration_bar = make_progress(
			COLORS["yellow"]
		)
		layout.addWidget(
			self.penetration_bar
		)
		self.penetration_label = make_label(
			"0%",
			10,
			"yellow",
			True
		)
		layout.addWidget(
			self.penetration_label
		)
		return panel
	# ========================================================
	# GRÁFICA HISTÓRICA
	# ========================================================
	def _build_chart_panel(self):
		panel = make_panel()
		layout = QVBoxLayout(panel)
		layout.setContentsMargins(15, 15, 15, 15)
		layout.setSpacing(10)
		layout.addWidget(
			make_label(
				"EVOLUCIÓN DEL CONTEO",
				14,
				"text",
				True
			)
		)
		legend = QHBoxLayout()
		legend.addWidget(
			make_label(
				"● RUNNING COUNT",
				9,
				"green",
				True
			)
		)
		legend.addWidget(
			make_label(
				"● TRUE COUNT",
				9,
				"blue",
				True
			)
		)
		legend.addStretch()
		layout.addLayout(legend)
		self.history_chart = HistoryChart()
		layout.addWidget(
			self.history_chart
		)
		layout.addWidget(
			make_label(
				"Cada punto representa un movimiento registrado. "
				"Deshacer también genera un nuevo punto.",
				9,
				"muted"
			)
		)
		return panel
	# ========================================================
	# HISTORIAL DE MOVIMIENTOS
	# ========================================================
	def _build_history_panel(self):
		panel = make_panel()
		layout = QVBoxLayout(panel)
		layout.setContentsMargins(15, 15, 15, 15)
		layout.addWidget(
			make_label(
				"ÚLTIMAS CARTAS REGISTRADAS",
				13,
				"text",
				True
			)
		)
		self.history_label = make_label(
			"Sin movimientos",
			11,
			"muted"
		)
		self.history_label.setWordWrap(True)
		layout.addWidget(
			self.history_label
		)
		return panel
	# ========================================================
	# ACTUALIZAR KPIs
	# ========================================================
	def _refresh_kpis(self):
		total = self.total_cards
		remaining = self.remaining_cards
		dealt = self.dealt_cards
		self.kpis["remaining"].update_value(
			f"{remaining:,}",
			f"de {total:,} cartas iniciales"
		)
		self.kpis["dealt"].update_value(
			f"{dealt:,}",
			"Cartas retiradas"
		)
		self.kpis["penetration"].update_value(
			f"{self.penetration:.2f}%",
			"Penetración del zapato"
		)
		self.kpis["decks"].update_value(
			f"{self.remaining_decks:.2f}",
			"Mazos equivalentes"
		)
		self.kpis["running"].update_value(
			f"{self.running_count:+d}",
			"Running Count Hi-Lo"
		)
		self.kpis["true"].update_value(
			format_signed(self.true_count),
			"True Count Hi-Lo"
		)
		indicators = self._calculate_indicators()
		self.kpis["p_low"].update_value(
			f"{indicators['low']:.2f}%",
			"Probabilidad de 2 a 6"
		)
		self.kpis["p_medium"].update_value(
			f"{indicators['medium']:.2f}%",
			"Probabilidad de 7 a 9"
		)
		self.kpis["p_high"].update_value(
			f"{indicators['high']:.2f}%",
			"Probabilidad de 10 a As"
		)
		self.kpis["p_ten"].update_value(
			f"{indicators['ten']:.2f}%",
			"Probabilidad de 10, J, Q o K"
		)
		self.kpis["p_ace"].update_value(
			f"{indicators['ace']:.2f}%",
			"Probabilidad de As"
		)
		self.kpis["p_blackjack"].update_value(
			f"{indicators['blackjack']:.2f}%",
			"Probabilidad en dos extracciones"
		)
		self.kpis["expected_hilo"].update_value(
			format_signed(
				indicators["expected_hilo"],
				4
			),
			"Valor Hi-Lo esperado por extracción"
		)
		self.probability_note.setText(
			f"Distribución calculada sobre {remaining:,} "
			f"cartas restantes."
		)
	# ========================================================
	# ACTUALIZAR CARTAS
	# ========================================================

	def _refresh_cards(self):
		total_remaining = self.remaining_cards

		for rank in RANKS:
			remaining = self.remaining_counts[rank]
			initial = self.initial_counts[rank]

			probability = safe_percentage(
				remaining,
				total_remaining
			)

			self.card_tiles[rank].update_card(
				remaining,
				initial,
				probability
			)
	# ========================================================
	# ACTUALIZAR TABLA
	# ========================================================
	def _refresh_table(self):
		total = self.remaining_cards
		for row, rank in enumerate(RANKS):
			initial = self.initial_counts[rank]
			dealt = self.dealt_counts[rank]
			remaining = self.remaining_counts[rank]
			probability = safe_percentage(
				remaining,
				total
			)
			depletion = safe_percentage(
				remaining,
				initial
			)
			values = [
				rank,
				str(initial),
				str(dealt),
				str(remaining),
				f"{probability:.2f}%",
				f"{depletion:.1f}%",
			]
			for column, value in enumerate(values):
				item = QTableWidgetItem(value)
				item.setTextAlignment(
					Qt.AlignmentFlag.AlignCenter
				)
				if column == 0:
					item.setFont(
						QFont(
							"Segoe UI",
							10,
							QFont.Weight.Bold
						)
					)
				if column == 4:
					item.setForeground(
						QColor(COLORS["blue"])
					)
					item.setFont(
						QFont(
							"Segoe UI",
							10,
							QFont.Weight.Bold
						)
					)
				if column == 5:
					if remaining == 0:
						background = QColor("#512F36")
					elif depletion >= 65:
						background = QColor("#244438")
					elif depletion >= 30:
						background = QColor("#51442B")
					else:
						background = QColor("#542F36")
					item.setBackground(
						QBrush(background)
					)
				if column == 3 and remaining == 0:
					item.setForeground(
						QColor(COLORS["red"])
					)
				self.table.setItem(
					row,
					column,
					item
				)
		self.table_note.setText(
			f"Probabilidades calculadas sobre {total:,} cartas. "
			"Disponibilidad = porcentaje del inventario inicial "
			"que permanece en el zapato."
		)
	# ========================================================
	# ACTUALIZAR COMPOSICIÓN
	# ========================================================
	def _refresh_composition(self):
		for key, data in self.group_bars.items():
			group = data["group"]
			count = sum(
				self.remaining_counts[rank]
				for rank in group
			)
			percentage = safe_percentage(
				count,
				self.remaining_cards
			)
			data["progress"].setValue(
				round(percentage)
			)
			data["count"].setText(
				f"{count:,} cartas restantes"
			)
			data["percentage"].setText(
				f"{percentage:.2f}%"
			)
		self.penetration_bar.setValue(
			round(self.penetration)
		)
		self.penetration_label.setText(
			f"{self.penetration:.2f}% utilizado"
		)
	# ========================================================
	# ACTUALIZAR GRÁFICA
	# ========================================================
	def _refresh_chart(self):
		self.history_chart.set_history(
			self.history
		)
	# ========================================================
	# ACTUALIZAR HISTORIAL
	# ========================================================
	def _refresh_history(self):
		recent = self.moves[-20:]
		recent = list(reversed(recent))
		if recent:
			self.history_label.setText(
				"  →  ".join(recent)
			)
		else:
			self.history_label.setText(
				"Sin movimientos"
			)
	# ========================================================
	# ACTUALIZACIÓN GENERAL
	# ========================================================
	def _refresh_dashboard(self):
		self._refresh_kpis()
		self._refresh_cards()
		self._refresh_table()
		self._refresh_composition()
		self._refresh_chart()
		self._refresh_history()
		self.deck_selector.setEnabled(
			self.dealt_cards == 0
		)
	# ========================================================
	# VALIDACIÓN DE CONSISTENCIA
	# ========================================================
	def validate_state(self):
		for rank in RANKS:
			if self.remaining_counts[rank] < 0:
				raise RuntimeError(
					f"Inventario negativo para {rank}"
				)
			if (
				self.remaining_counts[rank]
				+ self.dealt_counts[rank]
				!= self.initial_counts[rank]
			):
				raise RuntimeError(
					f"Error de consistencia para {rank}"
				)
		if (
			self.remaining_cards + self.dealt_cards
			!= self.total_cards
		):
			raise RuntimeError(
				"El inventario total no coincide."
			)
# ============================================================
# INICIO DE APLICACIÓN
# ============================================================
def main():
	app = QApplication(sys.argv)
	app.setApplicationName(APP_NAME)
	window = BlackjackShoeAnalytics()
	window.show()
	sys.exit(app.exec())
if __name__ == "__main__":
	main()
