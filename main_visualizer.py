import sys
import time
import math
import numpy as np
import sounddevice as sd

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QPen
from PyQt6.QtCore import Qt, QTimer, QPointF


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


class AudioVisualizer(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Audio Sphere Visualizer")
        self.resize(800, 600)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.fft_smooth = np.zeros(128)

        # === VOCALS ===
        self.vocal_level = 0.0
        self.vocal_avg = 0.0
        self.vocal_env = 0.0

        self.pitch_raw = 0.0
        self.pitch_smooth = 0.0
        self.pitch_ultra = 0.0
        self.pitch_confidence = 0.0
        self.prev_pitch = 0.0

        # Vibrato
        self.vibrato = 0.0
        self.vibrato_phase = 0.0

        # === ORB ===
        self.orb_radius = 0.0
        self.orb_velocity = 0.0
        self.orb_smooth = 0.09
        self.orb_damping = 0.92

        # === PIANO ===
        self.piano_energy = 0.0

        # === CHORUS DETECTION ===
        self.chorus_energy = 0.0
        self.chorus_attack = 0.015   # slow rise
        self.chorus_release = 0.006  # slow fall

        self.rotation = 0.0
        self.color_phase = 0.0

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

        # --- Piano / harmonic band ---
        piano_band = np.mean(fft[18:42])
        self.piano_energy = lerp(self.piano_energy, piano_band, 0.2)

        # --- Vocal band ---
        vocal_band = fft[22:62]
        vocals = np.mean(vocal_band)

        self.vocal_avg = self.vocal_avg * 0.985 + vocals * 0.015
        raw_env = max(0.0, vocals - self.vocal_avg)
        target_env = (raw_env * 4.0) ** 1.3

        idx = np.argmax(vocal_band)
        peak = vocal_band[idx]
        mean = np.mean(vocal_band) + 1e-6

        self.pitch_raw = idx / len(vocal_band)
        self.pitch_confidence = np.clip((peak / mean - 1.0), 0.0, 1.0)

        target_env *= self.pitch_confidence
        self.vocal_env = lerp(self.vocal_env, target_env, 0.28)

        # =========================
        # CHORUS ENERGY
        # =========================
        chorus_signal = (
            self.vocal_env * 1.4 +
            self.piano_energy * 0.9
        )

        if chorus_signal > 0.25:
            self.chorus_energy += (chorus_signal - self.chorus_energy) * self.chorus_attack
        else:
            self.chorus_energy += (chorus_signal - self.chorus_energy) * self.chorus_release

        self.chorus_energy = max(0.0, min(self.chorus_energy, 1.0))

    # =========================
    # RENDER
    # =========================
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        center = QPointF(w / 2, h / 2)

        # Pitch smoothing
        self.pitch_smooth = lerp(self.pitch_smooth, self.pitch_raw, 0.14)
        self.pitch_ultra = lerp(self.pitch_ultra, self.pitch_smooth, 0.08)

        # Vibrato
        pitch_delta = abs(self.pitch_ultra - self.prev_pitch)
        self.prev_pitch = self.pitch_ultra

        vibrato_target = pitch_delta * 6.0
        vibrato_target *= self.pitch_confidence
        vibrato_target *= min(self.vocal_env * 2.0, 1.0)

        self.vibrato = lerp(self.vibrato, vibrato_target, 0.18)
        self.vibrato_phase += 0.32 + self.vibrato * 0.7
        vibrato_wave = math.sin(self.vibrato_phase) * self.vibrato

        # ===============================
        # ORB SIZE (VOCALS + CHORUS)
        # ===============================
        base = min(w, h) * 0.22

        radius_target = (
            base +
            self.vocal_env * 170 +
            self.pitch_ultra * 55 +
            vibrato_wave * 14 +
            self.chorus_energy * 90   # 🌟 chorus lift
        )

        self.orb_velocity = lerp(
            self.orb_velocity,
            radius_target - self.orb_radius,
            self.orb_smooth
        )
        self.orb_velocity *= self.orb_damping
        self.orb_radius += self.orb_velocity
        radius = self.orb_radius

        # ===============================
        # ORB COLOR (CHORUS WARMTH)
        # ===============================
        self.color_phase += (
            self.vocal_env * 0.04 +
            self.vibrato * 0.015 +
            self.chorus_energy * 0.02
        )
        self.color_phase %= 4.0

        palette = [
            QColor(140, 60, 255, 220),
            QColor(255, 150, 80, 220),
            QColor(255, 235, 160, 220),
            QColor(120, 180, 255, 220),
            QColor(140, 60, 255, 220)
        ]

        i = int(self.color_phase)
        orb_color = lerp_color(palette[i], palette[i + 1], self.color_phase - i)

        painter.setPen(Qt.PenStyle.NoPen)
        grad = QRadialGradient(center, radius)
        grad.setColorAt(0.0, orb_color)
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(grad)
        painter.drawEllipse(center, radius, radius)

        # ===============================
        # PIANO SPIKES (SUPPORT)
        # ===============================
        slices = 96
        self.rotation += 0.0015

        piano_strength = (self.piano_energy ** 0.7) * 45

        for i in range(slices):
            angle = (i / slices) * 2 * math.pi + self.rotation

            inner = radius + 8
            outer = inner + piano_strength

            p1 = QPointF(center.x() + math.cos(angle) * inner,
                         center.y() + math.sin(angle) * inner)
            p2 = QPointF(center.x() + math.cos(angle) * outer,
                         center.y() + math.sin(angle) * outer)

            pen = QPen(QColor(180, 200, 255, 110))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(p1, p2)


# =========================
# RUN
# =========================
app = QApplication(sys.argv)
w = AudioVisualizer()
sys.exit(app.exec())
