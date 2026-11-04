from __future__ import annotations
from typing import List, Optional, Tuple
from PyQt6.QtCore import Qt, QThreadPool, QRunnable, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QComboBox, QCheckBox, QToolBar, QFrame,
    QDoubleSpinBox
)

from core.rules import TableRules
from core.shoe import CompositionShoe
from core.combinatorial import CompositionDependentEngine, DecisionEvaluation
from core.counting import CardCounter, CountingSystem, RoundingMode
from core.ap_metrics import AdvantagePlayMetrics, KellyFraction, BetRecommendation
from gui.components.ap_hud import APHudWidget
from gui.views.table_view_controller import TableViewController
from gui.views.drills_view import DrillsView
from gui.views.academy_view import AcademyView
from gui.views.xai_view import XAIView


class WorkerSignals(QObject):
    finished = pyqtSignal(int, object, int, float, object)
    error = pyqtSignal(int, str)


class CDEvaluationWorker(QRunnable):
    """Worker concurrente no bloqueante con token atómico de invalidación de carreras."""

    def __init__(
        self,
        eval_id: int,
        engine: CompositionDependentEngine,
        player_cards: Tuple[int, ...],
        upcard: int,
        shoe: CompositionShoe,
        counter: CardCounter,
        bankroll: float
    ) -> None:
        super().__init__()
        self.eval_id = eval_id
        self.engine = engine
        self.player_cards = player_cards
        self.upcard = upcard
        self.shoe = shoe
        self.counter = counter
        self.bankroll = bankroll
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            eval_cd, tc, edge = self.engine.evaluate_hand_with_counting(
                self.player_cards, self.upcard, self.shoe, self.counter
            )
            bet_rec = AdvantagePlayMetrics.recommend_bet(
                bankroll=self.bankroll,
                true_count=tc,
                base_edge=edge - (tc * 0.005),
                kelly_fraction=KellyFraction.HALF
            )
            self.signals.finished.emit(self.eval_id, eval_cd, tc, edge, bet_rec)
        except Exception as e:
            self.signals.error.emit(self.eval_id, str(e))


class MainWindow(QMainWindow):
    """Ventana Maestra con las 4 vistas integradas y sincronización reactiva de reglas."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("QUANTITATIVE AP BLACKJACK SUITE — Professional Desktop Engine")
        self.resize(1400, 800)

        self.rules = TableRules(decks=6, dealer_hits_soft_17=False, is_hole_card_game=True, allow_das=True)
        self.shoe = CompositionShoe.from_decks(6)
        self.counter = CardCounter(system=CountingSystem.HI_LO, rounding_mode=RoundingMode.FLOOR)
        self.engine = CompositionDependentEngine(self.rules)
        self.thread_pool = QThreadPool.globalInstance()

        self._bankroll: float = 10_000.0
        self._current_eval_id: int = 0

        self._init_qss()
        self._build_top_toolbar()
        self._build_ui_layout()

    def _init_qss(self) -> None:
        self.setStyleSheet("""
            QMainWindow { background-color: #0F1117; }
            QToolBar {
                background-color: #1A1D24;
                border-bottom: 1px solid #2B2F3A;
                padding: 4px;
                spacing: 8px;
            }
            QLabel {
                color: #CFD8DC;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            QComboBox, QDoubleSpinBox {
                background-color: #14171F;
                color: #00E676;
                border: 1px solid #2B2F3A;
                border-radius: 4px;
                padding: 4px 8px;
                font-family: Consolas;
                font-size: 13px;
            }
            QComboBox::drop-down { border: none; }
            QCheckBox {
                color: #90A4AE;
                font-size: 13px;
                spacing: 5px;
            }
            QCheckBox::indicator:checked {
                background-color: #00E676;
                border: 1px solid #00E676;
            }
            QPushButton.nav-btn {
                background-color: transparent;
                color: #90A4AE;
                font-size: 14px;
                font-weight: bold;
                border: none;
                padding: 10px 16px;
                border-radius: 4px;
                text-align: left;
            }
            QPushButton.nav-btn:hover {
                background-color: #1A1D24;
                color: #FFFFFF;
            }
            QPushButton.nav-btn:checked {
                background-color: #2979FF;
                color: #FFFFFF;
            }
        """)

    def _build_top_toolbar(self) -> None:
        toolbar = QToolBar("Rule Controls", self)
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        toolbar.addWidget(QLabel(" Mazos: "))
        self.combo_decks = QComboBox()
        self.combo_decks.addItems(["1", "2", "4", "6", "8"])
        self.combo_decks.setCurrentText("6")
        self.combo_decks.currentIndexChanged.connect(self._on_rule_changed)
        toolbar.addWidget(self.combo_decks)

        toolbar.addWidget(QLabel(" Crupier: "))
        self.combo_dealer = QComboBox()
        self.combo_dealer.addItems(["Stand Soft 17 (S17)", "Hit Soft 17 (H17)"])
        self.combo_dealer.currentIndexChanged.connect(self._on_rule_changed)
        toolbar.addWidget(self.combo_dealer)

        toolbar.addWidget(QLabel(" Pago BJ: "))
        self.combo_payout = QComboBox()
        self.combo_payout.addItems(["3:2 (1.5x)", "6:5 (1.2x)"])
        self.combo_payout.currentIndexChanged.connect(self._on_rule_changed)
        toolbar.addWidget(self.combo_payout)

        toolbar.addWidget(QLabel(" Tipo: "))
        self.combo_peek = QComboBox()
        self.combo_peek.addItems(["American Peek", "ENHC"])
        self.combo_peek.currentIndexChanged.connect(self._on_rule_changed)
        toolbar.addWidget(self.combo_peek)

        self.chk_das = QCheckBox("DAS")
        self.chk_das.setChecked(True)
        self.chk_das.stateChanged.connect(self._on_rule_changed)
        toolbar.addWidget(self.chk_das)

        self.chk_rsa = QCheckBox("RSA")
        self.chk_rsa.setChecked(True)
        self.chk_rsa.stateChanged.connect(self._on_rule_changed)
        toolbar.addWidget(self.chk_rsa)

        self.chk_surr = QCheckBox("Late Surrender")
        self.chk_surr.setChecked(True)
        self.chk_surr.stateChanged.connect(self._on_rule_changed)
        toolbar.addWidget(self.chk_surr)
        
        toolbar.addWidget(QLabel("   Capital Inicial ($): "))
        self.spin_start_bankroll = QDoubleSpinBox()
        self.spin_start_bankroll.setRange(100.0, 1_000_000.0)
        self.spin_start_bankroll.setValue(10_000.0)
        self.spin_start_bankroll.setSingleStep(1000.0)
        toolbar.addWidget(self.spin_start_bankroll)

        self.btn_reset = QPushButton("Reiniciar Sesión")
        self.btn_reset.setStyleSheet("""
            background-color: #FF5252; 
            color: #0F1117; 
            font-weight: bold; 
            padding: 4px 10px; 
            border-radius: 4px; 
            margin-left: 10px;
        """)
        self.btn_reset.clicked.connect(self.reset_session)
        toolbar.addWidget(self.btn_reset)

    def _build_ui_layout(self) -> None:
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        root_layout = QHBoxLayout(main_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        nav_bar = QFrame(self)
        nav_bar.setFixedWidth(200)
        nav_bar.setStyleSheet("background-color: #14171F; border-right: 1px solid #2B2F3A;")
        nav_layout = QVBoxLayout(nav_bar)
        nav_layout.setContentsMargins(8, 14, 8, 14)
        nav_layout.setSpacing(6)

        lbl_app = QLabel("QUANT LAB AP")
        lbl_app.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold; margin-bottom: 14px; margin-left: 6px;")
        nav_layout.addWidget(lbl_app)

        self.btn_table = QPushButton("Mesa AP / Coach")
        self.btn_drills = QPushButton("Gimnasio Drills")
        self.btn_academy = QPushButton("Academia Cuant")
        self.btn_xai = QPushButton("Árbol XAI (EV)")

        for btn in (self.btn_table, self.btn_drills, self.btn_academy, self.btn_xai):
            btn.setCheckable(True)
            btn.setProperty("class", "nav-btn")
            nav_layout.addWidget(btn)

        self.btn_table.setChecked(True)
        self.btn_table.clicked.connect(lambda: self._set_active_view(0))
        self.btn_drills.clicked.connect(lambda: self._set_active_view(1))
        self.btn_academy.clicked.connect(lambda: self._set_active_view(2))
        self.btn_xai.clicked.connect(lambda: self._set_active_view(3))

        nav_layout.addStretch()
        root_layout.addWidget(nav_bar)

        self.stack = QStackedWidget(self)
        root_layout.addWidget(self.stack, 1)

        self.hud = APHudWidget(self)

        view_table_container = QWidget()
        vt_layout = QHBoxLayout(view_table_container)
        vt_layout.setContentsMargins(0, 0, 0, 0)
        vt_layout.setSpacing(0)

        self.table_controller = TableViewController(
            rules=self.rules,
            shoe=self.shoe,
            counter=self.counter,
            engine=self.engine,
            hud=self.hud,
            parent=self
        )
        vt_layout.addWidget(self.table_controller, 1)
        vt_layout.addWidget(self.hud)
        self.stack.addWidget(view_table_container)

        self.view_drills = DrillsView(self)
        self.stack.addWidget(self.view_drills)

        self.view_academy = AcademyView(rules=self.rules, parent=self)
        self.stack.addWidget(self.view_academy)

        self.view_xai = XAIView(rules=self.rules, parent=self)
        self.stack.addWidget(self.view_xai)

    def _set_active_view(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        buttons = [self.btn_table, self.btn_drills, self.btn_academy, self.btn_xai]
        for i, b in enumerate(buttons):
            b.setChecked(i == index)

    def reset_session(self) -> None:
        self._bankroll = self.spin_start_bankroll.value()
        self.table_controller.bankroll = self._bankroll
        self.table_controller.full_reset()

    def _on_rule_changed(self) -> None:
        decks = int(self.combo_decks.currentText())
        h17 = self.combo_dealer.currentIndex() == 1
        payout = 1.2 if self.combo_payout.currentIndex() == 1 else 1.5
        is_hole = self.combo_peek.currentIndex() == 0
        das = self.chk_das.isChecked()
        rsa = self.chk_rsa.isChecked()
        surr = self.chk_surr.isChecked()

        self.rules = TableRules(
            decks=decks,
            dealer_hits_soft_17=h17,
            blackjack_payout=payout,
            is_hole_card_game=is_hole,
            allow_das=das,
            allow_rsa=rsa,
            allow_late_surrender=surr
        )
        self.engine = CompositionDependentEngine(self.rules)
        self.table_controller.rules = self.rules
        self.table_controller.engine = self.engine
        
        self.table_controller.reset_shoe_and_counter()

        self.view_academy.update_rules(self.rules)
        self.view_xai.update_rules(self.rules)

    def trigger_async_evaluation(self, player_cards: Tuple[int, ...], dealer_upcard: int) -> None:
        self._current_eval_id += 1
        eval_id = self._current_eval_id

        worker = CDEvaluationWorker(
            eval_id=eval_id,
            engine=self.engine,
            player_cards=player_cards,
            upcard=dealer_upcard,
            shoe=self.shoe,
            counter=self.counter,
            bankroll=self._bankroll
        )
        worker.signals.finished.connect(self._on_async_evaluation_finished)
        self.thread_pool.start(worker)

    def _on_async_evaluation_finished(
        self,
        eval_id: int,
        eval_cd: DecisionEvaluation,
        tc: int,
        edge: float,
        bet_rec: BetRecommendation
    ) -> None:
        if eval_id < self._current_eval_id:
            return

        self.hud.update_telemetry(
            rc=self.counter.running_count,
            tc=tc,
            edge=edge,
            bet_rec=bet_rec,
            shoe_counts=self.shoe.counts,
            total_cards=self.shoe.total_cards,
            eval_cd=eval_cd,
            decks=self.rules.decks
        )