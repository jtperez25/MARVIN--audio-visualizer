import sys
import time
import math
import numpy as np
import sounddevice as sd

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QPen
from PyQt6.QtCore import Qt, QTimer, QPointF


# =========================
# UTILS
# =========================
def find_blackhole_device():
    for i, dev in enumerate(sd.query_devices()):
        if "BlackHole" in dev["name"] and dev["max_input_channels"] > 0:
            return i
    return None


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    return QColor(
        int(lerp(c1.red(),   c2.red(),   t)),
        int(lerp(c1.green(), c2.green(), t)),
        int(lerp(c1.blue(),  c2.blue(),  t)),
        int(lerp(c1.alpha(), c2.alpha(), t))
    )


# =========================
# VISUALIZER
# =========================
class AudioVisualizer(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Audio Sphere Visualizer")
        self.resize(800, 600)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # FFT
        self.fft_smooth = np.zeros(128)

        # =========================
        # VOCAL MODEL
        # =========================
        self.vocal_energy = 0.0
        self.vocal_env = 0.0
        self.vocal_sustain = 0.0

        self.vocal_attack = 0.18
        self.vocal_release = 0.06

        # Pitch
        self.pitch_raw = 0.0
        self.pitch_smooth = 0.0

        # Confidence
        self.vocal_confidence = 0.0

        # =========================
        # ORB PHYSICS
        # =========================
        self.orb_radius = 0.0
        self.orb_velocity = 0.0
        self.orb_target = 0.0

        self.orb_response = 0.14
        self.orb_damping = 0.90

        # =========================
        # COLOR
        # =========================
        self.color_phase = 0.0

        # =========================
        # SPIKES
        # =========================
        self.beat_energy = 0.0
        self.beat_decay = 0.82

        self.rotation = 0.0

        # =========================
        # AUDIO
        # =========================
        device = find_blackhole_device()
        if device is None:
            print("⚠️ BlackHole not found")
            sys.exit(1)

        self.stream = sd.InputStream(
            device=device,
            channels=2,
            samplerate=44100,
            blocksize=512,
            callback=self.audio_callback
        )
        self.stream.start()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(16)

        self.show()

    # =========================
    # AUDIO CALLBACK
    # =========================
    def audio_callback(self, indata, frames, time_info, status):
        if status:
            return

        samples = np.mean(indata, axis=1)
        fft = np.abs(np.fft.rfft(samples))[:128]
        fft /= np.max(fft) + 1e-6

        self.fft_smooth = self.fft_smooth * 0.88 + fft * 0.12

        vocal_band = fft[18:60]
        vocal_energy = np.mean(vocal_band)

        noise_band = np.mean(fft[60:100]) + 1e-6
        harmonic_ratio = vocal_energy / noise_band

        idx = np.argmax(vocal_band)
        self.pitch_raw = idx / max(1, len(vocal_band))

        confidence = np.clip(harmonic_ratio * 0.6, 0.0, 1.0)
        self.vocal_confidence = lerp(self.vocal_confidence, confidence, 0.12)

        target = vocal_energy if self.vocal_confidence > 0.45 else 0.0

        if target > self.vocal_env:
            self.vocal_env += (target - self.vocal_env) * self.vocal_attack
        else:
            self.vocal_env += (target - self.vocal_env) * self.vocal_release

        if self.vocal_env > 0.08:
            self.vocal_sustain += 0.02
        else:
            self.vocal_sustain *= 0.92

        self.vocal_sustain = min(self.vocal_sustain, 1.0)

        percussion = np.mean(fft[5:18])
        piano = np.mean(fft[25:45])

        transient = percussion * 0.9 + piano * 0.6
        self.beat_energy = max(self.beat_energy, transient)

    # =========================
    # RENDER
    # =========================
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        center = QPointF(w / 2, h / 2)

        self.pitch_smooth = lerp(self.pitch_smooth, self.pitch_raw, 0.12)
        self.beat_energy *= self.beat_decay

        # =========================
        # ORB SIZE
        # =========================
        base_radius = min(w, h) * 0.22

        pitch_energy = self.pitch_smooth ** 1.35
        emotional_push = self.vocal_sustain ** 1.4

        self.orb_target = (
            base_radius +
            pitch_energy * 160 +
            self.vocal_env * 90 +
            emotional_push * 110
        )

        self.orb_velocity = lerp(
            self.orb_velocity,
            self.orb_target - self.orb_radius,
            self.orb_response
        )
        self.orb_velocity *= self.orb_damping
        self.orb_radius += self.orb_velocity

        radius = self.orb_radius

        # =========================
        # ORB COLOR (EXPANDED PALETTE)
        # =========================
        palette = [
            QColor(140, 60, 255, 220),   # deep purple
            QColor(255, 150, 80, 220),   # warm orange
            QColor(255, 235, 160, 220),  # butter yellow
            QColor(120, 180, 255, 220),  # cool blue
            QColor("#512800"),           # deep brown
            QColor("#5F8F4A"),           # moss green
            QColor("#B20000"),           # deep red
            QColor(140, 60, 255, 220)    # loop back
        ]

        self.color_phase += (
            pitch_energy * 0.03 +
            emotional_push * 0.04
        )

        palette_len = len(palette) - 1
        self.color_phase %= palette_len

        i = int(self.color_phase)
        t = self.color_phase - i

        orb_color = lerp_color(palette[i], palette[i + 1], t)

        painter.setPen(Qt.PenStyle.NoPen)
        grad = QRadialGradient(center, radius)
        grad.setColorAt(0.0, orb_color)
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(grad)
        painter.drawEllipse(center, radius, radius)

        # =========================
        # SPIKES
        # =========================
        slices = 96
        fft = self.fft_smooth
        self.rotation += 0.002 + self.beat_energy * 0.012

        for i in range(slices):
            angle = (i / slices) * 2 * math.pi + self.rotation
            band = fft[int(i / slices * len(fft))]

            spike = band * 20 + self.beat_energy * 55

            inner = radius + 6
            outer = inner + spike

            p1 = QPointF(
                center.x() + math.cos(angle) * inner,
                center.y() + math.sin(angle) * inner
            )
            p2 = QPointF(
                center.x() + math.cos(angle) * outer,
                center.y() + math.sin(angle) * outer
            )

            pen = QPen(QColor(180, 200, 255, 130))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(p1, p2)


# =========================
# RUN
# =========================
app = QApplication(sys.argv)
w = AudioVisualizer()
sys.exit(app.exec())
