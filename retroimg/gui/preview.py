"""Pannable full-resolution images with explicit fit and integer zoom choices."""
from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)


class ImageView(QGraphicsView):
    def __init__(self, *, smooth=False):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.item = self.scene().addPixmap(QPixmap())
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, smooth)
        self.setBackgroundBrush(Qt.GlobalColor.darkGray)
        self.setMinimumSize(180, 240)
        self.setAcceptDrops(False)
        self.viewport().setAcceptDrops(False)
        self.zoom = None

    def set_image(self, image: QImage):
        self.item.setPixmap(QPixmap.fromImage(image))
        self.scene().setSceneRect(self.item.boundingRect())
        self.apply_zoom()

    def apply_zoom(self):
        self.resetTransform()
        if self.zoom is None:
            if not self.item.pixmap().isNull():
                self.fitInView(self.item, Qt.AspectRatioMode.KeepAspectRatio)
        else:
            factor = self.zoom / self.devicePixelRatioF()
            self.scale(factor, factor)

    def event(self, event):
        if event.type() == QEvent.Type.DevicePixelRatioChange and hasattr(self, 'zoom'):
            QTimer.singleShot(0, self.apply_zoom)
        return super().event(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.zoom is None:
            self.apply_zoom()

    def wheelEvent(self, event):
        # Normal scrolling pans the full-resolution image; zoom is explicit.
        super().wheelEvent(event)


class ImagePane(QWidget):
    def __init__(self, title: str, *, smooth=False):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        label = QLabel(title)
        label.setStyleSheet('font-weight: 600;')
        bar.addWidget(label)
        self.dimensions = QLabel()
        bar.addWidget(self.dimensions, 1)
        self.zoom_box = QComboBox()
        self.zoom_box.addItem('Fit to panel', None)
        for zoom in (1, 2, 4, 8):
            self.zoom_box.addItem(f'{zoom * 100}%', zoom)
        self.zoom_box.setToolTip('100% shows one output pixel per physical screen pixel, including on HiDPI displays. '
                                 'Fitting may alter fine display patterns.')
        bar.addWidget(self.zoom_box)
        layout.addLayout(bar)
        self.view = ImageView(smooth=smooth)
        layout.addWidget(self.view, 1)
        self.zoom_box.currentIndexChanged.connect(self._zoom_changed)

    def _zoom_changed(self):
        self.view.zoom = self.zoom_box.currentData()
        self.view.apply_zoom()

    def set_image(self, image: QImage):
        self.dimensions.setText(f'{image.width()} × {image.height()}')
        self.view.set_image(image)
