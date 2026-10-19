"""Desktop editing, shared JSON presets and export of the completed full-size render."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QImage, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QSplitter, QVBoxLayout, QWidget, QComboBox, QApplication,
)

from retroimg.cli import build_parser
from retroimg.presets import list_presets, load_file, preset_directory, save_preset
from .controller import RenderController
from .options import OptionsPanel
from .preview import ImagePane


class MainWindow(QMainWindow):
    def __init__(self, *, presets_dir: Path | None = None):
        super().__init__()
        self.setWindowTitle('RetroIMG')
        self.resize(1380, 850)
        self.setMinimumSize(980, 640)
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(min(1380, max(980, available.width() - 60)),
                         min(850, max(640, available.height() - 80)))
        self.setAcceptDrops(True)
        self.source_path: Path | None = None
        self.result_path: Path | None = None
        self.result_revision = None
        self.presets_dir = presets_dir if presets_dir is not None else preset_directory()
        self.parser = build_parser()
        self.controller = RenderController(self)
        self.options = OptionsPanel()
        self.original = ImagePane('Original', smooth=True)
        self.result = ImagePane('Result')
        self.presets = []
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(14, 12, 14, 12)
        header = QHBoxLayout()
        title = QLabel('RetroIMG')
        title.setStyleSheet('font-size: 22px; font-weight: 600;')
        header.addWidget(title)
        self.file_label = QLabel('Open an image, or drop one here')
        self.file_label.setTextFormat(Qt.TextFormat.PlainText)
        header.addWidget(self.file_label, 1)
        self.open_button = QPushButton('Open image…')
        self.refresh_button = QPushButton('Refresh')
        self.cancel_button = QPushButton('Cancel')
        self.export_button = QPushButton('Export image…')
        self.export_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        for button in (self.open_button, self.refresh_button, self.cancel_button, self.export_button):
            header.addWidget(button)
        layout.addLayout(header)
        presets_bar = QHBoxLayout()
        presets_bar.addWidget(QLabel('Preset'))
        self.preset_box = QComboBox()
        self.preset_box.setPlaceholderText('Choose a preset…')
        self.preset_box.setMinimumWidth(200)
        presets_bar.addWidget(self.preset_box, 1)
        self.apply_preset_button = QPushButton('Apply preset')
        self.load_preset_button = QPushButton('Load file…')
        self.save_preset_button = QPushButton('Save preset…')
        for button in (self.apply_preset_button, self.load_preset_button, self.save_preset_button):
            presets_bar.addWidget(button)
        layout.addLayout(presets_bar)
        body = QSplitter(Qt.Orientation.Horizontal)
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setWidget(self.options)
        settings_scroll.setMinimumWidth(340)
        settings_scroll.setMaximumWidth(460)
        body.addWidget(settings_scroll)
        previews = QSplitter(Qt.Orientation.Horizontal)
        previews.addWidget(self.original)
        previews.addWidget(self.result)
        previews.setSizes([480, 480])
        body.addWidget(previews)
        body.setStretchFactor(1, 1)
        body.setSizes([370, 980])
        layout.addWidget(body, 1)
        status_bar = QHBoxLayout()
        self.status = QLabel('Ready. Fit-to-panel is for composition; use 100% to inspect dithering and CRT patterns.')
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.status.setToolTip(self.status.text())
        status_bar.addWidget(self.status, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedWidth(160)
        progress_policy = self.progress.sizePolicy()
        progress_policy.setRetainSizeWhenHidden(True)
        self.progress.setSizePolicy(progress_policy)
        # Reserve two lines even for short messages, and retain the progress
        # footprint while idle so changing state cannot resize the previews.
        self.status.setFixedHeight(max(self.status.fontMetrics().lineSpacing() * 2,
                                       self.progress.sizeHint().height()))
        self.progress.hide()
        status_bar.addWidget(self.progress)
        layout.addLayout(status_bar)
        self.options.changed.connect(self.update_preview)
        self.controller.ready.connect(self._preview_ready)
        self.controller.failed.connect(self._preview_failed)
        self.controller.busyChanged.connect(self._busy_changed)
        self.open_button.clicked.connect(self._choose_image)
        self.refresh_button.clicked.connect(self.update_preview)
        self.cancel_button.clicked.connect(self.cancel_preview)
        self.export_button.clicked.connect(self._choose_export)
        self.apply_preset_button.clicked.connect(self._apply_selected_preset)
        self.preset_box.currentIndexChanged.connect(
            lambda index: self.apply_preset_button.setEnabled(index >= 0 and self.options.kind.currentData() == 'retro'))
        self.load_preset_button.clicked.connect(self._choose_preset)
        self.save_preset_button.clicked.connect(self._choose_save_preset)
        for label, shortcut, callback in (
            ('Open image', QKeySequence.StandardKey.Open, self._choose_image),
            ('Export image', QKeySequence.StandardKey.Save, self._choose_export),
            ('Refresh', 'F5', self.update_preview),
        ):
            action = QAction(label, self)
            action.setShortcut(shortcut)
            action.triggered.connect(callback)
            self.addAction(action)
        self.refresh_presets()

    def _set_status(self, message):
        self.status.setText(message)
        self.status.setToolTip(message)

    def refresh_presets(self):
        self.presets, errors = list_presets(self.parser, self.presets_dir)
        self.preset_box.clear()
        for preset in self.presets:
            self.preset_box.addItem(preset.name)
        self.preset_box.setCurrentIndex(-1)
        if errors:
            self._set_status('Some presets could not be read: ' + '; '.join(errors))

    def _choose_image(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Open image', '',
                                                 'Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff);;All files (*)')
        if filename:
            try:
                self.open_image(Path(filename))
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, 'Cannot open image', str(exc))

    def open_image(self, path: Path):
        source = path.expanduser().resolve()
        with Image.open(source) as original:
            image = original.convert('RGB')
            data = image.tobytes()
            view = QImage(data, image.width, image.height, image.width * 3, QImage.Format.Format_RGB888).copy()
        self.source_path = source
        self.original.set_image(view)
        self.file_label.setText(source.name)
        self.file_label.setToolTip(str(source))
        self.options.set_source_size(image.size)

    def update_preview(self):
        retro = self.options.kind.currentData() == 'retro'
        for widget in (self.preset_box, self.apply_preset_button, self.load_preset_button, self.save_preset_button):
            widget.setEnabled(retro)
        self.apply_preset_button.setEnabled(retro and self.preset_box.currentIndex() >= 0)
        self.export_button.setEnabled(False)
        self.result_revision = None
        if self.source_path is None:
            return
        try:
            settings = self.options.settings() if retro else None
        except (ValueError, OverflowError) as exc:
            self.controller.cancel()
            self._set_status('Settings need attention: ' + str(exc))
            return
        self._set_status('Updating preview…')
        self.controller.submit(self.source_path, kind='retro' if retro else 'pixelate', settings=settings,
                                block_size=self.options.block_size.value())

    def _busy_changed(self, busy):
        self.progress.setVisible(busy)
        self.cancel_button.setEnabled(busy)

    def _preview_ready(self, response):
        image = QImage(response['image'])
        if image.isNull():
            self._preview_failed('The rendered preview could not be opened.')
            return
        self.result.set_image(image)
        self.result_path = Path(response['image'])
        self.result_revision = response['revision']
        self.export_button.setEnabled(True)
        width, height = response['size']
        logical_width, logical_height = response['logical_size']
        self._set_status(f'Ready: {width} × {height} output; {logical_width} × {logical_height} logical pixels. '
                         'Use 100% to inspect the display pattern.')

    def _preview_failed(self, message):
        self.export_button.setEnabled(False)
        self.result_revision = None
        self._set_status('Could not update preview: ' + message)

    def cancel_preview(self):
        self.controller.cancel()
        self.result_revision = None
        self.export_button.setEnabled(False)
        self._set_status('Preview cancelled. Change a setting or choose Refresh to try again.')

    def export_to(self, path: Path, *, replace=False):
        if self.result_path is None or self.result_revision != self.controller.revision:
            raise ValueError('Wait for the current preview before exporting.')
        target = path.expanduser().absolute()
        if self.source_path is not None and (target.resolve() == self.source_path or
                (target.exists() and target.samefile(self.source_path))):
            raise ValueError('Choose a different filename so the source image is preserved.')
        if target.exists() and not replace:
            raise FileExistsError('The output file already exists.')
        formats = {'.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG'}
        if target.suffix.lower() not in formats:
            raise ValueError('Choose a .png, .jpg or .jpeg filename.')
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.retroimg-', suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
            with Image.open(self.result_path) as image:
                image.save(temporary, format=formats[target.suffix.lower()])
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _choose_export(self):
        if not self.export_button.isEnabled():
            return
        suggested = self.source_path.with_name(self.source_path.stem + '-retro.png')
        filename, _ = QFileDialog.getSaveFileName(self, 'Export full-size image', str(suggested),
                                                 'PNG image (*.png);;JPEG image (*.jpg *.jpeg)',
                                                 options=QFileDialog.Option.DontConfirmOverwrite)
        if filename:
            path = Path(filename)
            if not path.suffix:
                path = path.with_suffix('.png')
            replace = path.exists()
            if replace and QMessageBox.question(self, 'Replace image?', f'Replace {path.name}?',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
            try:
                self.export_to(path, replace=replace)
                self._set_status(f'Saved {path}')
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, 'Cannot export image', str(exc))

    def _apply_selected_preset(self):
        index = self.preset_box.currentIndex()
        if 0 <= index < len(self.presets):
            self.options.set_settings(self.presets[index].settings)

    def load_preset_path(self, path: Path):
        preset = load_file(path, self.parser)
        self.options.set_settings(preset.settings)

    def save_preset_to(self, path: Path, *, replace=False):
        if self.options.kind.currentData() != 'retro':
            raise ValueError('Original-colour pixelation does not use conversion presets.')
        save_preset(path, path.stem.replace('-', ' '), '', self.options.settings(), self.parser, replace=replace)
        self.refresh_presets()

    def _choose_preset(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Load conversion preset', str(self.presets_dir), 'JSON presets (*.json)')
        if filename:
            try:
                self.load_preset_path(Path(filename))
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, 'Cannot load preset', str(exc))

    def _choose_save_preset(self):
        filename, _ = QFileDialog.getSaveFileName(self, 'Save conversion preset', str(self.presets_dir / 'my-style.json'),
                                                 'JSON presets (*.json)', options=QFileDialog.Option.DontConfirmOverwrite)
        if filename:
            path = Path(filename)
            if not path.suffix:
                path = path.with_suffix('.json')
            replace = path.exists()
            if replace and QMessageBox.question(self, 'Replace preset?', f'Replace {path.name}?',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
            try:
                self.save_preset_to(path, replace=replace)
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, 'Cannot save preset', str(exc))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                try:
                    self.open_image(Path(url.toLocalFile()))
                    event.acceptProposedAction()
                except (OSError, ValueError) as exc:
                    self._set_status('Cannot open image: ' + str(exc))
                break

    def closeEvent(self, event):
        self.controller.close()
        super().closeEvent(event)
