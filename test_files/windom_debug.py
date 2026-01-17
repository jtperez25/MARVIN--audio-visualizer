import sys
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import Qt

class DebugWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(400, 400)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setBrush(QColor(0, 255, 0, 200))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(50, 50, 300, 300)

app = QApplication(sys.argv)
w = DebugWindow()
sys.exit(app.exec())
