"""
ui.py — Interface graphique PyQt5 du serveur arbitre Dance Battle.

Lance le serveur HTTP défini dans server.py dans un thread séparé et
offre un panneau de contrôle, un tableau des robots et un journal.

Usage :
    source venv/bin/activate
    python ui.py
"""

import sys
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QTextEdit,
    QFileDialog, QGroupBox, QSplitter, QHeaderView, QFrame,
    QStatusBar, QAbstractItemView,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QColor, QPalette

import server as srv

DARK_BG      = "#0a0a0a"
PANEL_BG     = "#111111"
ACCENT       = "#9d8fff"
ACCENT2      = "#ff5370"
SUCCESS      = "#3ddc84"
WARNING      = "#ffb86c"
TEXT_PRIMARY = "#e0e0e0"
TEXT_MUTED   = "#555555"
BORDER       = "#222222"

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {DARK_BG};
    color: {TEXT_PRIMARY};
    font-family: 'Segoe UI', 'Inter', 'Roboto', sans-serif;
    font-size: 13px;
}}
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 14px;
    padding: 10px 8px 8px 8px;
    background-color: {PANEL_BG};
    font-weight: bold;
    font-size: 11px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {ACCENT};
}}
QPushButton {{
    background-color: #1a1a1a;
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 7px 16px;
    font-weight: 600;
    font-size: 12px;
}}
QPushButton:hover  {{ background-color: #202020; border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton:pressed {{ background-color: #0d0d0d; }}
QPushButton:disabled {{ background-color: #0f0f0f; color: {TEXT_MUTED}; border-color: #1a1a1a; }}
QPushButton#btn_start {{ background-color: #0f1a0f; border-color: #2a4a2a; color: {SUCCESS}; }}
QPushButton#btn_start:hover {{ background-color: #152015; border-color: {SUCCESS}; }}
QPushButton#btn_stop {{ background-color: #1a0f0f; border-color: #4a1a1a; color: {ACCENT2}; }}
QPushButton#btn_stop:hover {{ background-color: #201515; border-color: {ACCENT2}; }}
QPushButton#btn_clear {{
    background-color: transparent;
    border: 1px solid #1e1e1e;
    color: {TEXT_MUTED};
    font-size: 11px;
    padding: 4px 10px;
}}
QPushButton#btn_clear:hover {{ border-color: #333333; color: #888888; }}
QTextEdit {{
    background-color: #050505;
    border: 1px solid {BORDER};
    border-radius: 5px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    padding: 8px;
    color: {TEXT_PRIMARY};
}}
QTableWidget {{
    background-color: #050505;
    border: 1px solid {BORDER};
    border-radius: 5px;
    gridline-color: #181818;
    selection-background-color: #1e1e2e;
    alternate-background-color: #0d0d0d;
    color: {TEXT_PRIMARY};
}}
QTableWidget::item {{ padding: 7px 12px; border: none; }}
QTableWidget::item:selected {{ background-color: #1e1e2e; color: {ACCENT}; }}
QHeaderView::section {{
    background-color: #0a0a0a;
    color: {TEXT_MUTED};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px 12px;
    font-weight: bold;
    font-size: 11px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}
QScrollBar:vertical {{ background: #0a0a0a; width: 6px; border: none; }}
QScrollBar::handle:vertical {{ background: #2a2a2a; border-radius: 3px; min-height: 20px; }}
QScrollBar::handle:vertical:hover {{ background: #3a3a3a; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: #0a0a0a; height: 6px; border: none; }}
QScrollBar::handle:horizontal {{ background: #2a2a2a; border-radius: 3px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QLabel#lbl_title {{ font-size: 18px; font-weight: bold; color: {TEXT_PRIMARY}; letter-spacing: 0.5px; }}
QLabel#lbl_sub   {{ font-size: 11px; color: {TEXT_MUTED}; }}
QStatusBar {{ background-color: #080808; color: {TEXT_MUTED}; border-top: 1px solid {BORDER}; font-size: 11px; padding: 2px 8px; }}
QSplitter::handle {{ background-color: {BORDER}; width: 1px; }}
"""

LOG_COLORS = {
    "info":    "#666666",
    "success": "#3ddc84",
    "warning": "#ffb86c",
    "error":   "#ff5370",
    "step":    "#82aaff",
}

MEDALS = ["#1", "#2", "#3"]


# ─── Bridge thread HTTP → thread Qt ──────────────────────────────────────────

class _Bridge(QObject):
    """Transmet les événements du thread HTTP vers le thread Qt via signaux."""
    log_signal     = pyqtSignal(str, str)   # (message, level)
    robots_changed = pyqtSignal()

_bridge = _Bridge()

def _on_server_event(message, level):
    """Callback passé à server.set_event_callback — appelé depuis le thread HTTP."""
    _bridge.log_signal.emit(message, level)
    if any(k in message for k in ("/hello", "/step", "/bye")):
        _bridge.robots_changed.emit()

srv.set_event_callback(_on_server_event)


class ServerThread(QThread):
    started_ok = pyqtSignal(int)
    stopped    = pyqtSignal()
    error      = pyqtSignal(str)

    def __init__(self, port=8080):
        super().__init__()
        self.port  = port
        self._httpd = None

    def run(self):
        try:
            self._httpd = srv.creer_serveur(self.port)
            self.started_ok.emit(self.port)
            self._httpd.serve_forever()
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.stopped.emit()

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd = None


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dance Battle — Serveur Arbitre")
        self.resize(1100, 700)
        self.setStyleSheet(STYLESHEET)
        self._thread = None
        self._build_ui()
        self._connect_signals()
        # Rafraîchissement périodique de la table
        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh_table)
        self._timer.start(800)

    # ── Helpers UI ────────────────────────────────────────────────────────────

    def _label(self, text, color=TEXT_MUTED, size=11, bold=False):
        """Crée un QLabel stylisé inline."""
        lbl = QLabel(text)
        weight = "bold" if bold else "normal"
        lbl.setStyleSheet(f"color:{color}; font-size:{size}px; font-weight:{weight};")
        return lbl

    def _separator(self, orientation=QFrame.HLine):
        """Crée un séparateur horizontal ou vertical."""
        sep = QFrame()
        sep.setFrameShape(orientation)
        sep.setStyleSheet(f"color:{BORDER};")
        return sep

    # ── Construction de l'interface ───────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(10)
        root.setContentsMargins(16, 12, 16, 12)

        title = QLabel("Dance Battle Server")
        title.setObjectName("lbl_title")
        sub = QLabel("Serveur arbitre HTTP — contrôle des robots et des scores")
        sub.setObjectName("lbl_sub")
        self.lbl_dot = self._label("●", TEXT_MUTED, size=12)
        self.lbl_srv = self._label("arrêté")

        hdr = QHBoxLayout()
        vbl = QVBoxLayout()
        vbl.addWidget(title)
        vbl.addWidget(sub)
        hdr.addLayout(vbl)
        hdr.addStretch()
        hdr.addWidget(self.lbl_dot)
        hdr.addWidget(self.lbl_srv)
        root.addLayout(hdr)
        root.addWidget(self._separator())

        self.btn_start  = QPushButton("▶  Démarrer  :8080")
        self.btn_start.setObjectName("btn_start")
        self.btn_stop   = QPushButton("■  Arrêter")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setEnabled(False)
        self.btn_battle = QPushButton("📂  Charger .battle")
        self.lbl_battle = self._label("Aucun fichier chargé")

        ctrl = QGroupBox("Contrôles")
        cl = QHBoxLayout(ctrl)
        cl.setSpacing(10)
        cl.addWidget(self.btn_start)
        cl.addWidget(self.btn_stop)
        cl.addWidget(self._separator(QFrame.VLine))
        cl.addWidget(self.btn_battle)
        cl.addWidget(self.lbl_battle)
        cl.addStretch()
        root.addWidget(ctrl)

        # Panneau gauche — Robots
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["🤖 Robot ID", "📊 Score", "👣 Pas", "🏆 Rang"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)

        self.lbl_count = self._label("0 robot(s)")
        self.lbl_mvs   = self._label("MVS: —", color=ACCENT, bold=True)

        stats = QHBoxLayout()
        stats.addWidget(self.lbl_count)
        stats.addStretch()
        stats.addWidget(self.lbl_mvs)

        robots_grp = QGroupBox("Robots connectés")
        rl = QVBoxLayout(robots_grp)
        rl.addWidget(self.table)
        rl.addLayout(stats)

        # Panneau droit — Logs
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QTextEdit.NoWrap)

        self.btn_clear = QPushButton("🗑  Effacer les logs")
        self.btn_clear.setObjectName("btn_clear")
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self.btn_clear)

        logs_grp = QGroupBox("Journal des événements")
        lgl = QVBoxLayout(logs_grp)
        lgl.addWidget(self.log_view)
        lgl.addLayout(btn_row)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)
        splitter.addWidget(robots_grp)
        splitter.addWidget(logs_grp)
        splitter.setSizes([400, 700])
        root.addWidget(splitter, stretch=1)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Prêt — Chargez un fichier .battle puis démarrez le serveur.")

    # ── Connexions ────────────────────────────────────────────────────────────

    def _connect_signals(self):
        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_battle.clicked.connect(self._on_load_battle)
        self.btn_clear.clicked.connect(self.log_view.clear)
        _bridge.log_signal.connect(self._append_log)
        _bridge.robots_changed.connect(self._refresh_table)

    # ── Démarrage / arrêt ─────────────────────────────────────────────────────

    def _set_server_status(self, running, port=None):
        """Met à jour l'indicateur de statut du serveur."""
        color = SUCCESS if running else TEXT_MUTED
        text  = f"actif :{port}" if running else "arrêté"
        self.lbl_dot.setStyleSheet(f"font-size:12px; color:{color};")
        self.lbl_srv.setStyleSheet(f"color:{color}; font-size:11px; letter-spacing:0.5px;")
        self.lbl_srv.setText(text)
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)

    def _on_start(self):
        if self._thread and self._thread.isRunning():
            return
        self._thread = ServerThread(port=8080)
        self._thread.started_ok.connect(self._on_started)
        self._thread.stopped.connect(self._on_stopped)
        self._thread.error.connect(self._on_error)
        self._thread.start()
        self._set_server_status(False)   # désactive les boutons pendant démarrage
        self.btn_stop.setEnabled(True)

    def _on_stop(self):
        if self._thread:
            self._thread.stop()
            self._thread.wait(3000)

    def _on_started(self, port):
        self._set_server_status(True, port)
        self.statusBar().showMessage(f"✅ Serveur HTTP démarré sur le port {port}")
        self._append_log(f"Serveur démarré sur le port {port}", "success")

    def _on_stopped(self):
        self._set_server_status(False)
        self.statusBar().showMessage("Serveur arrêté.")
        self._append_log("Serveur arrêté.", "warning")

    def _on_error(self, msg):
        self._append_log(f"ERREUR : {msg}", "error")
        self.statusBar().showMessage(f"Erreur : {msg}")
        self._set_server_status(False)


    def _on_load_battle(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Charger fichier .battle", "", "Battle Files (*.battle);;Tous (*)"
        )
        if not path:
            return
        try:
            rules = srv.charger_battle(path)
            fname = path.split("/")[-1]
            self.lbl_battle.setText(f"✅ {fname}")
            self.lbl_battle.setStyleSheet(f"color:{SUCCESS}; font-size:11px;")
            self.lbl_mvs.setText(f"MVS: {rules.get('mvs', 10)} mouvements")
            self.statusBar().showMessage(f"Règles chargées depuis {path}")
        except Exception as e:
            self._append_log(f"Erreur chargement .battle : {e}", "error")

    def _refresh_table(self):
        with srv._lock:
            snapshot = dict(srv.robots)

        sorted_robots = sorted(snapshot.items(), key=lambda x: x[1]["score"], reverse=True)
        self.lbl_count.setText(f"{len(snapshot)} robot(s) connecté(s)")
        self.table.setRowCount(len(sorted_robots))

        for i, (rid, data) in enumerate(sorted_robots):
            score = data["score"]
            rang  = MEDALS[i] if i < 3 else f"#{i+1}"
            cells = [rid, str(score), str(data["steps"]), rang]
            for ci, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                if ci == 0:
                    item.setForeground(QColor(ACCENT))
                elif ci == 1:
                    item.setForeground(QColor(SUCCESS if score >= 0 else ACCENT2))
                if i == 0 and len(snapshot) > 1:
                    item.setBackground(QColor("#0d150d"))
                self.table.setItem(i, ci, item)

    def _append_log(self, message, level="info"):
        color = LOG_COLORS.get(level, "#aaaacc")
        ts    = datetime.now().strftime("%H:%M:%S")
        html  = (
            f'<span style="color:#555577;">[{ts}]</span> '
            f'<span style="color:{color};">{message}</span><br>'
        )
        cursor = self.log_view.textCursor()
        cursor.movePosition(cursor.End)
        self.log_view.setTextCursor(cursor)
        self.log_view.insertHtml(html)
        self.log_view.moveCursor(cursor.End)

    def closeEvent(self, event):
        self._on_stop()
        event.accept()

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    for role, color in [
        (QPalette.Window,          DARK_BG),
        (QPalette.WindowText,      TEXT_PRIMARY),
        (QPalette.Base,            "#050505"),
        (QPalette.AlternateBase,   "#0d0d0d"),
        (QPalette.Text,            TEXT_PRIMARY),
        (QPalette.Button,          PANEL_BG),
        (QPalette.ButtonText,      TEXT_PRIMARY),
        (QPalette.Highlight,       "#1e1e2e"),
        (QPalette.HighlightedText, ACCENT),
        (QPalette.Mid,             BORDER),
        (QPalette.Dark,            "#080808"),
        (QPalette.Shadow,          "#000000"),
    ]:
        palette.setColor(role, QColor(color))
    app.setPalette(palette)

    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
