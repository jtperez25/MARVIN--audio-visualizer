import sys
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPainter, QColor, QRadialGradient
from PyQt6.QtCore import Qt, QTimer, QPointF


class Visualizer(QWidget):
    def __init__(self):
        super().__init__()

        self.resize(600, 600)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # DEBUG value so it is ALWAYS visible
        self.bass = 0.5

        self.timer = QTimer()
        self.timer.timeout.connect(self.animate)
        self.timer.start(16)

        self.show()

    def animate(self):
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center = QPointF(self.rect().center())
        max_radius = min(self.width(), self.height()) // 2

        radius = max_radius * (0.3 + self.bass)
        alpha = 180  # FORCE visibility

        gradient = QRadialGradient(center, radius)
        gradient.setColorAt(0, QColor(120, 0, 255, alpha))
        gradient.setColorAt(1, QColor(120, 0, 255, 0))

        painter.setBrush(gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, radius, radius)

        def mousePressEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                self.drag_pos = event.globalPosition().toPoint()

        def mouseMoveEvent(self, event):
            if event.buttons() & Qt.MouseButton.LeftButton:
                delta = event.globalPosition().toPoint() - self.drag_pos
                self.move(self.pos() + delta)
                self.drag_pos = event.globalPosition().toPoint()

app = QApplication(sys.argv)
w = Visualizer()
sys.exit(app.exec())
