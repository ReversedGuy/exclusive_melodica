#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from functools import partial

from PySide6 import QtGui, QtCore, QtWidgets
from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QPixmap, QPainter, QFont, QColor, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QLabel, QTreeView, QFileSystemModel, QListWidgetItem, QSplitter, QPushButton,
    QSlider, QStyle, QComboBox, QStatusBar
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

MUSIC_DIR = Path.home() / "Music"
SUPPORTED_EXTS = (".mp3", ".wav", ".flac", ".ogg", ".m4a")  # basic set


# ---------- Theme palettes (material-inspired minimal palettes) ----------
THEMES = {
    "Deep Purple / Pink (default)": {
        "background": "#1f1326",
        "surface": "#2b1b33",
        "text": "#F2E7FE",
        "accent": "#ff4081",  # pink
    },
    "Indigo / Blue": {
        "background": "#0f1724",
        "surface": "#142033",
        "text": "#EAF2FF",
        "accent": "#3f51b5",
    },
    "Teal / Amber": {
        "background": "#062827",
        "surface": "#083638",
        "text": "#E8FFF7",
        "accent": "#ffb300",
    },
    "Pink / Purple": {
        "background": "#251321",
        "surface": "#331a2a",
        "text": "#FFF1FB",
        "accent": "#e91e63",
    },
    "Gray / Cyan": {
        "background": "#0b0b0d",
        "surface": "#121315",
        "text": "#E6EEF3",
        "accent": "#00bcd4",
    },
}


# ---------- Utilities ----------
def format_ms(ms: int):
    """Return mm:ss for milliseconds (safety for -1)."""
    if ms < 0:
        return "--:--"
    s = int(ms / 1000)
    m = s // 60
    s = s % 60
    return f"{m:02d}:{s:02d}"


def make_letter_pixmap(letter: str, size: int, bg_color: QColor, text_color: QColor):
    """Create a square rounded pixmap with a centered letter."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
    radius = int(size * 0.14)
    painter.setBrush(bg_color)
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(0, 0, size, size, radius, radius)

    # Draw letter
    font = QFont()
    font.setBold(True)
    # size letter to take many pixels
    font.setPointSize(int(size * 0.45))
    painter.setFont(font)
    painter.setPen(text_color)
    rect = pix.rect()
    painter.drawText(rect, Qt.AlignCenter, letter.upper())
    painter.end()
    return pix


# ---------- Main Window ----------
class MusicPlayerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Minimal Music Browser")
        self.resize(1000, 600)

        # Central widget layout
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)

        # Top controls: theme selector
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        self.theme_combo = QComboBox()
        for name in THEMES.keys():
            self.theme_combo.addItem(name)
        self.theme_combo.setCurrentIndex(0)
        self.theme_combo.currentTextChanged.connect(self.apply_theme)
        top_bar.addWidget(QLabel("Theme:"))
        top_bar.addWidget(self.theme_combo)
        layout.addLayout(top_bar)

        # Main split: file tree (left) and list + player (right)
        splitter = QSplitter()
        splitter.setHandleWidth(6)
        layout.addWidget(splitter)

        # Left: directory tree
        self.model = QFileSystemModel()
        self.model.setRootPath(str(MUSIC_DIR if MUSIC_DIR.exists() else Path.home()))
        self.model.setNameFilters(["*"])
        self.model.setNameFilterDisables(False)
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(str(MUSIC_DIR if MUSIC_DIR.exists() else Path.home())))
        # hide columns other than name
        for c in range(1, self.model.columnCount()):
            self.tree.hideColumn(c)
        self.tree.setHeaderHidden(True)
        self.tree.clicked.connect(self.on_dir_clicked)
        splitter.addWidget(self.tree)
        self.tree.setMinimumWidth(220)

        # Right: vertical area with song list and player
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(6, 6, 6, 6)

        # Current playlist / directory title + cover art
        header = QHBoxLayout()
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(64, 64)
        header.addWidget(self.cover_label)

        self.playlist_title = QLabel("Select a folder on the left")
        self.playlist_title.setStyleSheet("font-weight:600; font-size:16px;")
        header.addWidget(self.playlist_title)
        header.addStretch()
        right_layout.addLayout(header)

        # Song list
        self.song_list = QListWidget()
        self.song_list.itemClicked.connect(self.on_song_clicked)
        right_layout.addWidget(self.song_list)

        # Player controls
        controls = QHBoxLayout()

        self.prev_btn = QPushButton()
        self.prev_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipBackward))
        self.prev_btn.clicked.connect(self.prev_track)
        controls.addWidget(self.prev_btn)

        self.play_btn = QPushButton()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_btn.clicked.connect(self.play_pause)
        controls.addWidget(self.play_btn)

        self.stop_btn = QPushButton()
        self.stop_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_btn.clicked.connect(self.stop)
        controls.addWidget(self.stop_btn)

        self.next_btn = QPushButton()
        self.next_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self.next_btn.clicked.connect(self.next_track)
        controls.addWidget(self.next_btn)

        controls.addStretch()

        self.shuffle_btn = QPushButton("Shuffle")
        self.shuffle_btn.setCheckable(True)
        controls.addWidget(self.shuffle_btn)

        self.repeat_btn = QPushButton("Repeat")
        self.repeat_btn.setCheckable(True)
        controls.addWidget(self.repeat_btn)

        right_layout.addLayout(controls)

        # Seeker + time labels
        seek_layout = QHBoxLayout()
        self.time_label = QLabel("00:00")
        self.time_label.setFixedWidth(60)
        seek_layout.addWidget(self.time_label)

        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderMoved.connect(self.on_seek_slider_moved)
        self.seek_slider.sliderPressed.connect(self._seeker_pressed)
        self.seek_slider.sliderReleased.connect(self._seeker_released)
        seek_layout.addWidget(self.seek_slider)

        self.duration_label = QLabel("00:00")
        self.duration_label.setFixedWidth(60)
        seek_layout.addWidget(self.duration_label)
        right_layout.addLayout(seek_layout)

        # Volume and small status
        bottom_row = QHBoxLayout()
        bottom_row.addWidget(QLabel("Volume"))
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(70)
        self.vol_slider.setFixedWidth(120)
        self.vol_slider.valueChanged.connect(self.on_volume_changed)
        bottom_row.addWidget(self.vol_slider)
        bottom_row.addStretch()
        right_layout.addLayout(bottom_row)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(1, 1)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # Setup Media player
        self.player = QMediaPlayer()
        self.audio_out = QAudioOutput()
        self.player.setAudioOutput(self.audio_out)
        self.audio_out.setVolume(self.vol_slider.value() / 100.0)
        # signals
        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        self.player.playbackStateChanged.connect(self.on_playback_state_changed)
        self.player.sourceChanged.connect(lambda src: None)

        # internal playlist handling
        self.current_playlist = []  # list of file paths
        self.current_index = -1
        self.is_seeking = False

        # Periodic timer to update seeker if not using positionChanged reliably
        self.ui_timer = QTimer()
        self.ui_timer.setInterval(500)
        self.ui_timer.timeout.connect(self._periodic_update)
        self.ui_timer.start()

        # apply default theme
        self.apply_theme(self.theme_combo.currentText())

        # initial directory
        if MUSIC_DIR.exists():
            self.tree.setRootIndex(self.model.index(str(MUSIC_DIR)))
        else:
            self.tree.setRootIndex(self.model.index(str(Path.home())))

    # ---------------- UI behavior ----------------
    def apply_theme(self, theme_name):
        p = THEMES.get(theme_name, list(THEMES.values())[0])
        bg = p["background"]
        surface = p["surface"]
        text = p["text"]
        accent = p["accent"]
        # Apply a basic stylesheet using these colors. Minimal but effective.
        style = f"""
            QMainWindow {{
                background-color: {bg};
                color: {text};
            }}
            QWidget {{
                background-color: {surface};
                color: {text};
                selection-background-color: {accent};
            }}
            QListWidget {{
                background-color: {surface};
                border: 1px solid rgba(255,255,255,0.04);
            }}
            QTreeView {{
                background-color: {surface};
                border: none;
            }}
            QPushButton {{
                background-color: rgba(255,255,255,0.02);
                border: none;
                padding: 6px;
                border-radius: 6px;
            }}
            QPushButton:checked {{
                background-color: {accent};
                color: #fff;
            }}
            QSlider::groove:horizontal {{
                height: 8px;
                background: rgba(255,255,255,0.06);
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                width: 14px;
                background: {accent};
                margin: -4px 0;
                border-radius: 7px;
            }}
            QLabel {{
                color: {text};
            }}
            QComboBox {{
                background-color: rgba(255,255,255,0.02);
                padding: 4px;
                border-radius: 6px;
            }}
        """
        self.setStyleSheet(style)
        # update cover accent color (we'll pass accent color where needed)
        self._accent_color = QColor(accent)
        # refresh current cover
        self._update_cover_display()

    def on_dir_clicked(self, index):
        # when a directory is clicked, list its mp3s
        path = Path(self.model.filePath(index))
        if path.is_file():
            # if file clicked, go to its parent dir
            path = path.parent
        self.load_directory(path)

    def load_directory(self, path: Path):
        self.playlist_title.setText(str(path))
        self.song_list.clear()
        files = []
        for p in sorted(path.iterdir()):
            if p.suffix.lower() in SUPPORTED_EXTS and p.is_file():
                files.append(p)
        if not files:
            self.song_list.addItem("(no supported audio files found)")
            self.current_playlist = []
            self.current_index = -1
            self.status.showMessage("No audio files found in the folder.", 5000)
            self._update_cover_display()
            return

        for f in files:
            item = QListWidgetItem(f.name)
            item.setData(Qt.UserRole, str(f))
            letter = f.name[0].upper() if f.name else "?"
            icon_pixmap = make_letter_pixmap(letter, 48, self._accent_color, QColor("#ffffff"))
            item.setIcon(QtGui.QIcon(icon_pixmap))
            self.song_list.addItem(item)

        self.current_playlist = [str(f) for f in files]
        self.current_index = 0
        # select first item
        self.song_list.setCurrentRow(0)
        self._update_cover_display()
        # Autoplay first track? We'll not autoplay; wait for double-click or play pressed.
        self.status.showMessage(f"Loaded {len(files)} tracks.", 3000)

    def on_song_clicked(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)
        if not path:
            return
        try:
            idx = self.current_playlist.index(path)
        except ValueError:
            # not in current playlist (shouldn't happen)
            return
        self.play_at_index(idx)

    # ---------------- Playback control ----------------
    def play_at_index(self, idx: int):
        if idx < 0 or idx >= len(self.current_playlist):
            return
        self.current_index = idx
        file_path = self.current_playlist[idx]
        url = QUrl.fromLocalFile(file_path)
        self.player.setSource(url)
        self.player.play()
        self._update_cover_display()
        self.song_list.setCurrentRow(idx)
        self.status.showMessage(f"Playing: {Path(file_path).name}")

    def play_pause(self):
        state = self.player.playbackState()
        if state == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            # if nothing loaded, try to play first from playlist
            if not self.player.source().isLocalFile():
                if self.current_playlist:
                    self.play_at_index(self.current_index if self.current_index >= 0 else 0)
                else:
                    self.status.showMessage("No track selected.", 3000)
                    return
            else:
                self.player.play()

    def stop(self):
        self.player.stop()

    def prev_track(self):
        if not self.current_playlist:
            return
        new_idx = self.current_index - 1
        if new_idx < 0:
            if self.repeat_btn.isChecked():
                new_idx = len(self.current_playlist) - 1
            else:
                new_idx = 0
        self.play_at_index(new_idx)

    def next_track(self):
        if not self.current_playlist:
            return
        if self.shuffle_btn.isChecked():
            import random
            new_idx = random.randrange(len(self.current_playlist))
        else:
            new_idx = self.current_index + 1
            if new_idx >= len(self.current_playlist):
                if self.repeat_btn.isChecked():
                    new_idx = 0
                else:
                    new_idx = len(self.current_playlist) - 1
        self.play_at_index(new_idx)

    def on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def on_volume_changed(self, value):
        self.audio_out.setVolume(value / 100.0)

    # ---------------- Position / seeker ----------------
    def on_position_changed(self, pos):
        if self.is_seeking:
            return
        duration = self.player.duration()
        if duration > 0:
            val = int((pos / duration) * 1000)
            self.seek_slider.setValue(val)
        self.time_label.setText(format_ms(pos))

    def on_duration_changed(self, duration):
        self.duration_label.setText(format_ms(duration))

    def on_seek_slider_moved(self, value):
        # user is dragging; show tentative time
        duration = self.player.duration()
        if duration > 0:
            ms = int((value / 1000) * duration)
            self.time_label.setText(format_ms(ms))

    def _seeker_pressed(self):
        self.is_seeking = True

    def _seeker_released(self):
        # perform seek
        value = self.seek_slider.value()
        duration = self.player.duration()
        if duration > 0:
            ms = int((value / 1000) * duration)
            self.player.setPosition(ms)
        self.is_seeking = False

    def _periodic_update(self):
        # keep time label accurate if no signals
        if not self.is_seeking:
            pos = self.player.position()
            dur = self.player.duration()
            if dur > 0:
                self.seek_slider.setValue(int((pos / dur) * 1000))
            self.time_label.setText(format_ms(pos))
            self.duration_label.setText(format_ms(dur))

    # ---------------- Cover (letter) display ----------------
    def _update_cover_display(self):
        # If a track is selected display its first letter; else show folder letter / placeholder
        accent = getattr(self, "_accent_color", QColor(THEMES["Deep Purple / Pink (default)"]["accent"]))
        text_color = QColor("#ffffff")
        size = 64

        if self.current_playlist and 0 <= self.current_index < len(self.current_playlist):
            name = Path(self.current_playlist[self.current_index]).stem
        else:
            # try to display folder name
            title = self.playlist_title.text()
            if title:
                name = Path(title).name if title != "Select a folder on the left" else "M"
            else:
                name = "M"
        letter = (name[0] if name else "?").upper()
        pix = make_letter_pixmap(letter, size, accent, text_color)
        self.cover_label.setPixmap(pix)

    # ---------------- track end handling ----------------
    # (QMediaPlayer in Qt6 may emit position/duration and we can detect end by comparing)
    # We'll use a timer to detect near-end and auto-advance.
    def _detect_track_end_and_advance(self):
        if self.player.duration() <= 0:
            return
        if self.player.position() >= max(0, self.player.duration() - 200):  # in ms near end
            # if playing and not repeating one, move next
            if self.player.playbackState() == QMediaPlayer.PlayingState:
                # small delay to avoid repeated triggers
                self.next_track()

    # Not used directly but kept for extension
    # ---------------- cleanup ----------------
    def closeEvent(self, event):
        self.player.stop()
        super().closeEvent(event)


# ---------- Run ----------
def main():
    app = QApplication(sys.argv)
    # set app icon (optional)
    try:
        app.setWindowIcon(QIcon.fromTheme("media-playback-start"))
    except Exception:
        pass

    win = MusicPlayerWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
