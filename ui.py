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

# ─── Import de la logique serveur ────────────────────────────────────────────
import server as srv


# ─────────────────────────────────────────────────────────────────────────────
#  Bridge thread HTTP → thread Qt (via QObject + signals)
# ─────────────────────────────────────────────────────────────────────────────

class _Bridge(QObject):
    """Reçoit les événements depuis le thread HTTP et les réémet en Qt."""
    log_signal     = pyqtSignal(str, str)   # (message, level)
    robots_changed = pyqtSignal()

_bridge = _Bridge()


def _on_server_event(message, level):
    """Callback passé à server.set_event_callback — appelé depuis le thread HTTP."""
    _bridge.log_signal.emit(message, level)
    # Si l'événement concerne l'état des robots, on rafraîchit la table
    if any(k in message for k in ("/hello", "/step", "/bye")):
        _bridge.robots_changed.emit()

srv.set_event_callback(_on_server_event)


# ─────────────────────────────────────────────────────────────────────────────
#  Thread serveur HTTP
# ─────────────────────────────────────────────────────────────────────────────

class ServerThread(QThread):
    started_ok = pyqtSignal(int)
    stopped    = pyqtSignal()
    error      = pyqtSignal(str)

    def __init__(self, port=8080):
        super().__init__()
        self.port = port
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


# ─────────────────────────────────────────────────────────────────────────────
#  Palette / couleurs
# ─────────────────────────────────────────────────────────────────────────────

DARK_BG      = "#1a1d2e"
PANEL_BG     = "#242740"
ACCENT       = "#6c63ff"
ACCENT2      = "#ff6584"
SUCCESS      = "#43e97b"
WARNING      = "#f7971e"
TEXT_PRIMARY = "#e8e8f0"
TEXT_MUTED   = "#8888aa"
BORDER       = "#3a3d55"

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {DARK_BG};
    color: {TEXT_PRIMARY};
    font-family: 'Segoe UI', 'Inter', 'Roboto', sans-serif;
    font-size: 13px;
}}
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 12px;
    padding: 8px;
    background-color: {PANEL_BG};
    font-weight: bold;
    font-size: 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {ACCENT};
}}
QPushButton {{
    background-color: {ACCENT};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: bold;
}}
QPushButton:hover  {{ background-color: #7c73ff; }}
QPushButton:pressed {{ background-color: #5a53cc; }}
QPushButton:disabled {{ background-color: #3a3d55; color: {TEXT_MUTED}; }}
QPushButton#btn_stop {{
    background-color: {ACCENT2};
}}
QPushButton#btn_stop:hover {{ background-color: #ff7a9a; }}
QPushButton#btn_clear {{
    background-color: #3a3d55;
    color: {TEXT_MUTED};
    font-size: 11px;
    padding: 5px 12px;
}}
QPushButton#btn_clear:hover {{ background-color: #4a4d70; color: {TEXT_PRIMARY}; }}
QTextEdit {{
    background-color: #12141f;
    border: 1px solid {BORDER};
    border-radius: 6px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    padding: 6px;
}}
QTableWidget {{
    background-color: #12141f;
    border: 1px solid {BORDER};
    border-radius: 6px;
    gridline-color: {BORDER};
    selection-background-color: {ACCENT};
    alternate-background-color: #1e2133;
}}
QTableWidget::item {{ padding: 6px 10px; border: none; }}
QHeaderView::section {{
    background-color: {PANEL_BG};
    color: {ACCENT};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px 10px;
    font-weight: bold;
    font-size: 12px;
}}
QLabel#lbl_title   {{ font-size: 20px; font-weight: bold; color: {ACCENT}; }}
QLabel#lbl_sub     {{ font-size: 11px; color: {TEXT_MUTED}; }}
QStatusBar {{
    background-color: {PANEL_BG};
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
    font-size: 11px;
}}
QSplitter::handle {{ background-color: {BORDER}; width: 2px; }}
"""

LOG_COLORS = {
    "info":    "#aaaacc",
    "success": "#43e97b",
    "warning": "#f7971e",
    "error":   "#ff6584",
    "step":    "#6cd8fa",
}


# ─────────────────────────────────────────────────────────────────────────────
#  Fenêtre principale
# ─────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dance Battle — Serveur Arbitre")
        self.resize(1100, 700)
        self.setStyleSheet(STYLESHEET)

        self._thread = None

        self._build_ui()
        self._connect_signals()

        # Rafraîchissement périodique de la table (au cas où)
        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh_table)
        self._timer.start(800)

    # ── Construction de l'interface ───────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(10)
        root.setContentsMargins(16, 12, 16, 12)

        # En-tête
        hdr = QHBoxLayout()
        vbl = QVBoxLayout()
        t = QLabel("⚔️  Dance Battle Server")
        t.setObjectName("lbl_title")
        s = QLabel("Serveur arbitre HTTP — contrôle des robots et des scores")
        s.setObjectName("lbl_sub")
        vbl.addWidget(t)
        vbl.addWidget(s)
        hdr.addLayout(vbl)
        hdr.addStretch()

        self.lbl_dot  = QLabel("●")
        self.lbl_dot.setStyleSheet(f"font-size:16px; color:{TEXT_MUTED};")
        self.lbl_srv  = QLabel("Serveur arrêté")
        self.lbl_srv.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px;")
        hdr.addWidget(self.lbl_dot)
        hdr.addWidget(self.lbl_srv)
        root.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{BORDER};")
        root.addWidget(sep)

        # Barre de contrôle
        ctrl = QGroupBox("Contrôles")
        cl = QHBoxLayout(ctrl)
        cl.setSpacing(10)

        self.btn_start  = QPushButton("▶  Démarrer serveur (port 8080)")
        self.btn_stop   = QPushButton("■  Arrêter")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setEnabled(False)
        self.btn_battle = QPushButton("📂  Charger .battle")
        self.lbl_battle = QLabel("Aucun fichier chargé")
        self.lbl_battle.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px;")

        cl.addWidget(self.btn_start)
        cl.addWidget(self.btn_stop)
        vsep = QFrame()
        vsep.setFrameShape(QFrame.VLine)
        vsep.setStyleSheet(f"color:{BORDER};")
        cl.addWidget(vsep)
        cl.addWidget(self.btn_battle)
        cl.addWidget(self.lbl_battle)
        cl.addStretch()
        root.addWidget(ctrl)

        # Contenu principal (splitter)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)

        # Panneau gauche — Robots
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        robots_grp = QGroupBox("Robots connectés")
        rl = QVBoxLayout(robots_grp)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["🤖 Robot ID", "📊 Score", "👣 Pas", "🏆 Rang"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        rl.addWidget(self.table)

        stats = QHBoxLayout()
        self.lbl_count = QLabel("0 robot(s)")
        self.lbl_count.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px;")
        self.lbl_mvs = QLabel("MVS: —")
        self.lbl_mvs.setStyleSheet(f"color:{ACCENT}; font-size:11px; font-weight:bold;")
        stats.addWidget(self.lbl_count)
        stats.addStretch()
        stats.addWidget(self.lbl_mvs)
        rl.addLayout(stats)
        ll.addWidget(robots_grp)
        splitter.addWidget(left)

        # Panneau droit — Logs
        right = QWidget()
        rrl = QVBoxLayout(right)
        rrl.setContentsMargins(0, 0, 0, 0)
        logs_grp = QGroupBox("Journal des événements")
        lgl = QVBoxLayout(logs_grp)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QTextEdit.NoWrap)
        lgl.addWidget(self.log_view)

        btn_row = QHBoxLayout()
        self.btn_clear = QPushButton("🗑  Effacer les logs")
        self.btn_clear.setObjectName("btn_clear")
        btn_row.addStretch()
        btn_row.addWidget(self.btn_clear)
        lgl.addLayout(btn_row)

        rrl.addWidget(logs_grp)
        splitter.addWidget(right)

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

    # ── Démarrage / arrêt du serveur ─────────────────────────────────────────

    def _on_start(self):
        if self._thread and self._thread.isRunning():
            return
        self._thread = ServerThread(port=8080)
        self._thread.started_ok.connect(self._on_started)
        self._thread.stopped.connect(self._on_stopped)
        self._thread.error.connect(self._on_error)
        self._thread.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def _on_stop(self):
        if self._thread:
            self._thread.stop()
            self._thread.wait(3000)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _on_started(self, port):
        self.lbl_dot.setStyleSheet(f"font-size:16px; color:{SUCCESS};")
        self.lbl_srv.setText(f"Serveur actif — port {port}")
        self.lbl_srv.setStyleSheet(f"color:{SUCCESS}; font-size:12px;")
        self.statusBar().showMessage(f"✅ Serveur HTTP démarré sur le port {port}")
        self._append_log(f"Serveur démarré sur le port {port}", "success")

    def _on_stopped(self):
        self.lbl_dot.setStyleSheet(f"font-size:16px; color:{TEXT_MUTED};")
        self.lbl_srv.setText("Serveur arrêté")
        self.lbl_srv.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px;")
        self.statusBar().showMessage("Serveur arrêté.")
        self._append_log("Serveur arrêté.", "warning")

    def _on_error(self, msg):
        self._append_log(f"ERREUR : {msg}", "error")
        self.statusBar().showMessage(f"Erreur : {msg}")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    # ── Chargement du fichier .battle ─────────────────────────────────────────

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
            mvs = rules.get("mvs", 10)
            self.lbl_mvs.setText(f"MVS: {mvs} mouvements")
            self.statusBar().showMessage(f"Règles chargées depuis {path}")
        except Exception as e:
            self._append_log(f"Erreur chargement .battle : {e}", "error")

    # ── Table des robots ──────────────────────────────────────────────────────

    def _refresh_table(self):
        import threading as _t
        with srv._lock:
            snapshot = dict(srv.robots)

        nb = len(snapshot)
        self.lbl_count.setText(f"{nb} robot(s) connecté(s)")
        sorted_robots = sorted(snapshot.items(), key=lambda x: x[1]['score'], reverse=True)
        self.table.setRowCount(nb)

        medals = ["🥇", "🥈", "🥉"]
        for i, (rid, data) in enumerate(sorted_robots):
            score = data['score']
            steps = data['steps']
            rang  = medals[i] if i < 3 else f"#{i+1}"
            items = [
                QTableWidgetItem(rid),
                QTableWidgetItem(str(score)),
                QTableWidgetItem(str(steps)),
                QTableWidgetItem(rang),
            ]
            for ci, item in enumerate(items):
                item.setTextAlignment(Qt.AlignCenter)
                if ci == 1:
                    item.setForeground(QColor(SUCCESS if score >= 0 else ACCENT2))
                if i == 0 and nb > 1:
                    item.setBackground(QColor("#1e2f1e"))
                self.table.setItem(i, ci, item)

    # ── Journal ───────────────────────────────────────────────────────────────

    def _append_log(self, message, level="info"):
        color = LOG_COLORS.get(level, "#aaaacc")
        ts    = datetime.now().strftime("%H:%M:%S")
        html  = (
            f'<span style="color:#555577;">[{ts}]</span> '
            f'<span style="color:{color};">{message}</span><br>'
        )
        self.log_view.moveCursor(self.log_view.textCursor().End)
        self.log_view.insertHtml(html)
        self.log_view.moveCursor(self.log_view.textCursor().End)

    def closeEvent(self, event):
        self._on_stop()
        event.accept()


# ─────────────────────────────────────────────────────────────────────────────
#  Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window,          QColor(DARK_BG))
    palette.setColor(QPalette.WindowText,      QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.Base,            QColor("#12141f"))
    palette.setColor(QPalette.AlternateBase,   QColor(PANEL_BG))
    palette.setColor(QPalette.Text,            QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.Button,          QColor(PANEL_BG))
    palette.setColor(QPalette.ButtonText,      QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.Highlight,       QColor(ACCENT))
    palette.setColor(QPalette.HighlightedText, QColor("white"))
    app.setPalette(palette)

    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
