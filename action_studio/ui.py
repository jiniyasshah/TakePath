"""TakePath V10.2: Windows action recording, editing and retakes."""
from __future__ import annotations

import base64
import copy
import ctypes
from dataclasses import replace
import io
import os
from pathlib import Path
import sys
import time
import uuid

from PySide6.QtCore import QByteArray, QBuffer, QEvent, QIODevice, QPoint, QPointF, QRect, QRectF, QSize, QSettings, QSignalBlocker, Qt, QTimer, Signal, QFileInfo, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QAction, QColor, QDoubleValidator, QFont, QGuiApplication, QKeySequence, QPainter, QPainterPath, QPen, QPixmap, QImage, QShortcut, QIcon
from PySide6.QtWidgets import (
    QAbstractButton, QAbstractItemView, QAbstractSpinBox, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFileIconProvider, QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton,
    QScrollArea, QScrollBar, QSpinBox, QSplitter, QStackedWidget, QSystemTrayIcon, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget,
)
from . import __version__
from .retakes import RetakeHistory
from .core import Action, Project, interpolate_path, load_project, save_project, remove_actions, reorder_actions, format_replay_step, MOUSE_SPEED_FACTORS, ACTION_MOUSE_SPEED_MODES, ACTION_TYPING_SPEED_MODES, TYPING_SPEED_FACTORS, effective_mouse_speed, effective_typing_speed
from .recorder import Recorder, activate_target_window, center_cursor, foreground, title_of, virtual_screen, window_rect
from .playback import Player
from .secure_store import WindowsCredentialStore, CredentialError, validate_password, valid_reference, credential_store
from .portable_secrets import encrypt_secret_bundle, decrypt_secret_bundle, PortableSecretError
from .targets import open_windows, usable_window, screen_entries, window_menu_label
from .platform_api import (foreground as platform_foreground, window_pid, is_ours as platform_is_ours,
                           activate_target_window as platform_activate, center_cursor as platform_center,
                           supported as platform_supported)
from PySide6.QtSvg import QSvgRenderer

INK = '#EDF0F7'
MUTED = '#9DA6B8'
ACCENT = '#7697FF'
BG = '#0B0D12'
SURFACE = '#141720'

CSS = """
* { font-family: 'Segoe UI'; }
QWidget { background: #0B0D12; color: #EDF0F7; font-size: 12px; }
QLabel { background: transparent; }
QMainWindow, QDialog { background: #0B0D12; }
QFrame#dockBody { background: #12141C; border: 1px solid #2B303D; border-radius: 23px; }
/* Separate hit-test surfaces meet at one seam, without two rounded inner ends. */
QFrame#dockBodyJoinedLeft { background: #12141C; border: 1px solid #2B303D;
  border-right: 0px; border-top-left-radius: 23px; border-bottom-left-radius: 23px;
  border-top-right-radius: 0px; border-bottom-right-radius: 0px; }
QFrame#dockBodyJoinedRight { background: #12141C; border: 1px solid #2B303D;
  border-left: 0px; border-top-left-radius: 0px; border-bottom-left-radius: 0px;
  border-top-right-radius: 23px; border-bottom-right-radius: 23px; }
QWidget#dockGripOverlay { background: transparent; }
QWidget#dockPage, QStackedWidget#dockStack { background: transparent; }
QWidget#propertyGroup, QWidget#inspectorHolder { background: transparent; }
QFrame#topBar { background: #10131A; border-bottom: 1px solid #252B37; }
QFrame#card { background: #121620; border: 1px solid #262D3B; border-radius: 13px; }
QFrame#soft { background: #191D28; border: 1px solid #2B3241; border-radius: 11px; }
QFrame#toolbar { background: #131720; border: 1px solid #2A303D; border-radius: 11px; }
QFrame#rail { background: #0E1118; border-right: 1px solid #252C37; }
QFrame#separator { background: #303541; border: none; }
QLabel#brand { font-size: 14px; font-weight: 700; }
QLabel#heading { font-size: 18px; font-weight: 650; }
QLabel#tiny { font-size: 10px; font-weight: 700; color: #8994A8; }
QLabel#muted { color: #9CA5B5; font-size: 11px; }
QLabel#clock { font-size: 15px; font-weight: 700; font-family: 'Consolas'; }
QLabel#recordClock { font-size: 17px; font-weight: 700; font-family: 'Consolas'; color: #FFFFFF; }
QLabel#recIndicator { color: #FF586E; font-weight: 750; letter-spacing: 1px; }
QPushButton { min-height: 32px; padding: 1px 12px; background: #1D2330;
  border: 1px solid #2B3443; border-radius: 9px; font-weight: 600; }
QPushButton:hover { background: #293241; border-color: #495970; }
QPushButton:pressed { background: #1C2633; }
QPushButton:disabled { color: #666F7E; background: #121720; border-color: #222936; }
QPushButton#primary { background: #6486FA; border-color: #6486FA; color: #FFFFFF; }
QPushButton#primary:hover { background: #7897FF; }
QPushButton#record { background: #F63E67; color: white; border-color: #F63E67; }
QPushButton#record:hover { background: #FF5678; }
QPushButton#outline { background: transparent; border: 1px solid #383A45; }
QPushButton#quiet { background: transparent; border: 1px solid transparent; color: #BFC1CD; }
QPushButton#quiet:hover { background: #252D3B; }
QPushButton#warning { background: #2B2028; border: 1px solid #452E3B; color: #FF8899; }
QPushButton#choice { background: #222431; border: 1px solid #373B4C; }
QPushButton#choice:checked { background: #303B5C; border-color: #7E98FF; }
QPushButton#dockButton { min-height: 42px; background: transparent; border: 1px solid transparent; border-radius: 11px;
  padding: 0px 11px; color: #E6E7F0; font-size: 12px; font-weight: 600; }
QPushButton#dockButton:hover { background: #252C38; }
QPushButton#dockRetake { color: #B7C4FF; font-weight: 600; background: transparent; border: 1px solid transparent; border-radius: 11px; min-height: 42px; padding: 0px 7px; }
QPushButton#dockRetake:hover { background: #252C38; border-color: #3B465B; }
QPushButton#dockButton[hasTarget="true"] { background: #1D222E; border-color: #333C4C; }
QPushButton#dockButton[hasTarget="true"]:hover { background: #273143; }
QLabel#targetName { font-size: 12px; font-weight: 650; background: transparent; }
QLabel#microLabel { background: transparent; font-size: 10px; font-weight: 600; color: #8790A3; }
QFrame#sectionStrip { background: #191D27; border: 1px solid #2A3040; border-radius: 11px; }
QLabel#actionTitle { font-size: 15px; font-weight: 700; background: transparent; }
QPushButton#modePill { background:#212634; border:1px solid #363F50; border-radius:9px; min-height:32px; }
QPushButton#modePill:hover { background:#303951; }

QPushButton#dockButton:checked { background: #253550; border-color: #50698D; }
QPushButton#dockIcon { min-height: 38px; max-height: 38px; min-width: 36px; max-width: 36px;
  background: transparent; border: 1px solid transparent; border-radius: 10px; padding: 0px; }
QPushButton#dockIcon:hover { background: #252D3A; }
QPushButton#dockIcon:checked { background: #273956; border-color: #4A628B; }
QPushButton#dockEdit { min-height: 38px; background: transparent; border: 1px solid transparent;
  border-radius: 10px; padding: 0px 9px; color: #E9EDFF; }
QPushButton#dockEdit:hover { background: #283141; border-color: #3C485B; }
QPushButton#recordGlyph { min-width:48px; max-width:48px; min-height:48px; max-height:48px;
  background: transparent; border: 0; padding: 0; }
QPushButton#replayOrb { min-width:48px; max-width:48px; min-height:48px; max-height:48px;
  background: #6486FA; border: 1px solid #7995FF; border-radius: 24px; padding: 0; }
QPushButton#replayOrb:hover { background: #7897FF; border-color: #9FB3FF; }
QPushButton#stopOrb { border: 0; border-radius: 23px; background: #F43C66;
 min-width: 46px; max-width: 46px; min-height: 46px; max-height: 46px; padding: 0; }
QPushButton#stopOrb:hover { background: #FF547A; }
QFrame#dockBodyJoinedRight QPushButton#dockIcon {
  min-width: 28px; max-width: 28px; min-height: 34px; max-height: 34px;
  padding: 0px; background: transparent; border: 1px solid transparent; border-radius: 9px;
}
QFrame#dockBodyJoinedRight QPushButton#dockIcon:hover { background: #252D3A; }
QFrame#dockBodyJoinedRight QPushButton#stopOrb {
  min-width: 42px; max-width: 42px; min-height: 42px; max-height: 42px;
  border-radius: 21px; padding: 0px; }
QPushButton#dockGripIcon {
  min-width: 34px; max-width: 34px; min-height: 42px; max-height: 42px;
  background: transparent; border: 1px solid transparent; border-radius: 9px; padding: 0px;
}
QPushButton#dockGripIcon:hover { background: #252D3A; }
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
  background: #1B202B; border: 1px solid #313A4A; border-radius: 9px;
  padding: 7px 10px; selection-background-color: #536EB1; }
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: #698EFF; }
QComboBox::drop-down { border: 0; width: 20px; }
QComboBox QAbstractItemView { background: #191E29; color: #F4F6FB; selection-background-color: #354B75; }
QTableWidget { background: #10151D; alternate-background-color: #151A24;
  selection-background-color: #2D3B5A; selection-color: #FFFFFF; border: 0;
  border-radius: 10px; gridline-color: #252631; }
QTableWidget::item { border-bottom: 1px solid #242938; padding: 7px 11px; }
QHeaderView::section { background: #171D28; color: #A4AEC1; border: none;
  border-bottom: 1px solid #343540; padding: 10px; font-size: 10px; font-weight: 750; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #10151D; width: 7px; }
QScrollBar::handle:vertical { background: #444654; border-radius: 3px; min-height: 25px; }
QSplitter::handle { background: #0D1118; }
QSplitter::handle:vertical { height: 6px; }
QMenu { background: #181D28; color: #F1F4FA; border: 1px solid #343D4C; border-radius: 11px; padding: 7px; }
QMenu::item { border-radius: 7px; padding: 9px 25px; }
QMenu::item:selected { background: #394762; }
QMenu::separator { height: 1px; background: #434350; margin: 5px 8px; }
QToolTip { color: #F5F7FC; background: #1C2533; border: 1px solid #39495B; padding: 6px; }
QCheckBox { spacing: 7px; }
QCheckBox::indicator { width: 15px; height: 15px; }
QPushButton#passwordReveal { background: #1C2430; border: 1px solid #344055;
    border-radius: 9px; padding: 0; min-width: 37px; min-height: 37px; }
QPushButton#passwordReveal:hover { background: #293548; border-color: #586B8D; }
QPushButton#passwordReveal:checked { background: #2B3950; border-color: #6B82AA; }

/* V9: one calm, grouped replay toolbar (no dark boxed labels). */
QFrame#replayToolbar { background: #151A24; border: 1px solid #293241; border-radius: 12px; }
QWidget#toolbarGroup, QWidget#toolbarContent { background: transparent; }
QLabel#toolbarCaption { color: #8D99AC; background: transparent;
  font-size: 10px; font-weight: 650; }
QLabel#toolbarEstimate { color: #D9E3F3; background: transparent;
  font-size: 12px; font-weight: 650; }
QFrame#toolbarDivider { background: #2B3545; border: none; }
QDoubleSpinBox#toolbarInput, QComboBox#toolbarInput {
  min-height: 34px; max-height: 34px; border-radius: 9px;
  background: #202632; border: 1px solid #343E50; padding: 0px 10px;
  color: #ECF2FB; }
QDoubleSpinBox#toolbarInput:hover, QComboBox#toolbarInput:hover { border-color: #596C8E; }
QDoubleSpinBox#toolbarInput:focus, QComboBox#toolbarInput:focus { border-color: #879CFF; }
QPushButton#toolbarApply { min-height: 36px; max-height: 36px; padding: 0px 11px;
  background: #273449; border: 1px solid #3C4C64; border-radius: 9px; color: #E2EBFF; }
QPushButton#toolbarApply:hover { background: #334462; border-color: #6482B5; }
QPushButton#toolbarToggle { min-height: 36px; max-height: 36px;
  background: #202632; border: 1px solid #343E50; border-radius: 9px;
  padding: 0px 11px; font-weight: 600; color: #B8C3D3; }
QPushButton#toolbarToggle:hover { background: #2C374A; }
QPushButton#toolbarToggle:checked { background: #2B3C56; border-color: #617DAC; color: #E7F0FF; }
QScrollArea#toolbarScroll { border: none; background: transparent; }
QScrollArea#toolbarScroll > QWidget > QWidget { background: transparent; }
QScrollBar:horizontal { background: #151A24; height: 6px; border: none; }
QScrollBar::handle:horizontal { background: #435069; border-radius: 3px; min-width: 24px; }

/* V9: stable gap entry with a dedicated unit label; no native spin-button clipping. */
QFrame#gapControl { background: #202632; border: 1px solid #344053; border-radius: 9px; }
QFrame#gapControl:hover { border-color: #51627B; }
QFrame#gapControl[editing="true"] { border-color: #7899FF; }
QLineEdit#gapText { background: transparent; color: #F0F4FC; border: none; border-radius: 0;
  padding: 0px; font-size: 12px; font-weight: 650; selection-background-color: #506C9F; }
QLineEdit#gapText:focus { border: none; background: transparent; }
QLabel#gapUnit { background: transparent; color: #A5AFBF; font-size: 11px; font-weight: 600; }
"""

# Compact, rendered vector icons instead of platform-dependent Unicode glyphs.
ICON_PATHS = {
 'grip':'<circle cx="9" cy="5" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="19" r="1"/>',
 'monitor':'<rect x="3" y="4" width="18" height="14" rx="2"/><path d="M8 21h8M12 18v3"/>',
 'window':'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18"/>',
 'chevron':'<path d="m6 9 6 6 6-6"/>',
 'clock':'<circle cx="12" cy="13" r="9"/><path d="M12 8v5l3 2M9 2h6"/>',
 'target':'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/><path d="M12 1v5M12 18v5M1 12h5M18 12h5"/>',
 'dots':'<circle cx="12" cy="5" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="12" cy="19" r="1.4"/>',
 'minus':'<path d="M5 12h14"/>',
 'close':'<path d="M5 5l14 14M19 5 5 19"/>',
 'pause':'<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>',
 'play':'<path d="m7 4 13 8-13 8z"/>',
 'stop':'<rect x="6" y="6" width="12" height="12" rx="2"/>',
 'edit':'<path d="M12 20h9M16.5 3.5a2 2 0 0 1 4 4L9 19l-5 1 1-5z"/>',
 'folder':'<path d="M3 7a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v9H3z"/>',
 'save':'<path d="M4 3h14l3 3v15H3V3zM7 3v7h10V3M7 21v-8h10v8"/>',
 'trash':'<path d="M4 7h16M9 7V4h6v3M7 7l1 14h8l1-14M10 11v6M14 11v6"/>',
 'retake':'<path d="M3 11a9 9 0 1 1 2.7 6.4"/><path d="M3 4v7h7"/>',
 'eye':'<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
 'eye-off':'<path d="M3 3l18 18"/><path d="M10.6 5.1A10.2 10.2 0 0 1 12 5c6.5 0 10 7 10 7a14 14 0 0 1-4 4.6M6.3 6.3C3.4 8.3 2 12 2 12s3.5 7 10 7a10.7 10.7 0 0 0 4.3-.9"/><path d="M10 10a3 3 0 0 0 4 4"/>',
 'plus':'<path d="M12 4v16M4 12h16"/>',
 'copy':'<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
 'cursor':'<path d="m4 3 15 9-7 1-4 7z"/>',
 'arrow-left':'<path d="m15 18-6-6 6-6M9 12h11"/>',
 'expand':'<path d="M9 3H4a1 1 0 0 0-1 1v5M15 3h5a1 1 0 0 1 1 1v5M3 15v5a1 1 0 0 0 1 1h5M21 15v5a1 1 0 0 1-1 1h-5"/>',
}

def password_reveal_button(field):
    """Explicit, local show/hide toggle; secrets stay masked by default.

    The toggle only changes a QLineEdit echo mode. It does not write the
    value to settings, disk, project JSON, clipboard, or logs.
    """
    button=QPushButton()
    button.setObjectName('passwordReveal')
    button.setCheckable(True)
    button.setFixedSize(37,37)
    button.setCursor(Qt.PointingHandCursor)
    def update(visible):
        field.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)
        button.setIcon(vector_icon('eye-off' if visible else 'eye','#C4CCE0',18))
        button.setIconSize(QSize(18,18))
        button.setToolTip('Hide password' if visible else 'Show password')
        button.setAccessibleName('Hide password' if visible else 'Show password')
    button.toggled.connect(update)
    update(False)
    return button


def app_icon():
    """Bundled Windows icon for taskbar, titlebar and notification area."""
    bundle = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
    icon_file = bundle / 'assets' / ('takepath.ico' if sys.platform=='win32' else 'takepath-icon.png')
    return QIcon(str(icon_file)) if icon_file.is_file() else vector_icon('cursor','#8BA5FF',32)


def vector_icon(name, color='#CED0DE', size=24):
    path = ICON_PATHS[name]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
           f'fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
           f'{path}</svg>').encode('utf-8')
    img = QPixmap(size, size)
    img.fill(Qt.transparent)
    renderer = QSvgRenderer(QByteArray(svg))
    painter = QPainter(img)
    renderer.render(painter)
    painter.end()
    return QIcon(img)

def icon_button(name, slot, tip='', role='dockIcon', color='#C9CBD8', size=19):
    w = QPushButton()
    w.setObjectName(role)
    w.setIcon(vector_icon(name, color))
    w.setIconSize(QSize(size,size))
    w.setToolTip(tip)
    w.setCursor(Qt.PointingHandCursor)
    w.clicked.connect(slot)
    return w



def V(parent=None, margins=(0, 0, 0, 0), spacing=10):
    layout = QVBoxLayout(parent)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return layout


def H(parent=None, margins=(0, 0, 0, 0), spacing=8):
    layout = QHBoxLayout(parent)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return layout


def L(text, role=None):
    widget = QLabel(text)
    if role:
        widget.setObjectName(role)
    return widget


def B(text, slot, role='quiet', tip=''):
    widget = QPushButton(text)
    widget.setObjectName(role)
    if tip:
        widget.setToolTip(tip)
    widget.clicked.connect(slot)
    return widget


def F(role='card'):
    widget = QFrame()
    widget.setObjectName(role)
    return widget


def spin(lo=0, hi=3600, val=0, suffix=''):
    w = QSpinBox()
    w.setRange(lo, hi)
    w.setValue(val)
    w.setSuffix(suffix)
    return w


def number(lo=0, hi=600, val=0.5, suffix=' s'):
    w = QDoubleSpinBox()
    w.setRange(lo, hi)
    w.setDecimals(2)
    w.setSingleStep(.05)
    w.setValue(val)
    w.setSuffix(suffix)
    return w


class _GapTextEdit(QLineEdit):
    """Numeric text entry with accessible arrow/wheel increments."""
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Up, Qt.Key_Down):
            self.parentWidget().nudge(0.10 if event.key() == Qt.Key_Up else -0.10)
            event.accept()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        # Don't accidentally alter timing while scrolling the action editor.
        if self.hasFocus():
            self.parentWidget().nudge(0.10 if event.angleDelta().y() > 0 else -0.10)
            event.accept()
        else:
            event.ignore()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.parentWidget()._focus_changed(True)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.parentWidget()._focus_changed(False)


class GapInput(QFrame):
    """Stable, editable seconds input that remains legible at Windows DPI scales.

    QDoubleSpinBox with NoButtons can render an empty edit area with some Qt
    styles/high-DPI setups. A validated QLineEdit and separate unit label keep
    the value visible and make numeric validation/commit rules explicit.
    """
    valueChanged = Signal(float)

    def __init__(self, value=0.8, minimum=0.0, maximum=3600.0, step=0.10, parent=None):
        super().__init__(parent)
        self.setObjectName('gapControl')
        self.setFixedHeight(38)
        self.setMinimumWidth(116)
        self._minimum, self._maximum, self._step = float(minimum), float(maximum), float(step)
        self._value = float(value)
        lay=H(self,(12,0,10,0),3)
        self.field=_GapTextEdit(self)
        self.field.setObjectName('gapText')
        self.field.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.field.setValidator(QDoubleValidator(self._minimum,self._maximum,2,self.field))
        self.field.setToolTip('Type a gap in seconds. Up / Down adjusts by 0.10 s.')
        self.field.setMinimumWidth(62)
        self.field.setText(f'{self._value:.2f}')
        self.field.editingFinished.connect(self._commit)
        lay.addWidget(self.field,1)
        unit=L('s','gapUnit')
        unit.setFixedWidth(10)
        lay.addWidget(unit)

    def _focus_changed(self, focused):
        self.setProperty('editing', 'true' if focused else 'false')
        self.style().unpolish(self)
        self.style().polish(self)

    def _commit(self):
        try:
            raw=float(self.field.text().strip())
        except (TypeError,ValueError):
            raw=self._value
        if not self._minimum <= raw <= self._maximum:
            raw=self._value
        self.setValue(raw)

    def nudge(self, amount):
        self._commit()
        self.setValue(self._value+amount)

    def value(self):
        self._commit()
        return self._value

    def setValue(self, value):
        try:
            parsed=float(value)
        except (TypeError,ValueError):
            parsed=self._value
        value=round(min(self._maximum,max(self._minimum,parsed)),2)
        changed=value != self._value
        self._value=value
        displayed=f'{value:.2f}'
        if self.field.text() != displayed:
            self.field.setText(displayed)
        if changed:
            self.valueChanged.emit(value)


def format_elapsed(secs):
    secs = max(0, int(secs))
    return f'{secs // 60:02}:{secs % 60:02}'


def get_window_preview(hwnd):
    """One small, local screenshot of the target window for coordinate editing.

    This is a still image, not a video. Only captures the visible rectangle of the
    selected window and clips it to the virtual desktop. Does not write to disk.
    """
    import mss
    x, y, w, h = window_rect(hwnd)
    sx, sy, sw, sh = virtual_screen()
    left, top = max(x, sx), max(y, sy)
    right, bottom = min(x + w, sx + sw), min(y + h, sy + sh)
    if right <= left or bottom <= top:
        raise ValueError('Selected window is outside the visible desktop')
    rect = {'left': left, 'top': top, 'width': right-left, 'height': bottom-top}
    with mss.mss() as capturer:
        shot = capturer.grab(rect)
    image = QImage(shot.bgra, shot.width, shot.height, QImage.Format_BGRA8888).copy()
    pixmap = QPixmap.fromImage(image).scaled(1700, 1050, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    output = QByteArray()
    buf = QBuffer(output)
    buf.open(QIODevice.WriteOnly)
    pixmap.save(buf, 'JPEG', 74)
    buf.close()
    return base64.b64encode(bytes(output)).decode('ascii'), [left, top, right-left, bottom-top]


def get_screen_preview(bounds=None):
    """Capture one still of the chosen monitor (or virtual desktop fallback)."""
    import mss
    left, top, width, height = bounds or virtual_screen()
    with mss.mss() as capturer:
        shot = capturer.grab({'left':left,'top':top,'width':width,'height':height})
    image = QImage(shot.bgra, shot.width, shot.height, QImage.Format_BGRA8888).copy()
    pix = QPixmap.fromImage(image).scaled(1700, 1050, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    output = QByteArray()
    buf = QBuffer(output)
    buf.open(QIODevice.WriteOnly)
    pix.save(buf, 'JPEG', 72)
    buf.close()
    return base64.b64encode(bytes(output)).decode('ascii'), [left,top,width,height]


class SceneCanvas(QWidget):
    """Full-window still preview, editable mouse targets, and motion path overlay."""
    picked = Signal(int)
    moved = Signal(int, int, int)

    def __init__(self, owner, parent=None):
        super().__init__(parent)
        self.owner = owner
        self.pixmap = QPixmap()
        self.selected_ids = set()
        self.drag_index = -1
        self.setMouseTracking(True)
        self.setMinimumSize(400, 210)
        self.setCursor(Qt.CrossCursor)
        self._image_rect = QRectF()
        self.setToolTip('Select a numbered click or drag a target to correct its position.')

    def update_project(self, selected_ids=()):
        self.selected_ids = set(selected_ids)
        encoded = self.owner.project.preview_jpeg
        self.pixmap = QPixmap()
        if encoded:
            try:
                if len(encoded) <= 10_000_000:
                    self.pixmap.loadFromData(base64.b64decode(encoded), 'JPEG')
            except Exception:
                pass
        self.update()

    def _bounds(self):
        return self.owner.project.preview_bounds if not self.pixmap.isNull() else self.owner.project.screen_bounds

    def _canvas_rect(self):
        _, _, w, h = self._bounds()
        if not self.pixmap.isNull():
            w, h = self.pixmap.width(), self.pixmap.height()
        w, h = max(1, w), max(1, h)
        available = self.rect().adjusted(25, 28, -25, -28)
        ratio = min(available.width() / w, available.height() / h)
        width, height = w * ratio, h * ratio
        return QRectF(available.center().x() - width/2, available.center().y()-height/2, width, height)

    def _at(self, x, y):
        bounds = self._bounds()
        rect = self._image_rect
        if rect.width() <= 0 or rect.height() <= 0:
            return QPoint(0, 0)
        return QPointF(rect.left() + (x-bounds[0]) / bounds[2] * rect.width(),
                       rect.top() + (y-bounds[1]) / bounds[3] * rect.height())

    def _screen_pos(self, local):
        rect = self._image_rect
        bx, by, bw, bh = self._bounds()
        px = max(0.0, min(1.0, (local.x() - rect.left()) / max(1, rect.width())))
        py = max(0.0, min(1.0, (local.y() - rect.top()) / max(1, rect.height())))
        return round(bx+px*bw), round(by+py*bh)

    def _endpoint(self, a):
        return (a.end_x, a.end_y) if a.kind == 'drag' else (a.x, a.y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor('#10151E'))
        self._image_rect = self._canvas_rect()
        r = self._image_rect
        painter.setPen(QPen(QColor('#364052'), 1))
        painter.setBrush(QColor('#19202A'))
        painter.drawRoundedRect(r.adjusted(-1,-1,1,1), 7, 7)
        if not self.pixmap.isNull():
            painter.save()
            painter.setClipRect(r)
            painter.drawPixmap(r, self.pixmap, QRectF(self.pixmap.rect()))
            painter.restore()
        else:
            painter.setPen(QPen(QColor('#252F3D'), 1, Qt.DotLine))
            for i in range(1, 10):
                x = r.left() + r.width() * i/10
                painter.drawLine(QPoint(round(x), round(r.top())), QPoint(round(x), round(r.bottom())))
            for i in range(1, 6):
                y = r.top() + r.height() * i/6
                painter.drawLine(QPoint(round(r.left()), round(y)), QPoint(round(r.right()), round(y)))
            painter.setPen(QColor('#8A98AD'))
            painter.drawText(r, Qt.AlignCenter, 'No screen snapshot available\nAction targets are still editable on this coordinate map')
        selected = [(i, a) for i, a in enumerate(self.owner.project.actions) if a.id in self.selected_ids]
        for i, a in selected:
            if a.kind not in ('click', 'drag', 'scroll'):
                continue
            finish = self._endpoint(a)
            if len(a.raw_path) >= 2:
                start = (round(a.raw_path[0][0]), round(a.raw_path[0][1]))
            else:
                start = (self._bounds()[0] + self._bounds()[2]//2,
                         self._bounds()[1] + self._bounds()[3]//2)
            path = QPainterPath(self._at(*start))
            if self.owner.project.cursor_mode == 'original' and len(a.raw_path) >= 2:
                for x, y, _ in a.raw_path[1:]:
                    path.lineTo(self._at(x,y))
            else:
                for x,y in interpolate_path(start, finish, 32):
                    path.lineTo(self._at(x,y))
            painter.setPen(QPen(QColor(147,156,255,220), 2.5, Qt.SolidLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)
        actions = self.owner.project.actions
        pointer = [(i, a) for i,a in enumerate(actions) if a.kind in ('click','drag','scroll')]
        for i,a in pointer[:180]:
            pos = self._at(*self._endpoint(a))
            active = a.id in self.selected_ids
            radius = 10 if active else 7
            painter.setPen(QPen(QColor('#DDE1FF') if active else QColor('#9AA7B9'), 1.2))
            painter.setBrush(QColor('#8897FF') if active else QColor(26,33,45,205))
            painter.drawEllipse(pos, radius, radius)
            if active:
                painter.setPen(QColor('#101424'))
                painter.setFont(QFont('Segoe UI', 8, QFont.Bold))
                painter.drawText(QRectF(pos.x()-11,pos.y()-9,22,18), Qt.AlignCenter, str(i+1))
        painter.setPen(QColor('#9DA9B8'))
        painter.setFont(QFont('Segoe UI', 9))
        painter.drawText(21, 22, 'VISUAL ACTION MAP')
        if not self.pixmap.isNull():
            painter.drawText(21,self.height()-13,'Final-frame screenshot · Actions may have changed the screen earlier')
        else:
            painter.drawText(21,self.height()-13,'Spatial preview · Screen coordinates')

    def _hit(self, pos):
        for i in reversed(range(len(self.owner.project.actions))):
            a=self.owner.project.actions[i]
            if a.kind not in ('click','drag','scroll'):
                continue
            marker=self._at(*self._endpoint(a))
            if (marker.x()-pos.x())**2+(marker.y()-pos.y())**2 < 17**2:
                return i
        return -1

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        i=self._hit(event.position())
        if i >= 0:
            self.picked.emit(i)
            self.drag_index=i
        else:
            self.drag_index=-1
            # A blank spatial preview should not leave an unrelated action
            # selected in the timeline.
            self.owner.clear_action_selection()

    def mouseMoveEvent(self,event):
        if self.drag_index >= 0 and event.buttons() & Qt.LeftButton:
            if self._image_rect.contains(event.position()):
                x,y=self._screen_pos(event.position())
                self.moved.emit(self.drag_index, x, y)

    def mouseReleaseEvent(self,event):
        self.drag_index=-1


class RecordOrb(QPushButton):
    """A pixel-centered, antialiased record glyph (never a font-dependent bullet)."""
    def __init__(self, slot, parent=None):
        super().__init__(parent)
        self.setObjectName('recordGlyph')
        self.setFixedSize(48, 48)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip('Start recording · F8 stops')
        self.clicked.connect(slot)
        self._hovered = False

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor('#FF5478') if self._hovered else QColor('#F43F67'))
        painter.drawEllipse(QRectF(0.8, 0.8, 46.4, 46.4))
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(QRectF(17.0, 17.0, 14.0, 14.0))
        painter.end()


class DockDragHandle(QPushButton):
    """A real drag affordance; keeps dragging from accidentally pressing controls."""
    def __init__(self, dock):
        super().__init__()
        self.dock = dock
        self.setObjectName('dockIcon')
        self.setIcon(vector_icon('grip','#777887'))
        self.setIconSize(QSize(18,18))
        self.setToolTip('Drag to move the recording bar')
        self.setCursor(Qt.SizeAllCursor)
        self.offset = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if hasattr(self.dock,'_dock_geometry_animation'):
                self.dock._dock_geometry_animation.stop()
            self.offset = event.globalPosition().toPoint() - self.dock.pos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.offset is not None and event.buttons() & Qt.LeftButton:
            self.dock.move(event.globalPosition().toPoint() - self.offset)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.offset is not None:
            self.dock.owner.settings.setValue('dock_location', 'custom')
            self.dock.owner.settings.setValue('dock_x', self.dock.x())
            self.dock.owner.settings.setValue('dock_y', self.dock.y())
        self.offset = None
        super().mouseReleaseEvent(event)


class DockControlIsland(QWidget):
    """Separate interactive window above the click-through recording status.

    Its own HWND is intentionally NOT mouse-transparent. The status dock's
    HWND can forward clicks to Brave while Pause/Stop and expand remain
    interactive. The drag grip now has a separate window at the far left.
    Windows WS_EX_NOACTIVATE avoids stealing focus.
    """
    def __init__(self, dock):
        flags=Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        if sys.platform == 'win32':
            flags |= Qt.WindowDoesNotAcceptFocus
        super().__init__(None, flags)
        self.dock=dock
        self.setObjectName('dockControlIsland')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        # Keep the independent clickable HWND; eliminate its outer gap.
        self.setFixedSize(116, 64)
        layout=V(self,(0,0,0,0),0)
        frame=F('dockBodyJoinedRight')
        self.frame=frame
        layout.addWidget(frame)
        actions=H(frame,(5,1,5,1),2)
        # The drag control lives at the far left of the entire active dock.
        self.pause=icon_button('pause',dock.owner.toggle_pause,'Pause or resume (F7)')
        self.pause.setAccessibleName('Pause or resume recording or replay')
        self.pause.setFixedSize(28,34)
        actions.addWidget(self.pause)
        self.stop=icon_button('stop',dock.owner.stop,'Stop recording or replay (F8)',
                              'stopOrb','#FFFFFF',20)
        self.stop.setAccessibleName('Stop recording or replay')
        self.stop.setFixedSize(42,42)
        actions.addWidget(self.stop)
        self.compact=icon_button('minus',lambda:dock.set_compact_mode(not dock.compact_active),
                                  'Toggle compact recording dock')
        self.compact.setAccessibleName('Toggle compact dock')
        self.compact.setFixedSize(28,34)
        actions.addWidget(self.compact)
        self._excluded_from_capture=False

    def showEvent(self,event):
        super().showEvent(event)
        if sys.platform != 'win32':
            return
        try:
            hwnd=int(self.winId())
            user32=ctypes.windll.user32
            current=user32.GetWindowLongW(hwnd,-20)
            user32.SetWindowLongW(hwnd,-20,(current | 0x08000000) & ~0x00000020)
            # HWND_TOPMOST, SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE |
            # SWP_NOOWNERZORDER | SWP_FRAMECHANGED.
            user32.SetWindowPos(hwnd,-1,0,0,0,0,
                                0x0010|0x0002|0x0001|0x0200|0x0020)
            if not self._excluded_from_capture:
                self._excluded_from_capture=bool(user32.SetWindowDisplayAffinity(hwnd,0x11))
        except Exception:
            pass

    def update_controls(self, paused, compact):
        self.pause.setIcon(vector_icon('play' if paused else 'pause'))
        self.pause.setToolTip('Resume (F7)' if paused else 'Pause (F7)')
        self.compact.setIcon(vector_icon('plus' if compact else 'minus'))
        self.compact.setToolTip('Expand dock' if compact else 'Compact dock')


class DockGripOverlay(QWidget):
    """Clickable drag grip above the LEFT edge of the passive status HWND.

    It has its own nonactivating Win32 surface, so the rest of the status
    continues forwarding clicks to the target application during recording.
    """
    def __init__(self, dock):
        flags=Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        if sys.platform=='win32':
            flags |= Qt.WindowDoesNotAcceptFocus
        super().__init__(None, flags)
        self.setObjectName('dockGripOverlay')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedSize(34,42)
        row=H(self,(0,0,0,0),0)
        self.drag_handle=DockDragHandle(dock)
        self.drag_handle.setObjectName('dockGripIcon')
        self.drag_handle.setFixedSize(34,42)
        self.drag_handle.setToolTip('Drag to move the recording dock')
        self.drag_handle.setAccessibleName('Drag recording dock')
        row.addWidget(self.drag_handle)
        self._excluded_from_capture=False

    def showEvent(self,event):
        super().showEvent(event)
        if sys.platform != 'win32':
            return
        try:
            hwnd=int(self.winId())
            user32=ctypes.windll.user32
            current=user32.GetWindowLongW(hwnd,-20)
            user32.SetWindowLongW(hwnd,-20,(current | 0x08000000) & ~0x00000020)
            user32.SetWindowPos(hwnd,-1,0,0,0,0,
                                0x0010|0x0002|0x0001|0x0200|0x0020)
            if not self._excluded_from_capture:
                self._excluded_from_capture=bool(user32.SetWindowDisplayAffinity(hwnd,0x11))
        except Exception:
            pass


class ControlDock(QWidget):
    """Compact floating record bar. Editing controls stay in the editor."""
    def __init__(self, owner):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.owner = owner
        self.setObjectName('dockWindow')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(846, 84)
        self.countdown_secs = int(owner.settings.value('countdown', 3))
        self.target_mode = str(owner.settings.value('capture_scope', 'window'))
        self.selected_hwnd = 0
        self.selected_window_title = ''
        self.selected_window_display = ''
        self.selected_screen_bounds = None
        self.selected_screen_label = ''
        if self.target_mode not in ('window','screen'):
            self.target_mode = 'window'
        self._no_activate = False
        self._pointer_passthrough = False
        self._capture_exclusion_attempted = False
        self.compact_active = str(owner.settings.value('dock_short_while_active','true')).lower() == 'true'
        self.control_island = None
        self.grip_overlay = None
        self._dock_geometry_animation=QPropertyAnimation(self,b'geometry',self)
        self._dock_geometry_animation.setDuration(245)
        self._dock_geometry_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self._target_dimensions=(846,84)
        root=V(self,(10,7,10,9),0)
        self.root_layout=root
        body=F('dockBody')
        self.body=body
        root.addWidget(body,1)
        shadow=QGraphicsDropShadowEffect(body)
        self.dock_shadow=shadow
        shadow.setBlurRadius(46)
        shadow.setOffset(0,11)
        shadow.setColor(QColor(0,0,0,171))
        body.setGraphicsEffect(shadow)
        self.stack=QStackedWidget(body)
        self.stack.setObjectName('dockStack')
        outer=V(body,(8,5,8,5),0)
        outer.addWidget(self.stack)

        idle=QWidget()
        idle.setObjectName('dockPage')
        row=H(idle,(0,0,0,0),5)
        row.addWidget(DockDragHandle(self))
        self.target=QPushButton()
        self.target.setObjectName('dockButton')
        self.target.clicked.connect(self.show_targets)
        self.target.setToolTip('Choose a screen or a specific open application')
        self.target.setFixedWidth(194)
        # Layout-based vector chevron: unlike a text glyph it stays centered
        # across font scaling, DPI differences and Windows fallback fonts.
        label_row=H(self.target,(9,0,8,0),7)
        self.target_icon=QLabel(); self.target_icon.setFixedSize(21,21)
        label_row.addWidget(self.target_icon)
        self.target_text=L('Window','targetName')
        label_row.addWidget(self.target_text,1)
        self.target_chevron=QLabel()
        self.target_chevron.setPixmap(vector_icon('chevron','#AAB4CB',14).pixmap(14,14))
        self.target_chevron.setFixedSize(16,16)
        label_row.addWidget(self.target_chevron)
        for label in (self.target_icon,self.target_text,self.target_chevron):
            label.setAttribute(Qt.WA_TransparentForMouseEvents,True)
        row.addWidget(self.target)
        row.addSpacing(3)
        row.addWidget(self._separator())
        row.addStretch(1)
        self.center=icon_button('target',lambda:None,'Center the cursor in the target before recording')
        self.center.setCheckable(True)
        self.center.setChecked(str(owner.settings.value('center','true')).lower()=='true')
        self.center.toggled.connect(lambda checked:owner.settings.setValue('center',checked))
        row.addWidget(self.center)
        self.timer_button=QPushButton()
        self.timer_button.setObjectName('dockButton')
        self.timer_button.setIcon(vector_icon('clock','#91A6FF'))
        self.timer_button.setIconSize(QSize(20,20))
        self.timer_button.clicked.connect(self.show_countdowns)
        self.timer_button.setToolTip('Countdown before capture')
        self.timer_button.setFixedWidth(77)
        row.addWidget(self.timer_button)
        row.addSpacing(5)
        row.addWidget(self._separator())
        row.addStretch(1)
        self.primary_stack=QStackedWidget()
        self.primary_stack.setFixedSize(50,50)
        self.primary_stack.setObjectName('dockStack')
        self.record=RecordOrb(owner.start_recording)
        self.primary_stack.addWidget(self.record)
        self.replay=QPushButton()
        self.replay.setObjectName('replayOrb')
        self.replay.setIcon(vector_icon('play','#FFFFFF',24))
        self.replay.setIconSize(QSize(22,22))
        self.replay.setToolTip('Replay workflow · starts after countdown')
        self.replay.setCursor(Qt.PointingHandCursor)
        self.replay.clicked.connect(owner.start_playback)
        self.primary_stack.addWidget(self.replay)
        row.addWidget(self.primary_stack)
        self.retake_button=icon_button('retake',owner.retake,'Retake: record again using this target and countdown',color='#A9B8FE',size=20)
        self.retake_button.setObjectName('dockRetake')
        self.retake_button.setText(' Retake')
        self.retake_button.setFixedWidth(96)
        row.addWidget(self.retake_button)
        row.addSpacing(5)
        row.addWidget(self._separator())
        row.addStretch(1)
        self.edit_dock=icon_button('edit',owner.show_editor,'Open action editor')
        self.edit_dock.setObjectName('dockEdit')
        row.addWidget(self.edit_dock)
        self.more=icon_button('dots',self.show_more,'More options')
        row.addWidget(self.more)
        row.addWidget(icon_button('minus',self.minimize_to_taskbar,'Minimize to taskbar'))
        row.addWidget(icon_button('close',self.close,'Close TakePath'))
        self.stack.addWidget(idle)

        active=QWidget()
        active.setObjectName('dockPage')
        row=H(active,(0,0,0,0),4)
        self.active_handle=DockDragHandle(self)
        row.addWidget(self.active_handle)
        # Fixed left starting slot, even when the active dock is compact.
        self.grip_placeholder=QWidget()
        self.grip_placeholder.setFixedSize(34,42)
        self.grip_placeholder.setStyleSheet('background: transparent;')
        self.grip_placeholder.hide()
        row.addWidget(self.grip_placeholder)
        self.mode_status=L('●  REC','recIndicator')
        self.mode_status.setMinimumWidth(80)
        row.addWidget(self.mode_status)
        self.clock=L('00:00','recordClock')
        self.clock.setMinimumWidth(64)
        row.addWidget(self.clock)
        self.step_status=L('','muted')
        self.step_status.setFixedWidth(230)
        self.step_status.setStyleSheet('color:#C6D2F5; font-size:11px; font-weight:650;')
        self.step_status.setToolTip('Current replay action')
        self.step_status.setVisible(False)
        row.addWidget(self.step_status)
        self.secure_hint=L('Manual input in app','muted')
        self.secure_hint.setStyleSheet('color:#C2CBF4; font-size:11px; font-weight:600;')
        self.secure_hint.setVisible(False)
        row.addWidget(self.secure_hint)
        row.addStretch(1)
        self.active_retake=icon_button('retake',owner.retake,'Discard this take and restart the recording countdown',color='#BDC8FF',size=19)
        row.addWidget(self.active_retake)
        self.pause=icon_button('pause',owner.toggle_pause,'Pause / resume (F7)')
        row.addWidget(self.pause)
        self.stop=icon_button('stop',owner.stop,'Stop (F8)','stopOrb','#FFFFFF',20)
        row.addWidget(self.stop)
        row.addStretch(1)
        self.active_separator=self._separator()
        row.addWidget(self.active_separator)
        self.active_minimize=icon_button('minus',self.minimize_to_taskbar,'Minimize to taskbar')
        self.active_close=icon_button('close',self.close,'Stop and close')
        row.addWidget(self.active_minimize)
        row.addWidget(self.active_close)
        self.stack.addWidget(active)
        if sys.platform == 'win32':
            # Independent native HWND: status stays click-through, controls
            # are genuinely clickable and nonactivating.
            self.control_island=DockControlIsland(self)
            self.grip_overlay=DockGripOverlay(self)
        self.set_target(self.target_mode)
        self._update_countdown()
        self.place(str(owner.settings.value('dock_location','top')), initially=True)
        self.sync()

    def _separator(self):
        line=F('separator')
        line.setFixedSize(1,25)
        return line

    def _update_target(self):
        if self.target_mode=='screen':
            label=self.selected_screen_label or 'Screen 1'
            icon='monitor'
        elif self.selected_hwnd:
            label=self.selected_window_display or self.selected_window_title
            icon='window'
        else:
            label='Active window'
            icon='window'
        metrics=self.target_text.fontMetrics()
        self.target_text.setText(metrics.elidedText(label,Qt.ElideRight,132))
        self.target_icon.setPixmap(vector_icon(icon,'#C3CCE5',19).pixmap(19,19))
        self.target.setToolTip(label if self.selected_hwnd or self.target_mode=='screen' else 'Capture the focused application')
        self.target.setProperty('hasTarget','true')
        self.target.style().unpolish(self.target)
        self.target.style().polish(self.target)

    def _update_countdown(self):
        self.timer_button.setText(f'  {self.countdown_secs}s' if self.countdown_secs else '  Off')

    def show_countdowns(self):
        menu=QMenu(self)
        for seconds,label in [(0,'No delay'),(3,'3 seconds'),(5,'5 seconds'),(10,'10 seconds')]:
            action=menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(self.countdown_secs==seconds)
            action.triggered.connect(lambda _,s=seconds:self.set_countdown(s))
        menu.exec(self.timer_button.mapToGlobal(QPoint(0,self.timer_button.height()+6)))

    def set_countdown(self, seconds):
        self.countdown_secs=int(seconds)
        self.owner.settings.setValue('countdown',self.countdown_secs)
        self._update_countdown()

    def show_targets(self):
        """Real screen and window picker, refreshed each time it opens."""
        menu=QMenu(self)
        menu.setMinimumWidth(340)
        screens=list(QGuiApplication.screens())
        primary=QGuiApplication.primaryScreen()
        if primary in screens:
            screens.remove(primary)
            screens.insert(0,primary)
        menu.addSection('SCREENS')
        for label,bounds,_ in screen_entries(screens):
            act=menu.addAction(vector_icon('monitor','#A7B8FF',18),label)
            act.setToolTip(f'{bounds[2]} × {bounds[3]}  ·  ({bounds[0]}, {bounds[1]})')
            act.setCheckable(True)
            act.setChecked(self.target_mode=='screen' and self.selected_screen_bounds==bounds)
            act.triggered.connect(lambda _checked=False,b=bounds,l=label:self.select_screen(b,l))
        menu.addSeparator()
        menu.addSection('APPLICATIONS')
        focused=menu.addAction(vector_icon('window','#C7D0E7',18),'Follow active application')
        focused.setToolTip('Record actions in whichever app is focused after the countdown')
        focused.setCheckable(True)
        focused.setChecked(self.target_mode=='window' and not self.selected_hwnd)
        focused.triggered.connect(lambda _checked=False:self.select_window(0,''))
        targets=open_windows()
        if not targets:
            empty=menu.addAction('No open applications — open one and try again')
            empty.setEnabled(False)
        # Native executable icons, when available; Qt falls back to a vector icon.
        icon_provider=QFileIconProvider()
        for item in targets:
            display=window_menu_label(item)
            app_icon=icon_provider.icon(QFileInfo(item.process_path)) if item.process_path else QIcon()
            if app_icon.isNull():
                app_icon=vector_icon('window','#B7C6DE',18)
            act=menu.addAction(app_icon,display)
            act.setToolTip(f'{item.app_name or "Application"}\n{item.title}')
            act.setCheckable(True)
            act.setChecked(self.target_mode=='window' and self.selected_hwnd==item.hwnd)
            act.triggered.connect(lambda _checked=False,h=item.hwnd,t=item.title,d=display:self.select_window(h,t,d))
        menu.exec(self.target.mapToGlobal(QPoint(0,self.target.height()+6)))

    def select_screen(self,bounds,label):
        self.target_mode='screen'
        self.selected_hwnd=0
        self.selected_window_title=''
        self.selected_window_display=''
        self.selected_screen_bounds=tuple(bounds)
        self.selected_screen_label=label
        if not self.owner.replay_ready:self.owner.settings.setValue('capture_scope','screen')
        self._update_target()

    def select_window(self,hwnd,title,display=None):
        self.target_mode='window'
        self.selected_hwnd=int(hwnd)
        self.selected_window_title=str(title)
        self.selected_window_display=str(display or title)
        self.selected_screen_bounds=None
        self.selected_screen_label=''
        if not self.owner.replay_ready:self.owner.settings.setValue('capture_scope','window')
        self._update_target()

    def set_target(self,mode):
        # Legacy calls from capture / playback navigation select a mode, not
        # a possibly stale HWND from an earlier recording.
        if mode=='screen':
            screens=list(QGuiApplication.screens())
            primary=QGuiApplication.primaryScreen()
            if primary in screens:
                screens.remove(primary); screens.insert(0,primary)
            if screens:
                label,bounds,_=screen_entries(screens)[0]
                self.select_screen(bounds,label)
            else:
                self.target_mode='screen';self._update_target()
        else:
            self.select_window(0,'')

    def show_more(self):
        menu=QMenu(self)
        if self.owner.project.actions:
            menu.addAction('Retake workflow', self.owner.retake)
        if self.owner.take_history.available:
            menu.addAction('Restore previous take', self.owner.restore_previous_take)
        if self.owner.project.actions or self.owner.take_history.available:
            menu.addSeparator()
        menu.addAction('Open editor',self.owner.show_editor)
        menu.addAction('New project',self.owner.new_project)
        menu.addAction('Open project…',self.owner.open_project)
        menu.addAction('Save project…',self.owner.save)
        menu.addSeparator()
        compact=menu.addAction('Compact dock during recording / replay')
        compact.setCheckable(True)
        compact.setChecked(self.compact_active)
        compact.toggled.connect(self.set_compact_mode)
        menu.addSeparator()
        position=menu.addMenu('Dock position')
        for label,mode in [('Top center','top'),('Top left','top-left'),('Top right','top-right'),('Bottom center','bottom')]:
            position.addAction(label,lambda p=mode:self.place(p))
        menu.exec(self.more.mapToGlobal(QPoint(0,self.more.height()+6)))

    def place(self, location='top', initially=False):
        self._dock_geometry_animation.stop()
        screen=QGuiApplication.primaryScreen().availableGeometry()
        margin=18
        # Include the separate clickable controller in position calculations.
        # Otherwise the short bar is centered but its controller extends off
        # the right edge, and the overall unit looks misaligned.
        active=isinstance(getattr(self,'control_island',None),DockControlIsland) and (
            self.owner.recorder.active or
            bool(self.owner.player and self.owner.player.isRunning()))
        extra=self.control_island.width() if active else 0
        visual_width=self.width()+extra
        # Previous releases called bottom-center "center". Starting with V4,
        # that alias means the requested top-centered placement.
        if location=='center':
            location='top'
        if location=='custom':
            x=int(self.owner.settings.value('dock_x', screen.center().x()-visual_width//2))
            y=int(self.owner.settings.value('dock_y', screen.top()+margin))
            if not screen.adjusted(-25,-25,25,25).contains(QPoint(x,y)):
                location='top'
        if location!='custom':
            x=(screen.left()+margin if location=='top-left' else
               screen.right()-visual_width-margin if location=='top-right' else
               screen.left()+(screen.width()-visual_width)//2)
            y=screen.bottom()-self.height()-margin if location=='bottom' else screen.top()+margin
        self.move(x,y)
        if not initially:
            self.owner.settings.setValue('dock_location',location)

    def set_compact_mode(self, compact):
        compact=bool(compact)
        if compact == self.compact_active:
            return
        self.compact_active=compact
        self.owner.settings.setValue('dock_short_while_active',compact)
        self.sync()

    def _sync_control_island(self, active, paused):
        island=self.control_island
        grip=self.grip_overlay
        if island is None:
            return
        if not active or not self.isVisible():
            island.hide()
            if grip is not None:
                grip.hide()
            self.owner.recorder.set_interactive_bounds(None)
            return
        island.update_controls(paused, self.compact_active)
        # The controller stays flush right; the independent drag grip stays
        # at the LEFT edge in both compact and expanded active modes.
        point=QPoint(self.x()+self.width(), self.y())
        if island.pos()!=point:
            island.move(point)
        if not island.isVisible():
            island.show()
            island.raise_()  # only on transition; never steal target focus
        if grip is not None:
            grip_point=QPoint(self.x()+8,self.y()+(self.height()-grip.height())//2)
            if grip.pos()!=grip_point:
                grip.move(grip_point)
            if not grip.isVisible():
                grip.show()
                grip.raise_()
        # Use physical native hit boxes, including high-DPI Windows monitors.
        # Neither window should cause the rest of the dock to block clicks.
        try:
            control_bounds=window_rect(int(island.winId()))
            grip_bounds=window_rect(int(grip.winId())) if grip is not None else None
            self.owner.recorder.set_interactive_bounds(control_bounds, grip_bounds)
        except Exception:
            self.owner.recorder.set_interactive_bounds(None)

    def moveEvent(self,event):
        super().moveEvent(event)
        self._reposition_active_controls()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self._reposition_active_controls()

    def _reposition_active_controls(self):
        if self.control_island is not None and self.control_island.isVisible():
            self._sync_control_island(True, self.owner.recorder.paused or
                bool(self.owner.player and self.owner.player.pause_flag.is_set()))

    def _transition_dock_geometry(self, width, height, active):
        """Animate about the existing combined dock center, never the screen center."""
        previous_total=self.width()+(
            self.control_island.width() if self.control_island is not None
            and self.control_island.isVisible() else 0)
        center_x=self.x()+previous_total/2
        center_y=self.y()+self.height()/2
        new_total=width+(self.control_island.width() if active and self.control_island else 0)
        goal=QRect(round(center_x-new_total/2),round(center_y-height/2),width,height)
        self._target_dimensions=(width,height)
        self._dock_geometry_animation.stop()
        self.setMinimumSize(0,0)
        self.setMaximumSize(16777215,16777215)
        if not self.isVisible():
            self.setGeometry(goal)
            return
        self._dock_geometry_animation.setStartValue(self.geometry())
        self._dock_geometry_animation.setEndValue(goal)
        self._dock_geometry_animation.start()

    def hideEvent(self,event):
        if self.control_island is not None:
            self.control_island.hide()
            if self.grip_overlay is not None:
                self.grip_overlay.hide()
            self.owner.recorder.set_interactive_bounds(None)
        super().hideEvent(event)

    def minimize_to_taskbar(self):
        """Minimize through the editor's ordinary taskbar window."""
        self.owner.minimize_dock_to_taskbar()

    def showEvent(self, event):
        super().showEvent(event)
        if sys.platform=='win32' and not self._capture_exclusion_attempted:
            self._capture_exclusion_attempted=True
            try:
                # Windows 10 2004+: hide this dock from supported display captures.
                ctypes.windll.user32.SetWindowDisplayAffinity(int(self.winId()),0x11)
            except Exception:
                pass

    def _avoid_stealing_focus(self, active, pointer_passthrough=False):
        """Make active recording/replay dock visible but transparent to mouse.

        On Windows a translucent layered window needs WS_EX_TRANSPARENT
        for clicks to reach the underlying browser (e.g. URL bar).
        F7/F8 remain global pause/stop controls while click-through is on.
        Never intercept a click just because the overlay crosses a target.
        """
        if sys.platform != 'win32':
            return
        desired=bool(pointer_passthrough)
        if active == self._no_activate and desired == getattr(self,'_pointer_passthrough',False):
            return
        try:
            hwnd=int(self.winId())
            user32=ctypes.windll.user32
            flags=user32.GetWindowLongW(hwnd,-20)
            noactivate=0x08000000
            transparent=0x00000020
            layered=0x00080000
            updated=flags | noactivate if active else flags & ~noactivate
            if desired:
                updated |= transparent | layered
            else:
                updated &= ~transparent
            if updated != flags:
                user32.SetWindowLongW(hwnd,-20,updated)
                # Tell Windows to update hit-testing after extended styles
                # change; do not move or foreground the overlay.
                user32.SetWindowPos(hwnd,0,0,0,0,0,
                                   0x0001|0x0002|0x0004|0x0010|0x0020)
            self._no_activate=active
            self._pointer_passthrough=desired
        except Exception:
            pass

    def sync(self):
        recording=self.owner.recorder.active
        playing=bool(self.owner.player and self.owner.player.isRunning())
        pending=self.owner.timer.isActive() or bool(self.owner.pending_mode)
        busy=recording or playing or pending
        island_active=bool(self.control_island and (recording or playing))
        # The status HWND passes mouse clicks through; the adjoining control
        # HWND handles Pause/Stop and dragging. Both PAINT as one short pill.
        # Idle and countdown retain the original full dock and its shadow.
        desired_width=(290 if playing else 214) if island_active and self.compact_active else 846
        desired_height=64 if island_active else 84
        self.root_layout.setContentsMargins(
            *((0,0,0,0) if island_active else (10,7,10,9)))
        self.dock_shadow.setEnabled(not island_active)
        body_role='dockBodyJoinedLeft' if island_active else 'dockBody'
        if self.body.objectName()!=body_role:
            self.body.setObjectName(body_role)
            self.body.style().unpolish(self.body)
            self.body.style().polish(self.body)
            self.body.update()
        if self._target_dimensions!=(desired_width,desired_height):
            self._transition_dock_geometry(desired_width,desired_height,island_active)
        self.stack.setCurrentIndex(1 if busy else 0)
        self.retake_button.setVisible(bool(self.owner.project.actions) and not busy)
        self.active_retake.setVisible(recording and not island_active)
        for widget in (self.active_handle,self.pause,self.stop,self.active_separator,
                       self.active_minimize,self.active_close):
            widget.setVisible(not island_active)
        self.grip_placeholder.setVisible(island_active)
        self.step_status.setFixedWidth(148 if island_active and self.compact_active else 230)
        self.clock.setVisible(not (island_active and playing and self.compact_active))
        ready = self.owner.replay_ready and not busy
        self.primary_stack.setCurrentIndex(1 if ready else 0)
        self.center.setToolTip('Center before replay' if ready else 'Center before recording')
        finished = self.owner.playback_completed and not busy
        show_editor_label = finished or ready
        self.edit_dock.setText('  Open editor' if show_editor_label else '')
        self.edit_dock.setToolTip('Back to action editor' if ready else ('Open editor after replay' if finished else 'Open action editor'))
        self.edit_dock.setFixedWidth(135 if show_editor_label else 38)
        waiting = bool(playing and self.owner.player.awaiting_secure_input)
        self.secure_hint.setVisible(waiting and not (island_active and self.compact_active))
        self.step_status.setVisible(playing)
        if playing:
            index=self.owner.last_playback_step
            if 0 <= index < len(self.owner.project.actions):
                summary=format_replay_step(self.owner.project.actions[index],index,
                                           len(self.owner.project.actions))
                self.step_status.setText(self.step_status.fontMetrics().elidedText(
                    summary, Qt.ElideRight, self.step_status.width()-5))
                self.step_status.setToolTip(summary)
            else:
                self.step_status.setText('Preparing replay…')
                self.step_status.setToolTip('Waiting for the first action')
        self.pause.setToolTip('Continue after manual input (F7)' if waiting else 'Pause / resume (F7)')
        self._avoid_stealing_focus(busy or ready, pointer_passthrough=recording or playing)
        self.stop.setToolTip("Use the floating Stop controller or F8" if island_active else "Stop (F8)")
        self.stop.setIcon(vector_icon('close','#FFFFFF') if pending else vector_icon('stop','#FFFFFF'))
        self.pause.setEnabled(recording or playing)
        if recording:
            paused=self.owner.recorder.paused
            self.mode_status.setText('Ⅱ  PAUSED' if paused else '●  REC')
            self.mode_status.setStyleSheet('color:#FF647F; font-weight:750;')
            self.pause.setIcon(vector_icon('play' if paused else 'pause'))
        elif playing:
            paused=bool(self.owner.player.pause_flag.is_set())
            focus_wait=bool(getattr(self.owner, 'player_waiting_for_focus', False))
            ui_wait=bool(getattr(self.owner, 'player_waiting_for_ui', False))
            self.mode_status.setText('●  INPUT' if waiting else ('WAIT UI' if ui_wait else ('WAIT TARGET' if focus_wait else ('Ⅱ  PAUSED' if paused else '▶  PLAY'))))
            self.mode_status.setStyleSheet('color:#F5C680; font-weight:750;' if (waiting or focus_wait or ui_wait) else 'color:#8EA5FF; font-weight:750;')
            self.pause.setIcon(vector_icon('play' if paused else 'pause'))
        else:
            self.mode_status.setText('REPLAY IN' if self.owner.pending_mode=='play' else 'START IN')
            self.mode_status.setStyleSheet('color:#A2A9FF; font-weight:750;')
        if pending and not (recording or playing):
            self.clock.setText(str(self.owner.left_count))
        if not (recording or playing):
            self.stop.setToolTip('Cancel countdown' if pending else 'Stop (F8)')
        paused=bool(self.owner.recorder.paused if recording else
                    self.owner.player.pause_flag.is_set() if playing else False)
        self._sync_control_island(island_active, paused)

    def closeEvent(self,event):
        if self.owner.busy():
            # Avoid discarding captured actions while the recorder's finished
            # signal is waiting to open the editor.
            self.owner.stop()
            event.ignore()
            return
        if self.owner.close():
            event.accept()
        else:
            event.ignore()




def _center_dialog_on_screen(dialog):
    """Center over the visible dock/editor's monitor, never near the dock's top edge.

    Works with message boxes and credential-entry dialogs.  Re-run after the
    native window is shown because Windows can adjust the frame dimensions.
    """
    try:
        dialog.ensurePolished()
        if dialog.layout():dialog.layout().activate()
        dialog.adjustSize()
        parent=dialog.parentWidget()
        screen=parent.screen() if parent is not None and parent.isVisible() else None
        if screen is None:screen=QGuiApplication.primaryScreen()
        if screen is None:return
        area=screen.availableGeometry()
        frame=dialog.frameSize() if dialog.isVisible() else dialog.size()
        width=max(frame.width(),dialog.minimumWidth())
        height=max(frame.height(),dialog.minimumHeight())
        x=area.x()+max(0,(area.width()-width)//2)
        y=area.y()+max(0,(area.height()-height)//2)
        dialog.move(x,y)
    except Exception:
        pass  # Positioning must never prevent a critical prompt from opening.


def _foreground_dialog(dialog):
    """Make a short-lived modal prompt visible over the recorded browser.

    The full editor is often hidden while the floating dock stays topmost.
    A dialog parented to the hidden editor can therefore appear behind Chrome.
    """
    dialog.setWindowModality(Qt.ApplicationModal)
    dialog.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    dialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    _center_dialog_on_screen(dialog)

    def bring_forward():
        if not dialog.isVisible():
            return
        _center_dialog_on_screen(dialog)
        dialog.raise_()
        dialog.activateWindow()
        if sys.platform == 'win32':
            try:
                hwnd = int(dialog.winId())
                user32 = ctypes.windll.user32
                # HWND_TOPMOST with no size/position change.
                user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
                user32.SetForegroundWindow(hwnd)
            except Exception:
                pass

    QTimer.singleShot(0, bring_forward)
    QTimer.singleShot(120, bring_forward)
    return dialog


def _ask_in_front(parent, title, message, buttons, default):
    dialog = QMessageBox(QMessageBox.Question, title, message, buttons, parent)
    dialog.setDefaultButton(default)
    return _foreground_dialog(dialog).exec()


def _warn_in_front(parent, title, message):
    dialog = QMessageBox(QMessageBox.Warning, title, message, QMessageBox.Ok, parent)
    return _foreground_dialog(dialog).exec()


class SecurePreflightDialog(QDialog):
    """Request missing auto-fill values once, BEFORE starting the replay countdown."""
    def __init__(self, missing: list[tuple[str, str]], parent=None, allow_save=True):
        super().__init__(parent)
        self.setWindowTitle('Secure inputs for replay')
        self.setMinimumWidth(460)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint,False)
        layout=V(self,(24,22,24,20),14)
        layout.addWidget(L('Complete secure inputs','heading'))
        explanation=L('These values will be typed automatically into the target app. '
                      'Securely save on this device, or reuse one value for every missing step when appropriate.','muted')
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.inputs={}
        self.remember={}
        for ref,description in missing:
            group=F('card'); col=V(group,(12,10,12,11),7)
            col.addWidget(L(description,'muted'))
            edit=QLineEdit(); edit.setEchoMode(QLineEdit.Password)
            edit.setPlaceholderText('Password or secret value')
            edit.setMaxLength(512)
            password_row=H(spacing=7)
            password_row.addWidget(edit,1)
            password_row.addWidget(password_reveal_button(edit))
            col.addLayout(password_row)
            checkbox=QCheckBox('Save securely on this Windows PC')
            checkbox.setChecked(bool(allow_save))
            checkbox.setEnabled(allow_save)
            if not allow_save: checkbox.setToolTip('Windows Credential Manager is unavailable. Session-only input still works.')
            col.addWidget(checkbox)
            layout.addWidget(group)
            self.inputs[ref]=edit
            self.remember[ref]=checkbox
        self.apply_all=QCheckBox('Use the first passphrase for all missing secure inputs')
        self.apply_all.setChecked(False)
        self.apply_all.setEnabled(len(self.inputs)>1)
        self.apply_all.setToolTip('Only enable when every missing field uses exactly the same secret.')
        self.apply_all.toggled.connect(self._toggle_reuse)
        layout.addWidget(self.apply_all)
        self.error=L('','muted');self.error.setStyleSheet('color:#FF8899;');layout.addWidget(self.error)
        btn=QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        btn.button(QDialogButtonBox.Ok).setText('Prepare replay')
        btn.rejected.connect(self.reject)
        btn.accepted.connect(self._confirm)
        layout.addWidget(btn)
        if self.inputs:next(iter(self.inputs.values())).setFocus()

    def _toggle_reuse(self, enabled):
        first=next(iter(self.inputs))
        for ref,widget in self.inputs.items():
            if ref==first:continue
            widget.setEnabled(not enabled)
            self.remember[ref].setEnabled(not enabled and self.remember[first].isEnabled())

    def _confirm(self):
        try:
            if self.apply_all.isChecked():
                validate_password(next(iter(self.inputs.values())).text())
            else:
                for widget in self.inputs.values():validate_password(widget.text())
        except ValueError:
            self.error.setText('Enter a value for every required secure input.')
            return
        self.accept()

    def submitted(self):
        # Explicit opt-in to reuse the first value, never automatic guessing.
        if self.apply_all.isChecked():
            first=next(iter(self.inputs))
            secret=self.inputs[first].text()
            persist=self.remember[first].isChecked()
            return [(ref,secret,persist) for ref in self.inputs]
        return [(ref,edit.text(),self.remember[ref].isChecked()) for ref,edit in self.inputs.items()]


class PortablePassphraseDialog(QDialog):
    """User-supplied export/unlock passphrase. Never save or remember it."""
    def __init__(self,parent=None,confirm=False):
        super().__init__(parent)
        self.setWindowTitle('Encrypt portable project' if confirm else 'Unlock portable project')
        self.setMinimumWidth(460)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint,False)
        layout=V(self,(22,20,22,18),12)
        help_text=('A portable copy will include AES-GCM encrypted secure values. '
                   'Remember this passphrase: it cannot be recovered.'
                   if confirm else
                   'This project contains encrypted secure values. '
                   'Enter its export passphrase to unlock them for replay.')
        help_label=L(help_text,'muted');help_label.setWordWrap(True)
        layout.addWidget(help_label)
        self.value=QLineEdit()
        self.value.setEchoMode(QLineEdit.Password)
        self.value.setPlaceholderText('Passphrase (12+ characters)')
        self.value.setMaxLength(512)
        row=H(spacing=8);row.addWidget(self.value,1);row.addWidget(password_reveal_button(self.value))
        layout.addLayout(row)
        self.confirm=QLineEdit() if confirm else None
        if self.confirm is not None:
            self.confirm.setEchoMode(QLineEdit.Password)
            self.confirm.setPlaceholderText('Confirm passphrase')
            row=H(spacing=8);row.addWidget(self.confirm,1);row.addWidget(password_reveal_button(self.confirm))
            layout.addLayout(row)
        self.error=L('','muted');layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept_if_valid);buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_if_valid(self):
        if len(self.value.text()) < 12:
            self.error.setText('Use at least 12 characters.')
        elif self.confirm is not None and self.value.text()!=self.confirm.text():
            self.error.setText('Passphrases do not match.')
        else:
            self.accept()

    def passphrase(self):
        return self.value.text()

    def clear_passphrase(self):
        self.value.clear()
        if self.confirm is not None:self.confirm.clear()


class ActionContextMenu(QMenu):
    """Use Qt's native submenu aim/timing; do not hide on pointer movement.

    Previously aggressive hover handlers closed Mouse Speed as the cursor
    crossed the small gap from the root item into its submenu.
    """
    pass


class ActionTable(QTableWidget):
    """Drag timeline rows without letting Qt rearrange individual cells.

    The project (rather than the table widget) owns the action order. A
    drop supplies the original selected rows and the insertion boundary
    to MainWindow, which atomically reorders Action objects and refreshes
    the visual list. Multiple selected rows retain their relative order.
    """
    actionsDropped = Signal(list, int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDropIndicatorShown(True)
        self.setDragDropOverwriteMode(False)
        self._dragged_rows = []

    def mousePressEvent(self, event):
        # Native right-click must not collapse an existing multi-selection.
        # If the row is already selected, keep the selection for the menu.
        if event.button() == Qt.RightButton:
            index=self.indexAt(event.position().toPoint())
            if index.isValid() and self.selectionModel().isSelected(index):
                event.accept()
                return
        super().mousePressEvent(event)

    def startDrag(self, supported_actions):
        self._dragged_rows = sorted({index.row() for index in self.selectedIndexes()})
        if not self._dragged_rows:
            return
        try:
            super().startDrag(Qt.MoveAction)
        finally:
            self._dragged_rows = []

    def dragEnterEvent(self, event):
        if event.source() is self:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.source() is self:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        # A built-in QTableWidget InternalMove can shift cell contents
        # independently; never call the default drop handler.
        rows = list(self._dragged_rows)
        if event.source() is not self or not rows:
            event.ignore()
            return
        point = event.position().toPoint()
        index = self.indexAt(point)
        if index.isValid():
            target = index.row()
            cell = self.visualRect(index)
            if point.y() >= cell.center().y():
                target += 1
        else:
            target = 0 if point.y() < 0 else self.rowCount()
        event.acceptProposedAction()
        # Let the native drag gesture finish before replacing table items.
        QTimer.singleShot(0, lambda: self.actionsDropped.emit(rows, target))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings=QSettings('VisualActionStudio','VisualActionStudioV4')  # keep V9 preferences
        self.project=Project(cursor_mode=self.settings.value('cursor_mode','smooth'),
                             global_typing_mode=self.settings.value('typing_mode','smooth'))
        self.project_path=None
        self.is_dirty=False
        self.session_secrets={}  # memory-only; not written into projects / settings
        self.prepared_secure={}
        self._dock_taskbar_minimized=False
        try:
            self.credential_store=credential_store()
        except CredentialError:
            self.credential_store=None
        self.recorder=Recorder(self)
        self.recorder.started.connect(self._recording_started)
        self.recorder.finished.connect(self._recording_done)
        self.recorder.notice.connect(self.notice)
        self.recorder.pause_changed.connect(self._record_pause_status)
        self.player=None
        self.last_playback_message=''
        self.last_playback_step=-1
        self.target_hwnd=0
        self.record_started_at=0.0
        self.play_started_at=0.0
        self.pending_mode=''
        self.playback_completed=False
        self.replay_ready=False
        self.retake_pending=False
        self.restart_recording=False
        self.take_history=RetakeHistory()
        self.retake_origin_hwnd=0
        self.pending_record_scope='window'
        self.last_external_hwnd=0
        self.left_count=0
        self.ticker=QTimer(self)
        self.ticker.setInterval(200)
        self.ticker.timeout.connect(self._heartbeat)
        self.ticker.start()
        self.timer=QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick_countdown)
        self.updating=False
        self._build_editor()
        QApplication.instance().installEventFilter(self)
        self.dock=ControlDock(self)
        self.tray=None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray=QSystemTrayIcon(app_icon(),self)
            self.tray.setToolTip('TakePath · Action Recorder')
            self.tray_menu=QMenu(self)
            menu=self.tray_menu
            menu.addAction('Show recorder',self.show_dock)
            menu.addAction('Retake workflow',self.retake)
            menu.addAction('Open editor',self.show_editor)
            menu.addSeparator()
            menu.addAction('Stop active session (F8)',self.stop)
            menu.addAction('Exit',self.close)
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(lambda reason:self.show_dock() if reason==QSystemTrayIcon.Trigger else None)
            self.tray.show()
        self._build_shortcuts()
        self.refresh()
        self.setWindowTitle(f'TakePath {__version__}')
        self.setWindowIcon(app_icon())
        self.resize(1500,920)
        self.setMinimumSize(1010,690)

    def _build_editor(self):
        base=QWidget(); self.setCentralWidget(base)
        root=V(base,spacing=0)
        head=F('topBar'); hb=H(head,(22,12,22,12),11)
        logomark=QLabel()
        logomark.setPixmap(app_icon().pixmap(32,32))
        hb.addWidget(logomark)
        brandbox=V(spacing=1)
        brandbox.addWidget(L('TakePath','brand'))
        brandbox.addWidget(L('WORKFLOW EDITOR','tiny'))
        hb.addLayout(brandbox)
        hb.addSpacing(22)
        self.name=QLineEdit('Untitled workflow')
        self.name.setFixedWidth(244)
        self.name.setToolTip('Rename workflow')
        self.name.editingFinished.connect(self._rename)
        hb.addWidget(self.name)
        hb.addStretch(1)
        hb.addWidget(B('Save',self.save,'outline','Save project · Ctrl+S'))
        hb.addWidget(B('Back to recorder',self.show_dock,'quiet'))
        hb.addWidget(B('New capture',self.prepare_new_capture,'outline','Close editor and return to the recorder bar'))
        hb.addWidget(B('▶  Replay',self.prepare_replay,'primary','Switch to replay dock. Press Play there to start.'))
        root.addWidget(head)
        main_row=H(spacing=0)
        rail=F('rail');rail.setFixedWidth(58)
        railbox=V(rail,(10,14,10,10),12)
        railbox.addWidget(icon_button('arrow-left',self.show_dock,'Return to recording bar',color='#9CA7C3'))
        railbox.addSpacing(8)
        self.rail_add_button=icon_button('plus',self.add_action,'Insert action after selected; use + Before above the list to insert ahead',color='#A5B5FE')
        railbox.addWidget(self.rail_add_button)
        railbox.addWidget(icon_button('folder',self.open_project,'Open a project'))
        railbox.addWidget(icon_button('save',self.save,'Save this project'))
        railbox.addStretch(1)
        self.rail_delete_button=icon_button('trash',self.delete_selected,'Delete selected steps',color='#F0A4B3')
        railbox.addWidget(self.rail_delete_button)
        main_row.addWidget(rail)
        body=QSplitter(Qt.Vertical); body.setChildrenCollapsible(False)
        main_row.addWidget(body,1)
        root.addLayout(main_row,1)
        upper=QWidget(); up=H(upper,(16,14,16,6),12)
        center=F('card'); cv=V(center,(10,10,10,10),9)
        row=H(spacing=10)
        row.addWidget(L('ACTION MAP','tiny'))
        self.frame_hint=L('Optional spatial overview','muted')
        row.addWidget(self.frame_hint,1)
        row.addWidget(B('Expand preview',self.fullscreen_preview,'quiet'))
        row.addWidget(B('Remove image',self.clear_preview,'quiet'))
        cv.addLayout(row)
        self.canvas=SceneCanvas(self)
        cv.addWidget(self.canvas,1)
        self.canvas.picked.connect(self.select_index)
        self.canvas.moved.connect(self.move_canvas_point)
        up.addWidget(center,1)
        inspector=F('card'); inspector.setFixedWidth(320)
        self.inspector_panel=inspector
        ins=V(inspector,(14,15,14,12),10)
        ins.addWidget(L('ACTION PROPERTIES','tiny'))
        self.inspector_title=L('Select an action','heading')
        ins.addWidget(self.inspector_title)
        self.inspector_info=L('Choose a step below, or click a numbered marker in the preview.','muted')
        self.inspector_info.setWordWrap(True)
        ins.addWidget(self.inspector_info)
        scroller=QScrollArea(); scroller.setWidgetResizable(True)
        scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder=QWidget(); holder.setObjectName('inspectorHolder'); form=V(holder,(3,6,3,10),9)
        self.enable=QCheckBox('Include in playback')
        self.enable.toggled.connect(lambda v:self._set('enabled',v))
        form.addWidget(self.enable)
        self.delay_caption=L('PAUSE BEFORE ACTION','tiny')
        form.addWidget(self.delay_caption)
        self.delay=number(val=.5)
        self.delay.valueChanged.connect(lambda v:self._set('delay',v))
        form.addWidget(self.delay)
        self.text_container=QWidget(); self.text_container.setObjectName('propertyGroup'); tv=V(self.text_container,spacing=7)
        tv.addWidget(L('TEXT CONTENT','tiny'))
        self.edit_text=QTextEdit(); self.edit_text.setMaximumHeight(122)
        self.edit_text.textChanged.connect(lambda:self._set('text',self.edit_text.toPlainText()))
        tv.addWidget(self.edit_text)
        tv.addWidget(L('Global typing style controls replay.','muted'))
        tv.addWidget(L('Smooth typing interval','muted'))
        self.char_delay=number(0,2,.055)
        self.char_delay.valueChanged.connect(lambda v:self._set('char_delay',v))
        tv.addWidget(self.char_delay)
        tv.addWidget(B('Convert to secure input',self.convert_to_secure,'outline',
                       'Remove captured plain text and replace with an editable secure input action'))
        form.addWidget(self.text_container)
        self.secure_container=QWidget();self.secure_container.setObjectName('propertyGroup')
        sv=V(self.secure_container,spacing=9)
        sv.addWidget(L('SECURE INPUT','tiny'))
        self.secure_mode=QComboBox()
        self.secure_mode.addItem('Auto-fill', 'auto')
        self.secure_mode.addItem('Manual in target app', 'manual')
        self.secure_mode.addItem('Skip', 'skip')
        self.secure_mode.currentIndexChanged.connect(self._change_secure_mode)
        sv.addWidget(self.secure_mode)
        self.secure_autofill=QWidget();secure_form=V(self.secure_autofill,spacing=7)
        self.secret_status=L('Not configured','muted')
        self.secret_status.setWordWrap(True)
        secure_form.addWidget(self.secret_status)
        self.secret_edit=QLineEdit();self.secret_edit.setEchoMode(QLineEdit.Password)
        self.secret_edit.setPlaceholderText('Enter value to auto-fill (optional)')
        self.secret_edit.setMaxLength(512)
        secret_row=H(spacing=7)
        secret_row.addWidget(self.secret_edit,1)
        self.secret_reveal=password_reveal_button(self.secret_edit)
        secret_row.addWidget(self.secret_reveal)
        secure_form.addLayout(secret_row)
        self.secret_remember=QCheckBox('Save securely on this Windows PC')
        secure_form.addWidget(self.secret_remember)
        # These controls used to be placed side by side in a 288px inspector,
        # forcing horizontal scrolling and clipping the password controls.
        controls=V(spacing=5)
        controls.addWidget(B('Set value',self.set_secure_value,'primary'))
        controls.addWidget(B('Forget value',self.forget_secure_value,'quiet'))
        secure_form.addLayout(controls)
        review=B('Review value',self.review_secure_value,'quiet',
                 'Explicitly load the configured value into the masked field for verification')
        secure_form.addWidget(review)
        secret_help=L('Values stay hidden unless you click the eye icon. They never go in project JSON.','muted')
        secret_help.setWordWrap(True)
        secure_form.addWidget(secret_help)
        sv.addWidget(self.secure_autofill)
        form.addWidget(self.secure_container)
        self.key_container=QWidget(); self.key_container.setObjectName('propertyGroup'); kv=V(self.key_container,spacing=7)
        kv.addWidget(L('KEY OR SHORTCUT','tiny'))
        self.key=QLineEdit()
        self.key.textEdited.connect(lambda v:self._set('key',v))
        kv.addWidget(self.key)
        form.addWidget(self.key_container)
        self.wait_container=QWidget(); self.wait_container.setObjectName('propertyGroup')
        wait_form=V(self.wait_container,spacing=7)
        wait_form.addWidget(L('WAIT TYPE','tiny'))
        self.wait_mode=QComboBox()
        for label,mode in [('Pause for a fixed duration','duration'),
                           ('Target window title contains','target_title'),
                           ('Active window title contains','active_title'),
                           ('Focused safe field','focused_safe'),
                           ('Focused password field','focused_protected'),
                           ('Named control (Windows)','control_name')]:
            self.wait_mode.addItem(label,mode)
        self.wait_mode.currentIndexChanged.connect(lambda _i:self._set('wait_mode',self.wait_mode.currentData()))
        wait_form.addWidget(self.wait_mode)
        self.wait_value_caption=L('Window title / control name (when applicable)','muted')
        wait_form.addWidget(self.wait_value_caption)
        self.wait_value=QLineEdit()
        self.wait_value.setMaxLength(160)
        self.wait_value.setPlaceholderText('e.g. Save As or Search results')
        self.wait_value.textEdited.connect(lambda v:self._set('wait_value',v))
        wait_form.addWidget(self.wait_value)
        self.wait_timeout_caption=L('Maximum wait for condition (seconds)','muted')
        wait_form.addWidget(self.wait_timeout_caption)
        self.wait_timeout=number(0.5,120,15)
        self.wait_timeout.valueChanged.connect(lambda v:self._set('wait_timeout',v))
        wait_form.addWidget(self.wait_timeout)
        self.wait_help=L('Fixed pause uses the seconds above. Conditional waits only continue when the check is satisfied.','muted')
        self.wait_help.setWordWrap(True)
        wait_form.addWidget(self.wait_help)
        form.addWidget(self.wait_container)
        self.pointer_container=QWidget(); self.pointer_container.setObjectName('propertyGroup'); pv=V(self.pointer_container,spacing=7)
        pv.addWidget(L('SCREEN POSITION','tiny'))
        grid=QGridLayout();grid.setSpacing(7)
        self.coords={}
        for i,field in enumerate(['x','y','end_x','end_y']):
            widget=spin(-100000,100000)
            widget.valueChanged.connect(lambda v,key=field:self._set(key,v))
            self.coords[field]=widget
            grid.addWidget(L(field.replace('_',' ').upper(),'muted'),(i//2)*2,i%2)
            grid.addWidget(widget,(i//2)*2+1,i%2)
        pv.addLayout(grid)
        self.mouse_button=QComboBox()
        for caption, value in [('Left', 'left'), ('Right', 'right'), ('Middle', 'middle'),
                               ('Back (X1)', 'x1'), ('Forward (X2)', 'x2')]:
            self.mouse_button.addItem(caption, value)
        self.mouse_button.currentIndexChanged.connect(lambda _i:self._set('button',self.mouse_button.currentData()))
        pv.addWidget(L('Button','muted'))
        pv.addWidget(self.mouse_button)
        pv.addWidget(L('Movement time','muted'))
        self.motion_time=number(0,20,.32)
        self.motion_time.valueChanged.connect(lambda v:self._set('path_duration',v))
        pv.addWidget(self.motion_time)
        form.addWidget(self.pointer_container)
        self.scroll_container=QWidget(); self.scroll_container.setObjectName('propertyGroup'); sv=V(self.scroll_container,spacing=7)
        sv.addWidget(L('SCROLL AMOUNTS','tiny'))
        self.scroll_x=spin(-5000,5000);self.scroll_y=spin(-5000,5000)
        for text,widget,field in [('Horizontal',self.scroll_x,'dx'),('Vertical',self.scroll_y,'dy')]:
            sv.addWidget(L(text,'muted'));sv.addWidget(widget)
            widget.valueChanged.connect(lambda v,key=field:self._set(key,v))
        form.addWidget(self.scroll_container)
        form.addStretch()
        scroller.setWidget(holder);ins.addWidget(scroller,1)
        self.inspector_form=scroller
        main_row.addWidget(inspector)
        body.addWidget(upper)
        lower=F('card'); low=V(lower,(14,12,14,11),8)
        bar=H(spacing=8)
        bar.addWidget(L('Recorded actions','actionTitle'))
        self.count_label=L('0 steps','muted');bar.addWidget(self.count_label)
        bar.addStretch()
        self.preview_choice=B('Show action map',self.preview_menu,'quiet','Optional screenshot and click-position map')
        bar.addWidget(self.preview_choice)
        self.add_action_button=B('+ Add',self.add_action,'outline','Insert after the selected action; append when nothing is selected')
        bar.addWidget(self.add_action_button)
        self.before_action_button=B('+ Before',lambda:self.add_action(before=True),'quiet','Insert before the selected action, or at the very beginning if nothing is selected')
        bar.addWidget(self.before_action_button)
        self.action_operation_buttons=[
            B('Duplicate',self.duplicate,'quiet'),
            B('↑',lambda:self.move_action(-1),'quiet'),
            B('↓',lambda:self.move_action(1),'quiet'),
            B('Delete',self.delete_selected,'warning'),
            B('Select all',self.select_all,'quiet'),
        ]
        for button in self.action_operation_buttons:bar.addWidget(button)
        low.addLayout(bar)
        self.table=ActionTable(0,5)
        self.table.setHorizontalHeaderLabels(['STEP','TYPE','ACTION / TEXT','DELAY','ACTIVE'])
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_action_context_menu)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch)
        for ix,width in [(0,55),(1,110),(3,100),(4,75)]:
            self.table.setColumnWidth(ix,width)
            self.table.horizontalHeader().setSectionResizeMode(ix,QHeaderView.Fixed)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        self.table.actionsDropped.connect(self.reorder_dragged_actions)
        self.table.setToolTip('Drag rows to reorder; right-click a selected row to edit mouse speed or other selected actions.')
        low.addWidget(self.table,1)
        # V9: cohesive toolbar. Section captions sit ABOVE their controls,
        # avoiding nested boxed labels. It scrolls horizontally only on narrow
        # displays; the action table continues to use all remaining height.
        toolbar=F('replayToolbar')
        toolbar_layout=H(toolbar,(14,9,14,9),14)
        toolbar_content=QWidget()
        toolbar_content.setObjectName('toolbarContent')
        commands=H(toolbar_content,(0,0,0,0),13)

        def toolbar_group(caption):
            group=QWidget();group.setObjectName('toolbarGroup')
            column=V(group,(0,0,0,0),5)
            column.addWidget(L(caption,'toolbarCaption'))
            commands.addWidget(group)
            return column

        def toolbar_separator():
            line=F('toolbarDivider')
            line.setFixedSize(1,38)
            commands.addWidget(line,0,Qt.AlignVCenter)

        timing=toolbar_group('TIMING  ·  GAP')
        timing_controls=H(spacing=7)
        self.uniform=GapInput(value=0.80, minimum=0, maximum=3600, step=0.10)
        self.uniform.setFixedWidth(116)
        self.uniform.setToolTip('Pause between actions, in seconds · Up/Down adjusts by 0.10')
        timing_controls.addWidget(self.uniform)
        self.uniform_apply=B('Apply to all',self.uniform_all,'toolbarApply')
        self.uniform_apply.setObjectName('toolbarApply')
        self.uniform_apply.setMinimumWidth(113)
        timing_controls.addWidget(self.uniform_apply)
        timing.addLayout(timing_controls)

        toolbar_separator()
        cursor_group=toolbar_group('MOUSE PATH')
        self.global_mode=QComboBox()
        self.global_mode.setObjectName('toolbarInput')
        self.global_mode.setFixedWidth(122)
        self.global_mode.addItems(['Smooth','Straight','Gentle','Original'])
        self.global_mode.setToolTip('Global cursor movement style used during replay')
        self.global_mode.currentTextChanged.connect(lambda v:self.set_cursor_mode(v.lower()))
        cursor_group.addWidget(self.global_mode)

        mouse_speed_group=toolbar_group('MOUSE SPEED')
        self.mouse_speed=QComboBox()
        self.mouse_speed.setObjectName('toolbarInput')
        self.mouse_speed.setFixedWidth(106)
        self.mouse_speed.addItems(['Normal','Fast','Slow','Instant'])
        self.mouse_speed.setCurrentText(self.project.mouse_speed_mode.title())
        self.mouse_speed.setToolTip('Change mouse travel speed independently of action delays. Instant clicks move directly; drags keep a minimal travel time.')
        self.mouse_speed.currentTextChanged.connect(lambda v:self.set_mouse_speed(v.lower()))
        mouse_speed_group.addWidget(self.mouse_speed)

        typing_group=toolbar_group('TYPING STYLE')
        self.global_typing=QComboBox()
        self.global_typing.setObjectName('toolbarInput')
        self.global_typing.setFixedWidth(117)
        self.global_typing.addItems(['Original','Smooth','Instant'])
        self.global_typing.setToolTip('Original: recorded rhythm · Smooth: steady typing · Instant: no intentional typing delay')
        self.global_typing.currentTextChanged.connect(lambda v:self.set_typing_mode(v.lower()))
        typing_group.addWidget(self.global_typing)

        center_group=toolbar_group('CURSOR START')
        self.play_center=QPushButton('Center cursor')
        self.play_center.setObjectName('toolbarToggle')
        self.play_center.setCheckable(True)
        self.play_center.setIcon(vector_icon('target','#B2C4F2',16))
        self.play_center.setIconSize(QSize(15,15))
        self.play_center.setChecked(str(self.settings.value('play_center','true')).lower()=='true')
        self.play_center.setToolTip('Move cursor to the selected target center before playback')
        self.play_center.toggled.connect(lambda v:self.settings.setValue('play_center',v))
        center_group.addWidget(self.play_center)

        auto_group=toolbar_group('READINESS')
        self.auto_wait_toggle=QPushButton('Adaptive wait')
        self.auto_wait_toggle.setObjectName('toolbarToggle')
        self.auto_wait_toggle.setCheckable(True)
        self.auto_wait_toggle.setChecked(self.project.adaptive_wait)
        self.auto_wait_toggle.setToolTip('After clicks and navigation keys, briefly wait for visible changes to settle. Not a guarantee of browser/network readiness.')
        self.auto_wait_toggle.toggled.connect(self.set_adaptive_wait)
        auto_group.addWidget(self.auto_wait_toggle)

        speed_group=toolbar_group('PLAYBACK SPEED')
        self.speed=QComboBox()
        self.speed.setObjectName('toolbarInput')
        self.speed.addItems(['0.5×','0.75×','1×','1.25×','1.5×','2×','3×'])
        self.speed.setCurrentText('1×')
        self.speed.setFixedWidth(87)
        speed_group.addWidget(self.speed)

        commands.addStretch(1)
        estimate_group=toolbar_group('ESTIMATED REPLAY')
        self.duration_label=L('0.0 s','toolbarEstimate')
        estimate_group.addWidget(self.duration_label)
        self.speed.currentTextChanged.connect(lambda _value:self._metrics())
        toolbar_layout.addWidget(toolbar_content,1)
        # Keep all presets accessible instead of allowing them to overlap.
        # The scroll bar only appears on small-window sizes or high-DPI fonts.
        self.toolbar_scroll=QScrollArea()
        self.toolbar_scroll.setObjectName('toolbarScroll')
        self.toolbar_scroll.setWidgetResizable(True)
        self.toolbar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.toolbar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.toolbar_scroll.setFrameShape(QFrame.NoFrame)
        self.toolbar_scroll.setSizePolicy(toolbar.sizePolicy().horizontalPolicy(),toolbar.sizePolicy().verticalPolicy())
        self.toolbar_scroll.setWidget(toolbar)
        self.toolbar_scroll.setFixedHeight(94)
        low.addWidget(self.toolbar_scroll)
        body.addWidget(lower)
        self.editor_split=body
        self.preview_panel=upper
        self.preview_mode='hidden'
        upper.setVisible(False)
        body.setSizes([150,700]);body.setStretchFactor(0,1);body.setStretchFactor(1,7)
        foot=QWidget();ft=H(foot,(17,8,17,8),5)
        self.status_line=L('Ready to capture','muted');ft.addWidget(self.status_line,1)
        self.save_state=L('Unsaved','muted');ft.addWidget(self.save_state)
        root.addWidget(foot)

    def _build_shortcuts(self):
        for hotkey,callback in [('Ctrl+S',self.save),('Ctrl+O',self.open_project),('Ctrl+N',self.new_project)]:
            action=QAction(self)
            action.setShortcut(QKeySequence(hotkey))
            action.triggered.connect(callback)
            self.addAction(action)
        shortcut=QShortcut(QKeySequence('Delete'),self.table)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self.delete_selected)
        self.delete_shortcut=shortcut

    def busy(self):
        return bool(self.pending_mode) or self.timer.isActive() or self.recorder.active or bool(self.player and self.player.isRunning())

    def notice(self,message):
        self.status_line.setText(message)
        self.dock.setToolTip(message[:160])

    def _rename(self):
        name=self.name.text().strip() or 'Untitled workflow'
        if name!=self.project.name:
            self.project.name=name
            self.dirty()

    def dirty(self):
        self.is_dirty=True
        self.save_state.setText('● Unsaved changes')
        self._metrics()

    def _metrics(self):
        duration=0.0
        for a in self.project.actions:
            if not a.enabled:continue
            duration+=a.delay
            if a.kind=='wait' and a.wait_mode!='duration':duration+=min(a.wait_timeout,5.0)  # conditional estimate only
            if a.kind in ('click','drag'):duration+=a.path_duration*MOUSE_SPEED_FACTORS[effective_mouse_speed(a,self.project.mouse_speed_mode)]
            if a.kind=='type':
                policy=effective_typing_speed(a,self.project.global_typing_mode)
                if policy=='original':
                    duration+=(a.char_timings[-1] if len(a.char_timings)==len(a.text) and a.char_timings
                               else len(a.text)*a.char_delay)
                elif policy!='instant':
                    duration+=len(a.text)*a.char_delay*TYPING_SPEED_FACTORS.get(policy,1.0)
        multiplier=float(self.speed.currentText().replace('×','')) if self.speed.currentText() else 1.0
        self.duration_label.setText(f'{duration/max(multiplier,0.01):.1f} s')
        count=len(self.project.actions)
        selected=len(self._rows())
        self.count_label.setText(f'{count} steps  ·  {selected} selected' if selected else f'{count} steps')
        self.save_state.setText('● Unsaved changes' if self.is_dirty else (self.project_path.name if self.project_path else 'Not saved'))
        self.setWindowTitle(f"TakePath {__version__} — {self.project.name}{' *' if self.is_dirty else ''}")

    def set_adaptive_wait(self, enabled):
        if self.busy():return
        enabled=bool(enabled)
        if self.project.adaptive_wait != enabled:
            self.project.adaptive_wait=enabled
            self.dirty()

    def _rows(self):
        return sorted({index.row() for index in self.table.selectedIndexes()})

    def clear_action_selection(self):
        if not self.updating and self._rows():
            self.table.clearSelection()

    @staticmethod
    def _inside_widget(widget, ancestor):
        return widget is ancestor or ancestor.isAncestorOf(widget)

    def _click_within(self, widget, area, event):
        # Qt can deliver the same mouse press to multiple widgets while
        # propagating it up the parent hierarchy. Use the actual cursor
        # location too, not only the event receiver's widget ancestry.
        if self._inside_widget(widget, area):
            return True
        if area.isVisible():
            local = area.mapFromGlobal(event.globalPosition().toPoint())
            return area.rect().contains(local)
        return False

    def _inspector_field_hit(self, obj, event):
        # Preserve the selected action for ALL inspector interactions:
        # timing spinboxes, their nested line edits/arrows, checkboxes,
        # combos, text editors, sliders, scroll bars, and readable labels.
        # Checking just the receiver's geometry is not enough when Qt
        # propagates a child press to its parent widget.
        interactive=(QAbstractButton, QAbstractSpinBox, QComboBox, QLineEdit,
                     QTextEdit, QAbstractItemView, QScrollBar, QLabel)
        def field_or_label(widget):
            while widget is not None and widget is not self.inspector_panel:
                if isinstance(widget, interactive):
                    return True
                widget=widget.parentWidget()
            return False
        if self._inside_widget(obj, self.inspector_panel) and field_or_label(obj):
            return True
        global_point=event.globalPosition().toPoint()
        hit=QApplication.widgetAt(global_point)
        if hit is not None and self._inside_widget(hit, self.inspector_panel):
            return field_or_label(hit)
        inside=self.inspector_panel.mapFromGlobal(global_point)
        if self.inspector_panel.rect().contains(inside):
            return field_or_label(self.inspector_panel.childAt(inside))
        return False

    def _editor_control_hit(self, obj, event):
        """Identify real controls by cursor position, including nested inputs.

        A click on the timing GapInput may be propagated to the toolbar or
        even the main window; checking only the receiving widget caused the
        selected action to be cleared while the user adjusted a setting.
        """
        interactive=(QAbstractButton, QAbstractSpinBox, QComboBox, QLineEdit,
                     QTextEdit, QAbstractItemView, QScrollBar, QLabel)
        # Use the actual widget at the mouse coordinates first, then the
        # event receiver. All parents of nested line-edit/spin controls
        # still count as interactions with an editing widget.
        actual=QApplication.widgetAt(event.globalPosition().toPoint())
        for source in (actual, obj):
            widget=source
            while isinstance(widget, QWidget) and widget is not self:
                if isinstance(widget, interactive) and self._inside_widget(widget, self):
                    return True
                widget=widget.parentWidget()
        return False

    def eventFilter(self, obj, event):
        # Keep selection for every real editor control, including all
        # bottom playback settings. Clear only on genuinely empty surfaces.
        # Hit-testing actual mouse coordinates protects against Qt bubbling
        # a child input event to its parent container.
        if (event.type() == QEvent.MouseButtonPress and
                isinstance(obj, QWidget) and self.isVisible() and
                hasattr(self, 'table') and self._rows() and
                self._inside_widget(obj, self)):
            if self._click_within(obj, self.table, event):
                viewport=self.table.viewport()
                point=viewport.mapFromGlobal(event.globalPosition().toPoint())
                if viewport.rect().contains(point) and not self.table.indexAt(point).isValid():
                    self.clear_action_selection()
                return super().eventFilter(obj,event)
            if self._click_within(obj, self.inspector_panel, event):
                if not self._inspector_field_hit(obj, event):
                    self.clear_action_selection()
                return super().eventFilter(obj,event)
            if self._click_within(obj, self.toolbar_scroll, event):
                if not self._editor_control_hit(obj, event):
                    self.clear_action_selection()
                return super().eventFilter(obj,event)
            if self._editor_control_hit(obj, event):
                return super().eventFilter(obj,event)
            protected=[self.add_action_button, self.before_action_button,
                       self.rail_add_button, self.rail_delete_button,
                       self.canvas]
            protected.extend(self.action_operation_buttons)
            if not any(self._click_within(obj,w,event) for w in protected):
                self.clear_action_selection()
        return super().eventFilter(obj,event)

    @staticmethod
    def _action_table_label(action):
        # Surface overrides in the action list; inherited speed is indicated
        # by the global Mouse Speed control below the timeline.
        mouse=(f"  ·  Mouse: {action.mouse_speed_override.title()}"
               if action.kind in ('click','drag','scroll')
               and action.mouse_speed_override != 'inherit' else "")
        typing=(f"  ·  Typing: {action.typing_speed_override.title()}"
                if action.kind == 'type' and action.typing_speed_override!='inherit' else "")
        return action.label()+mouse+typing

    def set_selected_mouse_speed(self, mode, rows=None):
        """Apply one override to selected pointer actions, including multi-select."""
        if self.busy() or mode not in ACTION_MOUSE_SPEED_MODES:
            return
        rows=self._rows() if rows is None else sorted(set(rows))
        targets=[self.project.actions[i] for i in rows
                 if 0<=i<len(self.project.actions)
                 and self.project.actions[i].kind in ('click','drag','scroll')]
        changed=[a for a in targets if a.mouse_speed_override!=mode]
        if not changed:
            return
        for action in changed:
            action.mouse_speed_override=mode
        self.dirty()
        self.refresh({self.project.actions[i].id for i in rows
                      if 0<=i<len(self.project.actions)})
        message=('Using global mouse speed' if mode=='inherit'
                 else f'{mode.title()} mouse travel')
        self.notice(f'{message} for {len(changed)} action(s).')

    def set_selected_enabled(self, enabled, rows=None):
        if self.busy():return
        rows=self._rows() if rows is None else sorted(set(rows))
        targets=[self.project.actions[i] for i in rows
                 if 0<=i<len(self.project.actions)]
        changed=[a for a in targets if a.enabled!=bool(enabled)]
        if not changed:return
        for a in changed:a.enabled=bool(enabled)
        self.dirty()
        self.refresh({a.id for a in targets})
        self.notice(f'{"Enabled" if enabled else "Disabled"} {len(changed)} action(s).')

    def set_selected_typing_speed(self, mode, rows=None):
        """Only Type actions receive typing overrides; never secure values."""
        if self.busy() or mode not in ACTION_TYPING_SPEED_MODES:
            return
        rows=self._rows() if rows is None else sorted(set(rows))
        candidates=[self.project.actions[i] for i in rows
                    if 0<=i<len(self.project.actions)
                    and self.project.actions[i].kind=='type']
        changed=[a for a in candidates if a.typing_speed_override != mode]
        if not changed:return
        for a in changed:a.typing_speed_override=mode
        self.dirty()
        self.refresh({self.project.actions[i].id for i in rows
                      if 0<=i<len(self.project.actions)})
        self.notice(f'Typing speed: {mode.title()} for {len(changed)} action(s).')

    def set_selected_wait_duration(self, seconds, rows=None):
        if self.busy() or seconds not in (1.0,3.0,5.0,10.0):
            return
        rows=self._rows() if rows is None else sorted(set(rows))
        targets=[self.project.actions[i] for i in rows
                 if 0<=i<len(self.project.actions)
                 and self.project.actions[i].kind=='wait'
                 and self.project.actions[i].wait_mode=='duration']
        changed=[a for a in targets if a.delay!=seconds]
        if not changed:return
        for a in changed:a.delay=seconds
        self.dirty()
        self.refresh({self.project.actions[i].id for i in rows
                      if 0<=i<len(self.project.actions)})
        self.notice(f'Fixed wait: {seconds:g}s for {len(changed)} action(s).')

    def build_action_context_menu(self, pos):
        """Context-sensitive actions for the exact selected action types."""
        if self.busy():return None
        hit=self.table.indexAt(pos)
        if not hit.isValid():return None
        row=hit.row()
        selected=self._rows()
        if row not in selected:
            self.table.clearSelection()
            self.table.selectRow(row)
            selected=[row]
        selected=sorted(set(selected))
        picked=[self.project.actions[i] for i in selected
                if 0<=i<len(self.project.actions)]
        mouse_actions=[a for a in picked if a.kind in ('click','drag','scroll')]
        typed=[a for a in picked if a.kind=='type']
        timed=[a for a in picked if a.kind=='wait' and a.wait_mode=='duration']

        menu=ActionContextMenu(self.table)
        title=menu.addAction(f'{len(selected)} selected action(s)')
        title.setEnabled(False)
        menu.addSeparator()

        # Do not show mouse/typing controls for unrelated action types.
        if mouse_actions:
            mouse=menu.addMenu('Mouse speed')
            modes=[('Use global speed','inherit'),('Instant','instant'),
                   ('Fast','fast'),('Normal','normal'),('Slow','slow')]
            distinct={a.mouse_speed_override for a in mouse_actions}
            for label,mode in modes:
                action=mouse.addAction(label + (
                    f" ({self.project.mouse_speed_mode.title()})"
                    if mode=='inherit' else ''))
                action.setCheckable(True)
                action.setChecked(distinct=={mode})
                action.triggered.connect(
                    lambda _checked=False,chosen=mode,rows=tuple(selected):
                        self.set_selected_mouse_speed(chosen,rows))

        if typed:
            typing=menu.addMenu('Typing speed')
            modes=[('Use global typing','inherit'),('Original rhythm','original'),
                   ('Normal','normal'),('Fast','fast'),('Slow','slow'),('Instant','instant')]
            distinct={a.typing_speed_override for a in typed}
            for label,mode in modes:
                action=typing.addAction(label+(
                    f" ({self.project.global_typing_mode.title()})"
                    if mode=='inherit' else ''))
                action.setCheckable(True)
                action.setChecked(distinct=={mode})
                action.triggered.connect(
                    lambda _checked=False,chosen=mode,rows=tuple(selected):
                        self.set_selected_typing_speed(chosen,rows))

        if timed:
            pauses=menu.addMenu('Wait duration')
            for seconds in (1.0,3.0,5.0,10.0):
                action=pauses.addAction(f'{seconds:g} seconds')
                action.setCheckable(True)
                action.setChecked(all(a.delay==seconds for a in timed))
                action.triggered.connect(
                    lambda _checked=False,value=seconds,rows=tuple(selected):
                        self.set_selected_wait_duration(value,rows))

        if mouse_actions or typed or timed:
            menu.addSeparator()
        enable=menu.addAction('Enable selected')
        disable=menu.addAction('Disable selected')
        enable.setEnabled(any(not a.enabled for a in picked))
        disable.setEnabled(any(a.enabled for a in picked))
        enable.triggered.connect(
            lambda _checked=False,rows=tuple(selected):self.set_selected_enabled(True,rows))
        disable.triggered.connect(
            lambda _checked=False,rows=tuple(selected):self.set_selected_enabled(False,rows))
        menu.addSeparator()
        duplicate=menu.addAction('Duplicate selected')
        delete=menu.addAction('Delete selected')
        duplicate.triggered.connect(self.duplicate)
        delete.triggered.connect(self.delete_selected)

        # Native Qt hover and submenu safe-corridor behavior now owns opening
        # and closing; forced hide() during mouse travel made it unusable.
        return menu

    def show_action_context_menu(self, pos):
        menu=self.build_action_context_menu(pos)
        if menu is not None:
            try:
                menu.exec(self.table.viewport().mapToGlobal(pos))
            finally:
                menu.deleteLater()

    def refresh(self, ids=None):
        if ids is None:
            ids={self.project.actions[r].id for r in self._rows() if r<len(self.project.actions)}
        self.updating=True
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.project.actions))
        colors={'wait':'#9BCBFF','click':'#AFB4FF','drag':'#F1A7CE','scroll':'#90BDEB','type':'#7FD7C8','key':'#F1C38A','secure_input':'#FFB978'}
        for i,a in enumerate(self.project.actions):
            values=[f'{i+1:03d}',a.kind.upper(),self._action_table_label(a),f'{a.delay:.2f} s','Yes' if a.enabled else 'No']
            for j,value in enumerate(values):
                cell=QTableWidgetItem(value)
                cell.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
                if j in (0,3,4):cell.setTextAlignment(Qt.AlignCenter)
                if j==1:cell.setForeground(QColor(colors.get(a.kind,'#CDD7E5')))
                elif j in (0,3,4):cell.setForeground(QColor('#95A3B7'))
                if not a.enabled:cell.setForeground(QColor('#697587'))
                self.table.setItem(i,j,cell)
            self.table.setRowHeight(i,40)
        self.table.clearSelection()
        for i,a in enumerate(self.project.actions):
            if a.id in ids:
                self.table.selectRow(i) if len(ids)==1 else self.table.setRangeSelected(
                    self._row_range(i),True)
        self.table.blockSignals(False)
        self.updating=False
        self.canvas.update_project(ids)
        self.frame_hint.setText('Drag a click marker to reposition it' if self.project.preview_jpeg else 'Spatial map · no snapshot saved')
        with QSignalBlocker(self.global_mode):
            self.global_mode.setCurrentText(self.project.cursor_mode.title())
        with QSignalBlocker(self.global_typing):
            self.global_typing.setCurrentText(self.project.global_typing_mode.title())
        with QSignalBlocker(self.mouse_speed):
            self.mouse_speed.setCurrentText(self.project.mouse_speed_mode.title())
        with QSignalBlocker(self.auto_wait_toggle):
            self.auto_wait_toggle.setChecked(self.project.adaptive_wait)
        self._metrics()
        self.selection_changed()
        self.dock.sync()

    def _row_range(self,i):
        from PySide6.QtWidgets import QTableWidgetSelectionRange
        return QTableWidgetSelectionRange(i,0,i,self.table.columnCount()-1)

    def selection_changed(self):
        if self.updating:return
        rows=self._rows()
        ids={self.project.actions[r].id for r in rows if r<len(self.project.actions)}
        self.canvas.selected_ids=ids
        self.canvas.update()
        self._metrics()
        self.inspector_panel.setVisible(True)
        self.inspector_form.setVisible(len(rows)==1)
        self.uniform_apply.setText('Apply to selected' if rows else 'Apply to all')
        if len(rows)!=1:
            self.inspector_title.setText('Multiple selected' if rows else 'Nothing selected')
            self.inspector_info.setText(f'{len(rows)} steps selected. Press Delete selected to remove all at once.' if rows else 'Choose a step below or click its marker on the preview.')
            return
        a=self.project.actions[rows[0]]
        self.inspector_title.setText(a.kind.replace('_',' ').title()+' action')
        self.inspector_info.setText(a.label()[:120])
        self.updating=True
        controls=[(self.enable,'setChecked',a.enabled),(self.delay,'setValue',a.delay),
                  (self.edit_text,'setPlainText',a.text),
                  (self.char_delay,'setValue',a.char_delay),(self.key,'setText',a.key),
                  (self.wait_value,'setText',a.wait_value),(self.wait_timeout,'setValue',a.wait_timeout),
                  (self.mouse_button,'setCurrentIndex',max(0,self.mouse_button.findData(a.button))),(self.motion_time,'setValue',a.path_duration),
                  (self.scroll_x,'setValue',a.dx),(self.scroll_y,'setValue',a.dy)]
        controls.extend((widget,'setValue',getattr(a,key)) for key,widget in self.coords.items())
        for widget,method,value in controls:
            with QSignalBlocker(widget):getattr(widget,method)(value)
        self.text_container.setVisible(a.kind=='type')
        self.secure_container.setVisible(a.kind=='secure_input')
        if a.kind=='secure_input':
            with QSignalBlocker(self.secure_mode):
                self.secure_mode.setCurrentIndex(max(0,self.secure_mode.findData(a.secure_mode)))
            self.secret_reveal.setChecked(False)
            self.secret_edit.clear()   # only review on explicit request
            self._secure_status(a)
        self.key_container.setVisible(a.kind=='key')
        self.wait_container.setVisible(a.kind=='wait')
        with QSignalBlocker(self.wait_mode):
            self.wait_mode.setCurrentIndex(max(0,self.wait_mode.findData(a.wait_mode)))
        self._sync_wait_properties(a)
        self.pointer_container.setVisible(a.kind in ('click','drag','scroll'))
        self.scroll_container.setVisible(a.kind=='scroll')
        self.coords['end_x'].setEnabled(a.kind=='drag')
        self.coords['end_y'].setEnabled(a.kind=='drag')
        self.motion_time.setEnabled(a.kind in ('click','drag'))
        self.mouse_button.setEnabled(a.kind in ('click','drag'))
        self.updating=False

    def _sync_wait_properties(self, action):
        fixed = action.kind=='wait' and action.wait_mode=='duration'
        self.delay_caption.setText('WAIT DURATION' if fixed else 'PAUSE BEFORE ACTION')
        needs_name = action.kind=='wait' and action.wait_mode in ('target_title','active_title','control_name')
        conditional = action.kind=='wait' and not fixed
        self.wait_value_caption.setVisible(needs_name)
        self.wait_value.setVisible(needs_name)
        self.wait_timeout_caption.setVisible(conditional)
        self.wait_timeout.setVisible(conditional)
        if fixed:
            self.wait_help.setText('Pause for the duration above, then continue. F8 stops playback. No title or control name is needed.')
        else:
            self.wait_help.setText('Continue only when the selected condition matches; stop on timeout.')

    def _selected_secure(self):
        rows=self._rows()
        if len(rows)!=1:return None
        action=self.project.actions[rows[0]]
        return action if action.kind=='secure_input' else None

    def _secret_key(self,a):
        return a.secure_ref if valid_reference(a.secure_ref) else a.id

    def _secure_status(self,a):
        self.secure_autofill.setVisible(a.secure_mode=='auto')
        if a.secure_mode!='auto':return
        session=self._secret_key(a) in self.session_secrets
        persisted=False
        if a.secure_ref and self.credential_store:
            try:persisted=self.credential_store.get(a.secure_ref) is not None
            except CredentialError:pass
        self.secret_status.setText('● Saved in Windows Credential Manager' if persisted else
                                   '● Ready for this session' if session else
                                   '○ Missing · will ask before replay')

    def _change_secure_mode(self,index):
        if self.updating:return
        mode=self.secure_mode.currentData()
        self._set('secure_mode',mode)
        a=self._selected_secure()
        if a:self._secure_status(a)

    def convert_to_secure(self):
        if self.busy():return
        rows=self._rows()
        if len(rows)!=1:return
        a=self.project.actions[rows[0]]
        if a.kind!='type':return
        answer=QMessageBox.warning(self,'Convert to secure input',
            'Replace this text with a secure marker? Its captured text will be discarded. '
            'If this workflow was previously saved, delete or replace older copies that may contain the text.',
            QMessageBox.Yes | QMessageBox.Cancel,QMessageBox.Cancel)
        if answer!=QMessageBox.Yes:return
        a.kind='secure_input'; a.text=''; a.key='enter'; a.secure_mode='auto'; a.secure_ref=''
        self.dirty();self.refresh({a.id})

    def set_secure_value(self):
        if self.busy():return
        a=self._selected_secure()
        if a is None:return
        try:secret=validate_password(self.secret_edit.text())
        except ValueError as exc:
            QMessageBox.warning(self,'Secure input',str(exc));return
        if self.secret_remember.isChecked():
            if not self.credential_store:
                QMessageBox.warning(self,'Secure storage unavailable',
                    'Windows Credential Manager is unavailable. Uncheck Save securely to use session-only storage.')
                return
            ref=a.secure_ref if valid_reference(a.secure_ref) else uuid.uuid4().hex
            try:self.credential_store.set(ref,secret)
            except (CredentialError,ValueError) as exc:
                QMessageBox.warning(self,'Secure storage failed',str(exc));return
            a.secure_ref=ref
            self.session_secrets.pop(a.id,None)
            self.session_secrets.pop(ref,None)
            self.dirty()
        else:
            self.session_secrets[self._secret_key(a)]=secret
        self.secret_reveal.setChecked(False)
        self.secret_edit.clear()
        self._secure_status(a)
        self.notice('Secure input configured; its value is not stored in the project.')

    def review_secure_value(self):
        """User-triggered review only: never automatically unmask saved secrets."""
        if self.busy():return
        a=self._selected_secure()
        if a is None:return
        key=self._secret_key(a)
        secret=self.session_secrets.get(key)
        if secret is None and a.secure_ref and self.credential_store:
            try:secret=self.credential_store.get(a.secure_ref)
            except CredentialError as exc:
                _warn_in_front(self._visible_dialog_parent(),'Secure value unavailable',str(exc))
                return
        if secret is None:
            self.notice('No configured value to review. Enter a new one or supply it during replay.')
            return
        self.secret_reveal.setChecked(False)
        self.secret_edit.setText(secret)
        self.notice('Secure value loaded masked. Use the eye control if you want to verify it.')

    def forget_secure_value(self):
        if self.busy():return
        a=self._selected_secure()
        if a is None:return
        keys={a.id,self._secret_key(a)}
        if a.secure_ref and self.credential_store:
            try:self.credential_store.delete(a.secure_ref)
            except CredentialError as exc:
                QMessageBox.warning(self,'Could not remove stored value',str(exc));return
        for key in keys:self.session_secrets.pop(key,None)
        self.secret_reveal.setChecked(False)
        self.secret_edit.clear()
        self._secure_status(a)
        self.notice('Removed the saved/session value. This action will ask before replay.')

    def _set(self,key,value):
        if self.updating or self.busy():return
        rows=self._rows()
        if len(rows)!=1:return
        a=self.project.actions[rows[0]]
        if getattr(a,key)==value:return
        setattr(a,key,value)
        self.dirty()
        self.table.item(rows[0],2).setText(self._action_table_label(a))
        self.table.item(rows[0],3).setText(f'{a.delay:.2f} s')
        self.table.item(rows[0],4).setText('Yes' if a.enabled else 'No')
        self.inspector_info.setText(a.label()[:120])
        if key=='wait_mode':self._sync_wait_properties(a)
        self.canvas.update()

    def select_index(self,index):
        if 0<=index<self.table.rowCount():
            self.table.selectRow(index)
            self.table.scrollToItem(self.table.item(index,0))

    def move_canvas_point(self,index,x,y):
        if self.busy() or not 0<=index<len(self.project.actions):return
        a=self.project.actions[index]
        if a.kind=='drag':
            a.end_x,a.end_y=x,y
        else:
            a.x,a.y=x,y
        self.dirty()
        self.table.item(index,2).setText(a.label())
        if index in self._rows():self.selection_changed()
        self.canvas.update()

    def add_action(self, before=False):
        from PySide6.QtWidgets import QInputDialog
        if self.busy():return
        kind,ok=QInputDialog.getItem(self,'Add step','Action type',['click','type','key','scroll','drag','secure_input','wait'],0,False)
        if not ok:return
        rows=self._rows()
        pos=(min(rows) if rows else 0) if before else (max(rows)+1 if rows else len(self.project.actions))
        a=Action(kind=kind)
        if kind=='wait':
            a.wait_mode='duration'
            a.delay=3.0
        self.project.actions.insert(pos,a)
        self.dirty();self.refresh({a.id})

    def duplicate(self):
        if self.busy():return
        rows=self._rows()
        if not rows:return
        clones=[replace(self.project.actions[r],id=uuid.uuid4().hex,raw_path=[p[:] for p in self.project.actions[r].raw_path]) for r in rows]
        pos=rows[-1]+1
        self.project.actions[pos:pos]=clones
        self.dirty();self.refresh({c.id for c in clones})

    def delete_selected(self):
        if self.busy():return
        rows=self._rows()
        if not rows:return
        ids={self.project.actions[r].id for r in rows}
        self.project.actions=remove_actions(self.project.actions,ids)
        self.dirty();self.refresh(set())
        self.notice(f'Removed {len(rows)} selected action(s).')

    def reorder_dragged_actions(self, source_rows, before_row):
        if self.busy():
            return
        if not source_rows:
            return
        selected_ids={self.project.actions[i].id for i in source_rows
                      if 0<=i<len(self.project.actions)}
        try:
            reordered=reorder_actions(self.project.actions, source_rows, before_row)
        except ValueError:
            return
        if all(a is b for a,b in zip(self.project.actions, reordered)):
            return
        self.project.actions=reordered
        self.dirty()
        self.refresh(selected_ids)
        self.notice(f'Moved {len(source_rows)} action(s). Drag rows again to adjust the order.')

    def move_action(self,direction):
        if self.busy():return
        rows=self._rows()
        if len(rows)!=1:return
        i=rows[0];j=i+direction
        if j<0 or j>=len(self.project.actions):return
        self.project.actions[i],self.project.actions[j]=self.project.actions[j],self.project.actions[i]
        self.dirty();self.refresh({self.project.actions[j].id})

    def select_all(self):
        self.table.selectAll()

    def uniform_all(self):
        if self.busy():return
        rows=self._rows()
        targets=[self.project.actions[i] for i in rows] if rows else self.project.actions
        if not targets:return
        for a in targets:a.delay=self.uniform.value()
        self.dirty();self.refresh({a.id for a in targets} if rows else set())
        self.notice(f'Applied {self.uniform.value():.2f} sec gap to {len(targets)} step(s).')

    def set_mouse_speed(self,mode):
        if mode not in MOUSE_SPEED_FACTORS or self.project.mouse_speed_mode==mode:return
        self.project.mouse_speed_mode=mode
        self.dirty()
        self.notice(f'Mouse travel speed: {mode.title()}')

    def set_typing_mode(self,mode):
        if mode not in ('original','smooth','instant') or mode==self.project.global_typing_mode:return
        self.project.global_typing_mode=mode
        self.settings.setValue('typing_mode',mode)
        self.dirty()
        self.notice(f'Global typing: {mode.title()}')

    def set_cursor_mode(self,mode):
        if mode not in ('smooth','original','straight','gentle') or self.project.cursor_mode==mode:return
        self.project.cursor_mode=mode
        self.settings.setValue('cursor_mode',mode)
        self.dirty()
        self.canvas.update()
        with QSignalBlocker(self.global_mode):self.global_mode.setCurrentText(mode.title())
        self.dock.sync()

    def preview_menu(self):
        menu=QMenu(self)
        for mode,label in [('hidden','Hide map'),('compact','Compact map'),('expanded','Large map')]:
            act=menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(self.preview_mode==mode)
            act.triggered.connect(lambda _checked=False, m=mode:self.set_preview_mode(m))
        menu.exec(self.preview_choice.mapToGlobal(QPoint(0,self.preview_choice.height()+4)))

    def set_preview_mode(self, mode):
        if mode not in ('hidden','compact','expanded'):
            return
        self.preview_mode=mode
        self.preview_panel.setVisible(mode!='hidden')
        self.preview_choice.setText({'hidden':'Show action map',
                                     'compact':'Map: compact',
                                     'expanded':'Map: large'}[mode])
        if mode!='hidden':
            # Give the action table priority. A manual splitter drag can still
            # resize the preview freely between these presets.
            QTimer.singleShot(0, lambda: self.editor_split.setSizes(
                [205, max(420,self.editor_split.height()-205)] if mode=='compact' else
                [max(400,int(self.editor_split.height()*.65)), max(180,int(self.editor_split.height()*.35))]
            ))

    def fullscreen_preview(self):
        dialog=QDialog(self)
        dialog.setWindowTitle('Full screen preview · Esc to close')
        lay=V(dialog,(12,12,12,12),5)
        scene=SceneCanvas(self,dialog)
        scene.update_project({self.project.actions[r].id for r in self._rows()})
        def pick(i):
            self.select_index(i)
            scene.selected_ids = {self.project.actions[i].id}
            scene.update()
        scene.picked.connect(pick)
        scene.moved.connect(lambda i,x,y:(self.move_canvas_point(i,x,y),scene.update()))
        lay.addWidget(scene)
        dialog.showFullScreen()
        dialog.exec()
        self.canvas.update()

    def clear_preview(self):
        if not self.project.preview_jpeg:return
        self.project.preview_jpeg=''
        self.dirty();self.refresh()
        self.notice('Still image removed from this workflow.')

    def _visible_dialog_parent(self):
        # When the editor is hidden, parenting a dialog to it makes Windows
        # place the dialog behind the recorded app. The dock is the real owner.
        return self if self.isVisible() and not self.isMinimized() else self.dock

    def _discard_ok(self):
        if not self.is_dirty:return True
        ans=_ask_in_front(self._visible_dialog_parent(),'Unsaved changes',
            'Save the current project before continuing?',
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,QMessageBox.Save)
        if ans==QMessageBox.Cancel:return False
        if ans==QMessageBox.Save:return bool(self.save())
        return True

    def new_project(self):
        if self.busy() or not self._discard_ok():return
        self.session_secrets.clear()
        self.prepared_secure.clear()
        self.take_history.clear()
        self.project=Project(cursor_mode=self.settings.value('cursor_mode','smooth'),
                             global_typing_mode=self.settings.value('typing_mode','smooth'))
        self.project_path=None;self.is_dirty=False
        self.name.setText(self.project.name)
        self.refresh(set())
        self.show_dock()

    def open_example(self):
        if self.busy() or not self._discard_ok():return
        try:
            path=Path(__file__).resolve().parent.parent/'examples'/'tutorial_demo.vas.json'
            self.session_secrets.clear()
            self.prepared_secure.clear()
            self.take_history.clear()
            self.project=load_project(path)
            self.project_path=None;self.is_dirty=False
            self.name.setText(self.project.name)
            self.refresh(set())
            self.set_preview_mode('compact' if self.project.preview_jpeg else 'hidden')
            self.show_editor()
        except Exception as e:QMessageBox.critical(self,'Example failed',str(e))

    def open_project(self):
        if self.busy() or not self._discard_ok():return
        path,_=QFileDialog.getOpenFileName(self,'Open workflow',str(Path.home()),'TakePath projects (*.vas.json);;JSON (*.json)')
        if not path:return
        try:
            self.session_secrets.clear()
            self.prepared_secure.clear()
            self.take_history.clear()
            self.project=load_project(path)
            self.project_path=Path(path)
            self.is_dirty=False
            self.name.setText(self.project.name)
            self.refresh(set())
            self.set_preview_mode('compact' if self.project.preview_jpeg else 'hidden')
            self.show_editor()
            self.notice('Project loaded. Review coordinates and app state before replay.')
        except Exception as e:QMessageBox.critical(self,'Open failed',str(e))

    def save(self):
        self._rename()
        if self.project_path is None:
            return self.save_as()
        try:
            save_project(self.project,self.project_path)
            self.is_dirty=False
            self._metrics()
            self.notice('Project saved locally.')
            return True
        except Exception as e:
            QMessageBox.critical(self,'Save failed',str(e))
            return False

    def save_as(self):
        path,_=QFileDialog.getSaveFileName(self._visible_dialog_parent(),'Save workflow',str(Path.home()/'My workflow.vas.json'),
                                           'TakePath projects (*.vas.json)')
        if not path:return False
        if not path.lower().endswith('.vas.json'):
            path=path[:-5]+'.vas.json' if path.lower().endswith('.json') else path+'.vas.json'
        self.project_path=Path(path)
        return self.save()

    def minimize_dock_to_taskbar(self):
        """Show a real Windows taskbar entry instead of hiding in the tray."""
        self._dock_taskbar_minimized=True
        self.dock.hide()
        self.setWindowTitle(f'TakePath {__version__} · Recorder')
        self.showMinimized()

    def changeEvent(self,event):
        super().changeEvent(event)
        if (event.type()==QEvent.WindowStateChange and
                self._dock_taskbar_minimized and not self.isMinimized()):
            QTimer.singleShot(0,self._restore_minimized_dock)

    def _restore_minimized_dock(self):
        if not self._dock_taskbar_minimized:return
        self._dock_taskbar_minimized=False
        self.setWindowTitle(f'TakePath {__version__}')
        self.hide()
        self.dock.show()
        self.dock.sync()

    def show_editor(self):
        if self.busy():return
        self._dock_taskbar_minimized=False
        self.replay_ready=False
        self.prepared_secure.clear()
        self.showMaximized()
        self.raise_()
        self.activateWindow()
        self.dock.hide()

    def show_dock(self):
        self._dock_taskbar_minimized=False
        self.dock.show()
        self.hide()
        self.dock.raise_()
        self.dock.sync()

    def _is_ours(self,hwnd):
        if not hwnd:return True
        return platform_is_ours(hwnd)

    def _arm(self,mode):
        self.pending_mode=mode
        self.show_dock()
        self.left_count=self.dock.countdown_secs
        self.notice(f'Switch to your target application · {self.left_count}s')
        if self.left_count<=0:
            QTimer.singleShot(120,self._begin_pending)
        else:
            self.timer.start()
        self.dock.sync()

    def _tick_countdown(self):
        self.left_count-=1
        if self.left_count>0:
            self.dock.clock.setText(str(self.left_count))
            self.notice(f'Focus your target window · {self.left_count}s remaining')
        else:
            self.timer.stop()
            self._begin_pending()

    def _begin_pending(self):
        if not self.pending_mode:return
        mode=self.pending_mode
        self.pending_mode=''
        hwnd=foreground()
        if self.dock.target_mode=='window' and self.dock.selected_hwnd and usable_window(self.dock.selected_hwnd):
            hwnd=self.dock.selected_hwnd
        if self._is_ours(hwnd):
            # Clicking a frameless dock can focus Studio. Use the last external
            # target only if it still exists, then explicitly restore focus.
            hwnd=self.last_external_hwnd
            if hwnd and usable_window(hwnd):
                if not platform_activate(hwnd):
                    self.notice('Could not focus the target. Click the app and retry playback.')
                    if mode=='play':
                        self.prepared_secure.clear()
                        _warn_in_front(self.dock, 'Cannot start replay',
                            'Could not focus the target application. Bring its window forward and press Play again.')
                    self.dock.sync()
                    return
        if self._is_ours(hwnd) or (mode=='record' and not hwnd):
            self.notice('Not started. Focus the application you want to capture, then retry.')
            if mode=='play':self.prepared_secure.clear()
            self.dock.sync()
            return
        # Explicit window selection wins over whatever currently has focus.
        if self.dock.target_mode=='window' and self.dock.selected_hwnd:
            if not usable_window(self.dock.selected_hwnd):
                self.notice('Selected application was closed. Choose an open window and retry.')
                self.dock.select_window(0,'')
                self.dock.sync();return
            hwnd=self.dock.selected_hwnd
            if not platform_activate(hwnd):
                self.notice('Could not activate the selected window. Bring it forward, then retry.')
                if mode=='play':
                    self.prepared_secure.clear()
                    _warn_in_front(self.dock, 'Cannot start replay',
                        'The selected application could not be focused. Activate it manually and press Play again.')
                self.dock.sync();return
        self.target_hwnd=hwnd
        if mode=='record':
            self.pending_record_scope=self.dock.target_mode
            capture_bounds=self.dock.selected_screen_bounds if self.pending_record_scope=='screen' else None
            if self.dock.center.isChecked():
                try:
                    if capture_bounds:
                        x,y,w,h=capture_bounds
                        platform_center(hwnd, capture_bounds)
                    else:center_cursor(hwnd)
                except Exception as e:self.notice(f'Could not center cursor: {e}')
            if self.recorder.begin(int(self.dock.winId()),target_hwnd=hwnd,scope=self.pending_record_scope,
                                   capture_bounds=capture_bounds,
                                   dock_bounds=[self.dock.x(), self.dock.y(), self.dock.width(), self.dock.height()]):
                self.record_started_at=time.monotonic()
            else:
                self.notice('Recording failed to start. Choose a regular target application.')
        else:
            self._launch_playback(hwnd)
        self.dock.sync()

    def retake(self):
        """Explicit one-click re-record using current target/countdown.

        If called during recording, discard the unfinished take and restart.
        A completed previous take remains recoverable in memory and its
        original saved file is never overwritten automatically.
        """
        if self.recorder.active:
            self.restart_recording=True
            self.recorder.stop()
            return
        if self.busy():return
        self.playback_completed=False
        self.replay_ready=False
        self.prepared_secure.clear()
        self.retake_pending=bool(self.project.actions)
        self.retake_origin_hwnd=self.target_hwnd
        with QSignalBlocker(self.dock.center):
            self.dock.center.setChecked(str(self.settings.value('center','true')).lower()=='true')
        self.notice('Retake armed. Keep the same target and countdown; the old take is preserved until replacement.')
        self._arm('record')

    def restore_previous_take(self):
        """Recover the previous complete recording without disk writes."""
        if self.busy() or not self.take_history.available:return
        if self.is_dirty and self.project.actions:
            answer=_ask_in_front(self._visible_dialog_parent(),'Restore previous take',
                'Replace the current take with the previous one? Unsaved changes in the new take will be lost.',
                QMessageBox.Yes | QMessageBox.No,QMessageBox.No)
            if answer!=QMessageBox.Yes:return
        old=self.take_history.restore()
        self.project=old.project
        self.project_path=old.path
        self.is_dirty=old.dirty
        self.session_secrets=old.session_secrets
        self.target_hwnd=old.target_hwnd
        self.retake_pending=False
        self.playback_completed=False
        self.replay_ready=False
        self.name.setText(self.project.name)
        self.refresh(set())
        self.notice('Previous take restored from memory.')
        self.show_editor()

    def prepare_new_capture(self):
        """The editor's New capture button only opens the dock; never auto-record."""
        if self.busy():
            return
        self.playback_completed=False
        self.replay_ready=False
        self.prepared_secure.clear()
        # Restore the capture preferences when leaving replay-ready mode.
        self.dock.center.setChecked(str(self.settings.value('center','true')).lower()=='true')
        self.dock.set_target(self.settings.value('capture_scope','window'))
        self.show_dock()
        self.notice('Ready for a new capture. Press Record when you are ready.')
        self.dock.sync()

    def start_recording(self):
        if self.busy():return
        if self.project.actions:
            choice=_ask_in_front(self._visible_dialog_parent(),'Replace recording?',
                'Recording replaces the current action list. Save it first if you want to keep it.\n\nStart a new recording?',
                QMessageBox.Yes | QMessageBox.No,QMessageBox.No)
            if choice!=QMessageBox.Yes:return
        self._arm('record')

    def _recording_started(self,title):
        self.notice(f'Recording: {title[:55]} · F8 to finish')
        self.dock.sync()

    def _recording_done(self,actions,target_title,bounds):
        if self.restart_recording:
            self.restart_recording=False
            self.notice('Take discarded. Starting a fresh recording countdown.')
            QTimer.singleShot(200,lambda:self._arm('record'))
            self.dock.sync()
            return
        if not actions and self.retake_pending:
            self.retake_pending=False
            self.notice('Empty retake discarded. Your previous actions are unchanged.')
            self.dock.sync()
            return
        if self.retake_pending:
            self.take_history.capture(self.project,self.project_path,self.is_dirty,self.session_secrets,self.retake_origin_hwnd)
            self.project_path=None  # never overwrite the previous saved take on Save
            self.retake_pending=False
        self.playback_completed=False
        self.session_secrets.clear()
        self.prepared_secure.clear()
        # A still image is captured only after explicit recording stops, not continuously.
        self.project.actions=actions
        self.project.target_mode=self.pending_record_scope
        self.project.target_title=target_title
        self.project.screen_bounds=bounds
        self.project.screen_size=bounds[2:]
        self.project.recorded_window_bounds=(list(self.recorder.recorded_window_bounds)
                                             if self.project.target_mode=='window' else [])
        if self.project.target_mode=='screen' and self.dock.selected_screen_label:
            self.project.target_title=self.dock.selected_screen_label
        self.project.preview_jpeg=''
        self.project.preview_bounds=bounds[:]
        self.dirty()
        self.notice(f'{len(actions)} actions recorded. Preparing visual editor.')
        # Keep target unobscured for screenshot, then automatically open editor.
        self.dock.hide()
        QTimer.singleShot(220,self._complete_recording)

    def _complete_recording(self):
        try:
            encoded,bounds=(get_screen_preview(self.project.screen_bounds) if self.project.target_mode=='screen' else get_window_preview(self.target_hwnd))
            self.project.preview_jpeg=encoded
            self.project.preview_bounds=bounds
        except Exception as e:
            self.notice(f'Actions saved in memory; still preview unavailable: {e}')
        self.refresh({self.project.actions[0].id} if self.project.actions else set())
        if self.project.preview_jpeg:self.set_preview_mode('compact')
        self.showMaximized()
        self.raise_()
        self.activateWindow()
        if self.project.preview_jpeg:self.notice(f'Recorded {len(self.project.actions)} editable steps · captured a still frame.')

    def prepare_replay(self):
        """Editor click stages playback; only dock Play starts the countdown."""
        if self.busy() or not self.project.actions:return
        self.playback_completed=False
        self.replay_ready=True
        # Keep a selected window after recording when still open;
        # otherwise use focused-app replay as in earlier releases.
        if self.project.target_mode=='window' and usable_window(self.target_hwnd):
            self.dock.select_window(self.target_hwnd,title_of(self.target_hwnd))
        elif self.project.target_mode=='screen':
            matched=next(((label,bounds) for label,bounds,_ in screen_entries(QGuiApplication.screens())
                          if list(bounds)==self.project.screen_bounds),None)
            if matched:
                self.dock.select_screen(matched[1],matched[0])
            else:
                self.dock.set_target('screen')
        else:
            self.dock.set_target('window')
        with QSignalBlocker(self.dock.center):
            self.dock.center.setChecked(self.play_center.isChecked())
        self.show_dock()
        self.notice('Replay ready. Switch the target to its starting state, then press Play on the dock. F8 = stop.')
        self.dock.sync()

    def _prepare_secure_values(self):
        """Get every required auto-fill secret before focusing the target app.

        Never store values in Action.text, QSettings, the JSON project, or logs.
        Return False without starting playback if user cancels the prompt.
        """
        available={}
        missing={}
        key_by_action={}
        for index,a in enumerate(self.project.actions):
            if not a.enabled or a.kind!='secure_input' or a.secure_mode!='auto':continue
            key=self._secret_key(a)
            key_by_action[a.id]=key
            if key in available or key in missing:continue
            if key in self.session_secrets:
                available[key]=self.session_secrets[key]
                continue
            secret=None
            if a.secure_ref and self.credential_store:
                try:secret=self.credential_store.get(a.secure_ref)
                except CredentialError:
                    secret=None
            if secret is not None:
                available[key]=secret
            else:
                missing[key]=f'Step {index+1} · Secure input'
        if missing:
            dlg=SecurePreflightDialog(list(missing.items()),self.dock,allow_save=bool(self.credential_store))
            if _foreground_dialog(dlg).exec()!=QDialog.Accepted:return False
            submitted=dlg.submitted()
            for entry in dlg.inputs.values():entry.clear()
            for key,secret,save_on_pc in submitted:
                # A key may be the action's ID if no secure reference exists.
                if save_on_pc and self.credential_store:
                    ref=key if valid_reference(key) and any(a.secure_ref==key for a in self.project.actions) else uuid.uuid4().hex
                    try:self.credential_store.set(ref,secret)
                    except (CredentialError,ValueError) as exc:
                        _warn_in_front(self.dock,'Secure storage failed',str(exc)+'\n\nReplay has not started.')
                        return False
                    for a in self.project.actions:
                        if a.id==key or a.secure_ref==key:
                            a.secure_ref=ref
                            key_by_action[a.id]=ref
                    available[ref]=secret
                    self.dirty()
                else:
                    available[key]=secret
                    self.session_secrets[key]=secret
            dlg.close()
        self.prepared_secure={a_id:available[key] for a_id,key in key_by_action.items() if key in available}
        # A new persistent ref may have been attached above. Ensure it resolves
        # to the same just-provided password for this playback.
        for a in self.project.actions:
            if a.id in key_by_action and a.id not in self.prepared_secure:
                if a.secure_ref and a.secure_ref in available:
                    self.prepared_secure[a.id]=available[a.secure_ref]
        if len(self.prepared_secure)!=len(key_by_action):
            self.prepared_secure.clear()
            _warn_in_front(self.dock,'Missing secure input','Not every secure input was supplied. Playback was cancelled.')
            return False
        return True

    def start_playback(self):
        """Only the replay-ready dock can start playback."""
        if self.busy() or not self.project.actions or not self.replay_ready:return
        self.settings.setValue('play_center',self.dock.center.isChecked())
        with QSignalBlocker(self.play_center):
            self.play_center.setChecked(self.dock.center.isChecked())
        if not self._prepare_secure_values():
            self.notice('Replay cancelled; secure inputs not supplied.')
            self.dock.sync()
            return
        self._arm('play')

    def _launch_playback(self,hwnd):
        self.playback_completed=False
        self.replay_ready=False
        self.player_waiting_for_focus=False
        self.player_waiting_for_ui=False
        self.last_playback_message=''
        self.last_playback_step=-1
        actions=[replace(a,raw_path=[point[:] for point in a.raw_path]) for a in self.project.actions]
        speed=float(self.speed.currentText().replace('×',''))
        self.player=Player(actions,hwnd,speed,self.project.cursor_mode,self.play_center.isChecked(),
                           self,target_mode=self.project.target_mode,secure_values=self.prepared_secure,
                           typing_mode=self.project.global_typing_mode,
                           screen_bounds=self.project.screen_bounds if self.project.target_mode=='screen' else None,
                           recorded_window_bounds=self.project.recorded_window_bounds,
                           adaptive_wait=self.project.adaptive_wait,
                           mouse_speed_mode=self.project.mouse_speed_mode)
        self.prepared_secure={}
        self.player.progress.connect(self._on_progress)
        self.player.finished_result.connect(self._play_done)
        self.player.finished.connect(self._play_thread_done)
        self.player.paused_signal.connect(self._pause_status)
        self.player.focus_waiting.connect(self._focus_wait_status)
        self.player.readiness_waiting.connect(self._readiness_wait_status)
        self.player.adaptive_waiting.connect(self._adaptive_wait_status)
        self.player.secure_input_requested.connect(self._secure_input_prompt)
        self.play_started_at=time.monotonic()
        self.player.start()
        self.notice(f'Replaying {len(actions)} actions · F8 to stop')
        self.dock.sync()

    def _on_progress(self,i):
        self.last_playback_step=i
        # Do not bring the full editor to the front during replay.
        if 0<=i<len(self.project.actions):
            self.status_line.setText(f'Running step {i+1} / {len(self.project.actions)}')
        self.dock.sync()

    def _adaptive_wait_status(self, waiting):
        self.player_waiting_for_ui=bool(waiting)
        if waiting:
            self.notice('Checking whether the interface has visually settled · F8 to stop.')
        self.dock.sync()

    def _readiness_wait_status(self, waiting):
        self.player_waiting_for_focus=bool(waiting)
        if waiting:
            self.notice('Waiting for the selected readiness checkpoint · F8 to stop.')
        else:
            self.notice('Readiness checkpoint completed or ended.')
        self.dock.sync()

    def _focus_wait_status(self, waiting):
        self.player_waiting_for_focus=bool(waiting)
        if waiting:
            self.notice('Waiting briefly for the original target window to regain focus. F8 to stop.')
        else:
            self.notice('Target focus restored; replay can continue.')
        self.dock.sync()

    def _secure_input_prompt(self):
        self.notice('Manual secure input selected: enter it in the target app, then press Continue (F7).')
        self.dock.sync()

    def _pause_status(self,paused):
        if not paused:
            self.notice('Playback resumed')
        elif self.player and self.player.awaiting_secure_input:
            self.notice('Manual input step · continue with F7 when done.')
        else:
            self.notice('Paused · F7 to resume')
        self.dock.sync()

    def toggle_pause(self):
        if self.recorder.active:
            self.recorder.toggle_pause()
            return
        if not self.player or not self.player.isRunning():return
        if self.player.pause_flag.is_set():
            # Bring the original target back into focus before resuming.
            try:platform_activate(self.player.target_hwnd)
            except Exception:pass
        self.player.toggle_pause()

    def _play_done(self,message):
        self.last_playback_message=message
        self.notice(message)
        # The editor is hidden; displaying only its status line conceals errors.

    def _play_thread_done(self):
        self.player_waiting_for_focus=False
        self.player_waiting_for_ui=False
        self.prepared_secure.clear()
        message=getattr(self,'last_playback_message','')
        success=message=='Playback finished successfully.'
        # Completion stays on the final application view; errors return to a
        # replay-ready dock so a corrected workflow can be tried immediately.
        self.playback_completed=success
        # Keep the dock in Play / Retake mode even after a successful replay.
        # Never replace Play with the red Record button without an explicit
        # New Capture / Retake action; that previously caused accidental takes.
        self.replay_ready=bool(self.project.actions)
        self.refresh()
        self.dock.show()
        self.dock.sync()
        if message and not success and 'stopped by user' not in message.lower():
            step=getattr(self,'last_playback_step',-1)+1
            details=f'Step {step} of {len(self.project.actions)}.\n\n{message}\n\nThe editor remains closed; click Open editor to correct the action.'
            _warn_in_front(self.dock,'Replay stopped',details)

    def _record_pause_status(self,paused):
        self.notice('Recording paused · press F7 to continue' if paused else 'Recording resumed')
        self.dock.sync()

    def _heartbeat(self):
        if not hasattr(self,'dock'):return
        try:
            current=foreground()
            if current and not self._is_ours(current):
                self.last_external_hwnd=current
        except Exception:
            pass
        if self.recorder.active:
            self.dock.clock.setText(format_elapsed(self.recorder.elapsed()))
        elif self.player and self.player.isRunning():
            paused_time=(time.monotonic()-self.player.paused_at) if self.player.paused_at else 0
            elapsed=time.monotonic()-self.play_started_at-self.player.pause_accumulated-paused_time
            self.dock.clock.setText(format_elapsed(elapsed))
        elif self.timer.isActive() or self.pending_mode:
            self.dock.clock.setText(str(self.left_count))
        else:
            self.dock.clock.setText('00:00')
        self.dock.sync()

    def stop(self):
        if self.timer.isActive():
            self.timer.stop();self.pending_mode='';self.prepared_secure.clear();self.retake_pending=False;self.notice('Countdown cancelled')
        elif self.pending_mode:
            self.pending_mode='';self.prepared_secure.clear();self.retake_pending=False;self.notice('Countdown cancelled')
        if self.recorder.active:self.recorder.stop()
        if self.player and self.player.isRunning():self.player.cancel()
        self.dock.sync()

    def closeEvent(self,event):
        if self.busy():
            self.stop()
            if self.player and self.player.isRunning():
                self.player.wait(2500)
        if not self._discard_ok():
            event.ignore()
            return
        self.prepared_secure.clear()
        self.session_secrets.clear()
        self.dock.hide()
        if self.tray:self.tray.hide()
        event.accept()
        QApplication.quit()


def run():
    ok, reason = platform_supported()
    if not ok:
        print('TakePath cannot start: ' + reason)
        return 1
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('TakePath.ActionRecorder.1')
    except Exception:
        pass
    app=QApplication(sys.argv)
    app.setApplicationName('TakePath')
    app.setApplicationVersion('1.1.0')
    app.setQuitOnLastWindowClosed(False)  # the only initial window is a Qt.Tool dock
    app.setWindowIcon(app_icon())
    app.setStyle('Fusion')
    app.setStyleSheet(CSS)
    font=app.font();font.setFamily('Segoe UI' if sys.platform=='win32' else ('SF Pro Text' if sys.platform=='darwin' else 'Noto Sans'));font.setPointSize(10);app.setFont(font)
    window=MainWindow()
    window.dock.show()
    return app.exec()
