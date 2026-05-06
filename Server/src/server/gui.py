"""ERTS Server – PySide6 GUI
Visualises live Firebase data: train states and station statistics.
"""
from __future__ import annotations

from PySide6.QtCore import (
    Qt, QTimer, Signal, QObject, Slot, QPointF,
)
from PySide6.QtGui import (
    QColor, QFont, QPalette, QPainter, QPen, QBrush,
    QLinearGradient, QFontMetrics,
)
from PySide6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QMainWindow, QProgressBar,
    QPushButton, QScrollArea, QSizePolicy, QSplitter,
    QStatusBar, QTabWidget, QVBoxLayout, QWidget,
)

from database.erts_firebase import _db as firebase_db
from database.erts_firebase.models import CurrentStatus, StationStats, TrainState
from database.erts_firebase import track as track_api
from database.erts_firebase import station as station_api
from database.erts_firebase.train import get_train
from database.utils.track_info import TRACKS, Track


# ---------------------------------------------------------------------------
# Signal bridge
# ---------------------------------------------------------------------------

class _FirebaseBridge(QObject):
    """Emits Qt signals from Firebase background callbacks."""
    train_updated  = Signal(str, str, object)   # track_id, train_id, data (dict|None)
    tracks_updated = Signal(str, object)         # track_id, full trains snapshot (dict|None)

    _instance: "_FirebaseBridge | None" = None

    @classmethod
    def instance(cls) -> "_FirebaseBridge":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STATUS_COLOR: dict[str, str] = {
    CurrentStatus.MOVING.value:  "#4CAF50",
    CurrentStatus.STOPPED.value: "#FF9800",
}

_BOOL_ICON = {True: "✅", False: "❌"}


def _delay_color(delay_s: int) -> QColor:
    """Green → yellow → red based on delay seconds."""
    if delay_s <= 0:
        return QColor("#4CAF50")
    elif delay_s < 10:
        # interpolate green→yellow
        t = delay_s / 10.0
        r = int(0x4C + t * (0xFF - 0x4C))
        g = int(0xAF + t * (0xC0 - 0xAF))
        return QColor(r, g, 0x50)
    elif delay_s < 30:
        # interpolate yellow→orange
        t = (delay_s - 10) / 20.0
        return QColor(0xFF, int(0xC0 - t * (0xC0 - 0x60)), 0)
    else:
        return QColor("#F44336")


def _colored_label(text: str, color: str = "") -> QLabel:
    lbl = QLabel(text)
    if color:
        lbl.setStyleSheet(f"color: {color};")
    return lbl


def _bold_label(text: str) -> QLabel:
    lbl = QLabel(text)
    font = lbl.font()
    font.setBold(True)
    lbl.setFont(font)
    return lbl


# ---------------------------------------------------------------------------
# Train Card widget
# ---------------------------------------------------------------------------

class TrainCard(QGroupBox):
    """Displays and updates a single train's state."""

    def __init__(self, track_id: str, train_id: str, parent: QWidget | None = None):
        super().__init__(f"🚆  Train: {train_id}", parent)
        self.track_id = track_id
        self.train_id = train_id
        self._state: TrainState | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(
            "QGroupBox { border: 1px solid #555; border-radius: 6px; margin-top: 8px; padding: 8px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
        )
        grid = QGridLayout(self)
        grid.setColumnStretch(1, 1)

        def row(r: int, label: str) -> QLabel:
            grid.addWidget(_bold_label(label), r, 0)
            val = QLabel("—")
            grid.addWidget(val, r, 1)
            return val

        self._lbl_status    = row(0, "Status")
        self._lbl_next      = row(1, "Next Station")
        self._lbl_delay     = row(2, "Current Delay (s)")
        self._lbl_stop_req  = row(3, "Stop Requested")
        self._lbl_camera    = row(4, "Camera Detected")
        self._lbl_will_stop = row(5, "Will Stop")

        grid.addWidget(_bold_label("Progress on Track"), 6, 0)
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setTextVisible(True)
        self._progress.setFixedHeight(18)
        grid.addWidget(self._progress, 6, 1)

    def update_state(self, state: TrainState) -> None:
        self._state = state
        color = _STATUS_COLOR.get(state.current_status.value, "#ffffff")
        self._lbl_status.setText(state.current_status.value.upper())
        self._lbl_status.setStyleSheet(f"color: {color}; font-weight: bold;")
        self._lbl_next.setText(state.next_station or "—")
        self._lbl_delay.setText(str(state.current_delay))
        self._lbl_stop_req.setText(_BOOL_ICON[state.stop_requested])
        self._lbl_camera.setText(_BOOL_ICON[state.camera_detected])
        self._lbl_will_stop.setText(_BOOL_ICON[state.will_stop])
        pct = int(state.progress_on_track * 100)
        self._progress.setValue(pct)
        self._progress.setFormat(f"{state.progress_on_track:.1%}")

    def mark_offline(self) -> None:
        self._lbl_status.setText("OFFLINE")
        self._lbl_status.setStyleSheet("color: #888;")


# ---------------------------------------------------------------------------
# Track Map View
# ---------------------------------------------------------------------------

class TrackMapView(QWidget):
    """
    Visual overview of a track.

    Draws a horizontal track line with station markers and animated train
    blobs.  Train blobs are colour-coded by current_delay:
        green  →  yellow  →  red
    """

    _TRACK_Y_FRAC   = 0.45   # vertical centre of the track line as fraction of height
    _MARGIN_X_FRAC  = 0.06   # left/right padding as fraction of width
    _TRAIN_R        = 12     # train blob radius (px)
    _STATION_H      = 14     # station tick half-height (px)
    _LABEL_OFFSET   = 18     # px below station tick

    def __init__(self, track: Track, parent: QWidget | None = None):
        super().__init__(parent)
        self._track = track
        # train_id → TrainState
        self._trains: dict[str, TrainState] = {}
        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setToolTip("Train colour: 🟢 no delay  🟡 moderate  🔴 high delay")

    def update_trains(self, trains: dict[str, TrainState]) -> None:
        self._trains = dict(trains)
        self.update()

    def update_train(self, train_id: str, state: TrainState) -> None:
        self._trains[train_id] = state
        self.update()

    # ── painting ────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        W = self.width()
        H = self.height()
        margin = int(W * self._MARGIN_X_FRAC)
        track_y = int(H * self._TRACK_Y_FRAC)
        track_len = W - 2 * margin

        def x_for(pos: float) -> int:
            return margin + int(pos * track_len)

        # ── background ──
        painter.fillRect(self.rect(), QColor("#181825"))

        # ── track line (gradient) ──
        grad = QLinearGradient(margin, 0, W - margin, 0)
        grad.setColorAt(0.0, QColor("#45475a"))
        grad.setColorAt(1.0, QColor("#585b70"))
        painter.setPen(QPen(QBrush(grad), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(margin, track_y, W - margin, track_y)

        # ── stations ──
        station_font = QFont(painter.font())
        station_font.setPointSize(8)
        painter.setFont(station_font)
        fm = QFontMetrics(station_font)

        for stop in self._track.stops:
            sx = x_for(stop.position)

            # tick mark
            painter.setPen(QPen(QColor("#cdd6f4"), 2))
            painter.drawLine(sx, track_y - self._STATION_H, sx, track_y + self._STATION_H)

            # station dot
            painter.setBrush(QBrush(QColor("#89b4fa")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(sx, track_y), 5, 5)

            # label – alternate above/below to reduce overlap
            label = stop.name
            lw = fm.horizontalAdvance(label)
            idx = self._track.stops.index(stop)
            if idx % 2 == 0:
                ly = track_y - self._STATION_H - 6
            else:
                ly = track_y + self._STATION_H + fm.ascent() + 2
            painter.setPen(QColor("#cdd6f4"))
            painter.drawText(sx - lw // 2, ly, label)

        # ── trains ──
        train_font = QFont(painter.font())
        train_font.setPointSize(7)
        train_font.setBold(True)
        painter.setFont(train_font)
        fm2 = QFontMetrics(train_font)

        for train_id, state in self._trains.items():
            tx = x_for(state.progress_on_track)
            ty = track_y

            color = _delay_color(state.current_delay)
            dark_color = color.darker(160)

            # glow ring
            painter.setBrush(Qt.BrushStyle.NoBrush)
            glow_pen = QPen(color, 2)
            glow_pen.setStyle(Qt.PenStyle.SolidLine)
            painter.setPen(glow_pen)
            painter.drawEllipse(
                QPointF(tx, ty),
                self._TRAIN_R + 4, self._TRAIN_R + 4,
            )

            # filled blob
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(dark_color, 1))
            painter.drawEllipse(QPointF(tx, ty), self._TRAIN_R, self._TRAIN_R)

            # train label
            short_id = train_id[-4:] if len(train_id) > 4 else train_id
            lw2 = fm2.horizontalAdvance(short_id)
            painter.setPen(QColor("#1e1e2e"))
            painter.drawText(tx - lw2 // 2, ty + fm2.ascent() // 2 - 1, short_id)

        # ── legend ──
        legend_items = [
            (QColor("#4CAF50"), "No delay"),
            (QColor("#FFC000"), "Moderate"),
            (QColor("#F44336"), "High delay"),
        ]
        lx = W - margin
        ly_base = H - 12
        legend_font = QFont(painter.font())
        legend_font.setPointSize(7)
        legend_font.setBold(False)
        painter.setFont(legend_font)
        fm3 = QFontMetrics(legend_font)
        for i, (col, lbl) in enumerate(reversed(legend_items)):
            item_w = fm3.horizontalAdvance(lbl) + 18
            lx -= item_w + 6
            painter.setBrush(QBrush(col))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(lx, ly_base - 7, 8, 8)
            painter.setPen(QColor("#a6adc8"))
            painter.drawText(lx + 12, ly_base, lbl)

        painter.end()


# ---------------------------------------------------------------------------
# Station Stats panel
# ---------------------------------------------------------------------------

class StationStatsPanel(QGroupBox):
    """Shows StationStats for all stations on a track."""

    def __init__(self, track: Track, parent: QWidget | None = None):
        super().__init__(f"📍  Stations – {track.name}", parent)
        self._track = track
        self._rows: dict[str, dict[str, QLabel]] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(
            "QGroupBox { border: 1px solid #555; border-radius: 6px; margin-top: 8px; padding: 8px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
        )
        layout = QVBoxLayout(self)

        hdr = QHBoxLayout()
        for h in ("Station", "Stops", "Pass-throughs", "Avg Delay (s)"):
            lbl = _bold_label(h)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hdr.addWidget(lbl)
        layout.addLayout(hdr)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #555;")
        layout.addWidget(line)

        for stop in self._track.stops:
            row_layout = QHBoxLayout()
            name_lbl = QLabel(stop.name)
            stop_lbl = QLabel("—")
            pass_lbl = QLabel("—")
            avg_lbl  = QLabel("—")
            for lbl in (name_lbl, stop_lbl, pass_lbl, avg_lbl):
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                row_layout.addWidget(lbl)
            self._rows[stop.id] = {
                "stop":  stop_lbl,
                "pass":  pass_lbl,
                "avg":   avg_lbl,
            }
            layout.addLayout(row_layout)

    def refresh(self) -> None:
        for stop in self._track.stops:
            try:
                stats = station_api.get_station(self._track.id, stop.id)
                if stats:
                    self.update_station(stop.id, stats)
            except Exception as e:
                print(f"Station refresh failed: {e}")

    def update_station(self, station_id: str, stats: StationStats) -> None:
        row = self._rows.get(station_id)
        if row is None:
            return
        total = stats.stop_count + stats.no_stop_count
        avg = (stats.total_delay_sum / total) if total else 0.0
        row["stop"].setText(str(stats.stop_count))
        row["pass"].setText(str(stats.no_stop_count))
        row["avg"].setText(f"{avg:.1f}")


# ---------------------------------------------------------------------------
# Track Panel – aggregates train cards + station panel for one track
# ---------------------------------------------------------------------------

class TrackPanel(QWidget):
    """Full panel for one track, with a tab for detail view and map view."""

    _TRAIN_POLL_MS   = 5_000
    _STATION_POLL_MS = 15_000

    def __init__(self, track: Track, parent: QWidget | None = None):
        super().__init__(parent)
        self._track = track
        self._train_cards: dict[str, TrainCard] = {}
        self._train_states: dict[str, TrainState] = {}
        self._listener = None
        self._bridge = _FirebaseBridge.instance()
        self._setup_ui()
        self._connect_signals()
        self._start_listening()

        # ── periodic station refresh ──
        self._station_timer = QTimer(self)
        self._station_timer.setInterval(self._STATION_POLL_MS)
        self._station_timer.timeout.connect(self._station_panel.refresh)
        self._station_timer.start()
        self._station_panel.refresh()

        # ── periodic train state refresh (poll Firebase) ──
        self._train_timer = QTimer(self)
        self._train_timer.setInterval(self._TRAIN_POLL_MS)
        self._train_timer.timeout.connect(self._poll_trains)
        self._train_timer.start()

    # ── UI ──────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)

        title = QLabel(f"🛤  Track: {self._track.name}  ({self._track.id})")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 4px;")
        root.addWidget(title)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #45475a; }"
            "QTabBar::tab { padding: 6px 18px; background: #313244; color: #cdd6f4; }"
            "QTabBar::tab:selected { background: #45475a; font-weight: bold; }"
        )
        root.addWidget(self._tabs)

        # ── Tab 1: Detail view ──
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(2, 2, 2, 2)

        splitter = QSplitter(Qt.Orientation.Vertical)
        detail_layout.addWidget(splitter)

        train_container = QWidget()
        self._train_layout = QVBoxLayout(train_container)
        self._train_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        placeholder = QLabel("Waiting for train data…")
        placeholder.setObjectName("placeholder")
        self._train_layout.addWidget(placeholder)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(train_container)
        scroll.setMinimumHeight(180)
        splitter.addWidget(scroll)

        self._station_panel = StationStatsPanel(self._track)
        splitter.addWidget(self._station_panel)

        self._tabs.addTab(detail_widget, "📋  Live Data")

        # ── Tab 2: Map view ──
        map_widget = QWidget()
        map_layout = QVBoxLayout(map_widget)
        map_layout.setContentsMargins(8, 8, 8, 8)

        self._map_view = TrackMapView(self._track)
        map_layout.addWidget(self._map_view, stretch=1)

        # Delay legend label
        hint = QLabel("Train colour reflects current delay  ·  refreshes every 5 s")
        hint.setStyleSheet("color: #585b70; font-size: 10px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        map_layout.addWidget(hint)

        self._tabs.addTab(map_widget, "🗺  Track Map")

    # ── Firebase ────────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._bridge.tracks_updated.connect(self._on_tracks_snapshot)

    def _start_listening(self) -> None:
        def _cb(path: str, data: object) -> None:
            self._bridge.tracks_updated.emit(self._track.id, data)

        try:
            self._listener = track_api.listen_trains(self._track.id, _cb)
        except Exception as exc:
            print(f"[TrackPanel] listen_trains error: {exc}")

    # ── Slots ────────────────────────────────────────────────────────────────

    @Slot(str, object)
    def _on_tracks_snapshot(self, track_id: str, data: object) -> None:
        if track_id != self._track.id:
            return
        if not isinstance(data, dict):
            return
        self._apply_trains_dict(data)

    def _apply_trains_dict(self, data: dict) -> None:
        """Parse and push a full trains snapshot to both views."""
        # Remove placeholder label
        placeholder = self.findChild(QLabel, "placeholder")
        if placeholder:
            placeholder.deleteLater()

        for train_id, train_data in data.items():
            if not isinstance(train_data, dict):
                continue
            try:
                state = TrainState.from_dict(train_data)
            except Exception:
                continue

            self._train_states[train_id] = state

            # ── Detail card ──
            if train_id not in self._train_cards:
                card = TrainCard(self._track.id, train_id)
                self._train_cards[train_id] = card
                self._train_layout.addWidget(card)
            self._train_cards[train_id].update_state(state)

        # ── Map view ──
        self._map_view.update_trains(self._train_states)

    def _poll_trains(self) -> None:
        """Periodically re-fetch all known train states from Firebase."""
        if not self._train_states:
            return
        updated: dict[str, TrainState] = {}
        for train_id in list(self._train_states.keys()):
            try:
                state = get_train(self._track.id, train_id)
            except Exception:
                state = None
            if state is not None:
                updated[train_id] = state
                if train_id in self._train_cards:
                    self._train_cards[train_id].update_state(state)
        if updated:
            self._train_states.update(updated)
            self._map_view.update_trains(self._train_states)

    def closeEvent(self, event):  # noqa: N802
        if self._listener:
            try:
                self._listener.close()
            except Exception:
                pass
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ERTS – Real-Time Railway Visualiser")
        self.resize(1200, 720)
        self._track_panels: dict[str, TrackPanel] = {}
        self._setup_ui()
        self._setup_status_bar()

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ──
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("QFrame { background: #1e1e2e; }")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 12, 8, 8)

        logo = QLabel("🚄 ERTS Monitor")
        logo.setStyleSheet("color: #cdd6f4; font-size: 15px; font-weight: bold;")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(logo)

        sidebar_layout.addSpacing(12)
        sidebar_layout.addWidget(_bold_label("Tracks"))

        self._sidebar_buttons: dict[str, QPushButton] = {}
        for track_id, track in TRACKS.items():
            btn = QPushButton(f"  {track.name}")
            btn.setCheckable(True)
            btn.setStyleSheet(
                "QPushButton { text-align: left; padding: 6px 8px; border-radius: 4px;"
                "  background: transparent; color: #cdd6f4; border: none; }"
                "QPushButton:hover { background: #313244; }"
                "QPushButton:checked { background: #45475a; font-weight: bold; }"
            )
            btn.clicked.connect(lambda checked, tid=track_id: self._show_track(tid))
            sidebar_layout.addWidget(btn)
            self._sidebar_buttons[track_id] = btn

        sidebar_layout.addStretch()

        refresh_btn = QPushButton("⟳  Refresh All")
        refresh_btn.setStyleSheet(
            "QPushButton { padding: 6px; border-radius: 4px; background: #313244; color: #cdd6f4; }"
            "QPushButton:hover { background: #45475a; }"
        )
        refresh_btn.clicked.connect(self._refresh_all)
        sidebar_layout.addWidget(refresh_btn)

        root.addWidget(sidebar)

        # ── Content area ──
        self._content = _StackedLikeContainer()
        root.addWidget(self._content, stretch=1)

        for track_id, track in TRACKS.items():
            panel = TrackPanel(track)
            self._track_panels[track_id] = panel
            self._content.add_panel(track_id, panel)

        if TRACKS:
            first = next(iter(TRACKS))
            self._show_track(first)

    def _setup_status_bar(self) -> None:
        bar = QStatusBar()
        self.setStatusBar(bar)
        bar.showMessage("Connected to Firebase  •  Live updates + 5 s poll active")

    def _show_track(self, track_id: str) -> None:
        self._content.show_panel(track_id)
        for tid, btn in self._sidebar_buttons.items():
            btn.setChecked(tid == track_id)

    def _refresh_all(self) -> None:
        for panel in self._track_panels.values():
            panel._station_panel.refresh()
            panel._poll_trains()
        self.statusBar().showMessage("Refreshed all data", 3000)


# ---------------------------------------------------------------------------
# Simple stacked container
# ---------------------------------------------------------------------------

class _StackedLikeContainer(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._panels: dict[str, QWidget] = {}

    def add_panel(self, key: str, widget: QWidget) -> None:
        self._panels[key] = widget
        self._layout.addWidget(widget)
        widget.hide()

    def show_panel(self, key: str) -> None:
        for k, w in self._panels.items():
            w.setVisible(k == key)


# ---------------------------------------------------------------------------
# App entry point
# ---------------------------------------------------------------------------

def run_gui(
    service_account_path: str | None = None,
    database_url: str | None = None,
) -> None:
    """Initialize Firebase, then launch the Qt application."""
    firebase_db.init(
        service_account_path=service_account_path,
        database_url=database_url,
    )

    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor("#1e1e2e"))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor("#cdd6f4"))
    palette.setColor(QPalette.ColorRole.Base,            QColor("#181825"))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor("#1e1e2e"))
    palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor("#cdd6f4"))
    palette.setColor(QPalette.ColorRole.ToolTipText,     QColor("#cdd6f4"))
    palette.setColor(QPalette.ColorRole.Text,            QColor("#cdd6f4"))
    palette.setColor(QPalette.ColorRole.Button,          QColor("#313244"))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor("#cdd6f4"))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor("#89b4fa"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#1e1e2e"))
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    app.exec()

