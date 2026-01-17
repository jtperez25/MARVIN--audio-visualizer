import sys
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor


class TestWidget(QWidget):
    def __init__(self):
        super().__init__()

        # Frameless + transparent widget
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.resize(600, 600)

        # 60 FPS redraw timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(16)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setBrush(QColor(120, 0, 255, 180))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(200, 200, 200, 200)


app = QApplication(sys.argv)
w = TestWidget()
w.show()
sys.exit(app.exec())
