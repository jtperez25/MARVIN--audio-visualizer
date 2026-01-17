import sys
import time
import math
import numpy as np
import sounddevice as sd

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QPen
from PyQt6.QtCore import Qt, QTimer, QPointF


# =========================
# HELPERS
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
        self.resize(900, 700)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # FFT
        self.fft_smooth = np.zeros(128)

        # Levels
        self.bass_level = 0.0
        self.bass_avg = 0.0

        self.vocal_level = 0.0
        self.vocal_avg = 0.0
        self.vocal_confidence = 0.0

        # Pitch
        self.pitch_raw = 0.0
        self.pitch_smooth = 0.0
        self.pitch_ultra = 0.0

        # Orb physics
        self.orb_radius = 0.0
        self.orb_velocity = 0.0
        self.orb_target = 0.0

        self.orb_smooth = 0.065   # faster breath
        self.orb_damping = 0.92

        # Beat
        self.beat_energy = 0.0
        self.last_beat = 0.0
        self.beat_cooldown = 0.18

        # Color
        self.color_phase = 0.0

        # Rotation
        self.rotation = 0.0

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

        # -------------------------
        # BEAT (low percussion)
        # -------------------------
        bass = np.mean(fft[2:12])
        self.bass_avg = self.bass_avg * 0.98 + bass * 0.02
        self.bass_level = max(0.0, bass - self.bass_avg * 1.25)

        now = time.time()
        if bass > self.bass_avg * 1.4 and now - self.last_beat > self.beat_cooldown:
            self.last_beat = now
            self.beat_energy = min(self.beat_energy + bass, 1.0)

        # -------------------------
        # STRICT VOCAL ISOLATION
        # -------------------------
        vocal_band = fft[28:52]   # human formants
        vocal_energy = np.mean(vocal_band)

        self.vocal_avg = self.vocal_avg * 0.985 + vocal_energy * 0.015
        raw_vocal = max(0.0, vocal_energy - self.vocal_avg * 1.2)

        # Pitch detection (centroid)
        idx = np.argmax(vocal_band)
        self.pitch_raw = idx / max(1, len(vocal_band))

        # Pitch stability gate
        pitch_delta = abs(self.pitch_raw - self.pitch_smooth)
        pitch_stable = 1.0 if pitch_delta < 0.03 else 0.0

        # Harmonic confidence
        harmonic = np.max(vocal_band)
        noise = np.mean(fft[0:18]) + np.mean(fft[60:90])
        harmonic_ratio = harmonic / (noise + 1e-6)
        harmonic_gate = np.clip((harmonic_ratio - 1.5) * 1.1, 0.0, 1.0)

        self.vocal_confidence = raw_vocal * pitch_stable * harmonic_gate
        self.vocal_level = lerp(self.vocal_level, self.vocal_confidence, 0.30)

    # =========================
    # RENDER
    # =========================
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        center = QPointF(w / 2, h / 2)

        self.beat_energy *= 0.84

        # Pitch smoothing
        self.pitch_smooth = lerp(self.pitch_smooth, self.pitch_raw, 0.12)
        self.pitch_ultra = lerp(self.pitch_ultra, self.pitch_smooth, 0.045)

        # ===============================
        # ORB BREATHING (VOCALS ONLY)
        # ===============================
        base_radius = min(w, h) * 0.22
        pitch_energy = self.pitch_ultra ** 1.25

        emotional_push = max(0.0, self.vocal_level - 0.04) ** 1.8

        self.orb_target = (
            base_radius +
            pitch_energy * 140 +
            self.vocal_level * 190 +
            emotional_push * 260
        )

        self.orb_velocity = lerp(
            self.orb_velocity,
            self.orb_target - self.orb_radius,
            self.orb_smooth
        )
        self.orb_velocity *= self.orb_damping
        self.orb_radius += self.orb_velocity

        radius = self.orb_radius

        # ===============================
        # ORB COLOR (VOCAL EMOTION)
        # ===============================
        deep_purple = QColor(140, 60, 255, 220)
        warm_orange = QColor(255, 150, 80, 220)
        butter_yellow = QColor(255, 235, 160, 220)
        cool_blue = QColor(120, 180, 255, 220)

        self.color_phase += (
            pitch_energy * 0.018 +
            emotional_push * 0.025
        )
        self.color_phase %= 4.0

        palette = [
            deep_purple,
            warm_orange,
            butter_yellow,
            cool_blue,
            deep_purple
        ]

        i = int(self.color_phase)
        t = self.color_phase - i
        orb_color = lerp_color(palette[i], palette[i + 1], t)

        painter.setPen(Qt.PenStyle.NoPen)
        grad = QRadialGradient(center, radius)
        grad.setColorAt(0.0, orb_color)
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(grad)
        painter.drawEllipse(center, radius, radius)

        # ===============================
        # FREQUENCY SPIKES (SUPPORT)
        # ===============================
        fft = self.fft_smooth
        slices = 96
        self.rotation += 0.0015 + self.beat_energy * 0.015

        for i in range(slices):
            angle = (i / slices) * 2 * math.pi + self.rotation
            band = fft[int(i / slices * len(fft))]

            spike = (
                band * 18 +
                self.beat_energy * 55
            )

            inner = radius + 8
            outer = inner + spike

            p1 = QPointF(
                center.x() + math.cos(angle) * inner,
                center.y() + math.sin(angle) * inner
            )
            p2 = QPointF(
                center.x() + math.cos(angle) * outer,
                center.y() + math.sin(angle) * outer
            )

            pen = QPen(QColor(170, 190, 230, 110))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(p1, p2)


# =========================
# RUN
# =========================
app = QApplication(sys.argv)
w = AudioVisualizer()
sys.exit(app.exec())
