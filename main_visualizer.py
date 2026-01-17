import sys
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
        int(lerp(c1.red(), c2.red(), t)),
        int(lerp(c1.green(), c2.green(), t)),
        int(lerp(c1.blue(), c2.blue(), t)),
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

        self.fft_smooth = np.zeros(128)

        # =========================
        # VOCALS
        # =========================
        self.vocal_env = 0.0
        self.vocal_sustain = 0.0
        self.pitch_raw = 0.0
        self.pitch_smooth = 0.0
        self.vocal_confidence = 0.0

        self.vocal_attack = 0.18
        self.vocal_release = 0.06

        # =========================
        # ORB
        # =========================
        self.orb_radius = 0.0
        self.orb_velocity = 0.0
        self.orb_response = 0.14
        self.orb_damping = 0.90

        # =========================
        # SIDECHAIN
        # =========================
        self.sidechain_env = 0.0
        self.glow_pump = 0.0

        # =========================
        # SPIKES
        # =========================
        self.kick_energy = 0.0
        self.piano_energy = 0.0

        self.kick_decay = 0.78
        self.piano_decay = 0.90

        # =========================
        # CHORUS
        # =========================
        self.energy_avg = 0.0
        self.chorus_level = 0.0
        self.chorus_attack = 0.015
        self.chorus_release = 0.006

        # =========================
        # DROP DETECTION
        # =========================
        self.drop_flash = 0.0
        self.pre_drop_energy = 0.0
        self.drop_cooldown = 0.0

        # =========================
        # COLOR / ROTATION
        # =========================
        self.color_phase = 0.0
        self.rotation = 0.0
        self.rotation_freeze = 0.0

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

        energy = np.mean(fft)
        self.energy_avg = lerp(self.energy_avg, energy, 0.01)

        # =========================
        # VOCALS
        # =========================
        vocal_band = fft[18:60]
        noise_band = np.mean(fft[60:100]) + 1e-6
        vocal_energy = np.mean(vocal_band)
        harmonic_ratio = vocal_energy / noise_band

        self.pitch_raw = np.argmax(vocal_band) / len(vocal_band)
        confidence = np.clip(harmonic_ratio * 0.6, 0.0, 1.0)
        self.vocal_confidence = lerp(self.vocal_confidence, confidence, 0.12)

        target = vocal_energy if self.vocal_confidence > 0.45 else 0.0
        if target > self.vocal_env:
            self.vocal_env += (target - self.vocal_env) * self.vocal_attack
        else:
            self.vocal_env += (target - self.vocal_env) * self.vocal_release

        if self.vocal_env > 0.08:
            self.vocal_sustain = min(self.vocal_sustain + 0.02, 1.0)
        else:
            self.vocal_sustain *= 0.92

        # =========================
        # CHORUS
        # =========================
        chorus_trigger = (
            energy > self.energy_avg * 1.35 and
            self.vocal_sustain > 0.35
        )

        if chorus_trigger:
            self.chorus_level = min(1.0, self.chorus_level + self.chorus_attack)
        else:
            self.chorus_level = max(0.0, self.chorus_level - self.chorus_release)

        # =========================
        # KICK / PIANO
        # =========================
        kick = np.mean(fft[2:6])
        piano = np.mean(fft[24:48])
        mids = np.mean(fft[12:80])

        self.kick_energy = max(self.kick_energy, kick * 1.6)
        self.piano_energy = max(self.piano_energy, piano * 1.2)

        sidechain = max(0.0, kick - mids)
        self.sidechain_env = lerp(self.sidechain_env, sidechain, 0.35)

        # =========================
        # DROP DETECTION
        # =========================
        self.pre_drop_energy = lerp(self.pre_drop_energy, energy, 0.02)
        self.drop_cooldown = max(0.0, self.drop_cooldown - 0.016)

        drop_trigger = (
            self.drop_cooldown <= 0.0 and
            self.chorus_level > 0.6 and
            kick > self.pre_drop_energy * 1.8 and
            mids < self.pre_drop_energy * 0.9
        )

        if drop_trigger:
            self.drop_flash = 1.0
            self.drop_cooldown = 1.2
            self.rotation_freeze = 0.15

    # =========================
    # RENDER
    # =========================
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        center = QPointF(w / 2, h / 2)

        self.pitch_smooth = lerp(self.pitch_smooth, self.pitch_raw, 0.12)
        self.kick_energy *= self.kick_decay
        self.piano_energy *= self.piano_decay

        self.drop_flash *= 0.85
        self.rotation_freeze = max(0.0, self.rotation_freeze - 0.016)

        # =========================
        # ORB SIZE (DROP IMPACT)
        # =========================
        base_radius = min(w, h) * 0.22
        pitch_energy = self.pitch_smooth ** 1.35
        emotional = self.vocal_sustain ** 1.4
        bloom = self.chorus_level ** 1.4

        drop_punch = self.drop_flash ** 1.8

        target_radius = (
            base_radius +
            pitch_energy * 150 +
            self.vocal_env * 80 +
            emotional * 100 +
            bloom * 120 +
            drop_punch * 220
        )

        self.orb_velocity = lerp(
            self.orb_velocity,
            target_radius - self.orb_radius,
            self.orb_response
        )
        self.orb_velocity *= self.orb_damping
        self.orb_radius += self.orb_velocity

        # =========================
        # GLOW
        # =========================
        pump = min(self.sidechain_env * 5.0 + drop_punch * 1.4, 1.5)
        self.glow_pump = lerp(self.glow_pump, pump, 0.22)

        radius = self.orb_radius

        # =========================
        # COLOR
        # =========================
        deep_purple = QColor(140, 60, 255, 220)
        warm_orange = QColor(255, 150, 80, 220)
        soft_green = QColor(120, 200, 140, 220)
        deep_red = QColor(178, 0, 0, 220)

        self.color_phase += (
            pitch_energy * 0.028 +
            emotional * 0.035 +
            bloom * 0.05
        )
        self.color_phase %= 4.0

        i = int(self.color_phase)
        t = self.color_phase - i
        palette = [deep_purple, warm_orange, soft_green, deep_red, deep_purple]
        orb_color = lerp_color(palette[i], palette[i + 1], t)

        painter.setPen(Qt.PenStyle.NoPen)
        grad = QRadialGradient(center, radius * (1.0 + self.glow_pump * 0.15))
        grad.setColorAt(0.0, orb_color)
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(grad)
        painter.drawEllipse(center, radius, radius)

        # =========================
        # SPIKES
        # =========================
        spike_scale = 1.0 - bloom * 0.55 + self.drop_flash * 0.6

        if self.rotation_freeze <= 0.0:
            self.rotation += 0.002 + self.kick_energy * 0.015

        slices = 96
        for i in range(slices):
            angle = (i / slices) * 2 * math.pi + self.rotation
            band = self.fft_smooth[int(i / slices * len(self.fft_smooth))]

            kick_spike = self.kick_energy * 42
            piano_spike = band * 12 + self.piano_energy * 26
            spike = (kick_spike + piano_spike) * spike_scale

            inner = radius + 6
            outer = inner + spike

            alpha = int(90 + self.kick_energy * 80 + self.drop_flash * 80)
            pen = QPen(QColor(200, 220, 255, alpha))
            pen.setWidth(2)
            painter.setPen(pen)

            p1 = QPointF(center.x() + math.cos(angle) * inner,
                         center.y() + math.sin(angle) * inner)
            p2 = QPointF(center.x() + math.cos(angle) * outer,
                         center.y() + math.sin(angle) * outer)
            painter.drawLine(p1, p2)


# =========================
# RUN
# =========================
app = QApplication(sys.argv)
w = AudioVisualizer()
sys.exit(app.exec())
