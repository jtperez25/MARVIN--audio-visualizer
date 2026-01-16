import sys
import time
import math
import numpy as np
import sounddevice as sd
print(sd.query_devices())


from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QPen
from PyQt6.QtCore import Qt, QTimer, QPointF


# =========================
# Color mapping
# =========================
def color_for_band(i, total, intensity):
    t = i / total

    # Purple → Magenta → Cyan
    if t < 0.33:
        r = int(150 + (255 - 150) * (t / 0.33))
        g = int(50 + (80 - 50) * (t / 0.33))
        b = 255
    elif t < 0.66:
        tt = (t - 0.33) / 0.33
        r = int(255 * (1 - tt))
        g = int(80 + (220 - 80) * tt)
        b = 255
    else:
        tt = (t - 0.66) / 0.34
        r = int(255 * tt)
        g = int(220 + (255 - 220) * tt)
        b = 255

    alpha = int(120 + intensity * 135)
    return QColor(r, g, b, alpha)

def lerp_color(c1, c2, t):
    return QColor(
        int(c1.red()   + (c2.red()   - c1.red())   * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue()  + (c2.blue()  - c1.blue())  * t),
        255
    )

BASS_RIPPLE_COLOR = QColor(150, 70, 255)     # deep purple
SNARE_RIPPLE_COLOR = QColor(255, 235, 160)   # butter yellow

def ripple_color(base_color, ripple_dist, ripple_radius, strength):
    if strength <= 0.0:
        return base_color

    # How close is this layer to the ripple wave?
    d = abs(ripple_dist - ripple_radius)
    width = 40.0  # ripple thickness

    if d > width:
        return base_color

    t = 1.0 - (d / width)
    t *= strength

    # Blend toward white-magenta glow
    r = int(base_color.red()   + (255 - base_color.red())   * t)
    g = int(base_color.green() + (200 - base_color.green()) * t)
    b = int(base_color.blue()  + (255 - base_color.blue())  * t)

    return QColor(r, g, b, base_color.alpha())

# =========================
# Main visualizer
# =========================
class AudioVisualizer(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Audio Sphere Visualizer")
        self.resize(800, 600)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Audio state
        self.smooth_volume = 0.0
        self.smooth_bass = 0.0
        self.smooth_fft = np.zeros(128)

        # ===============================
        # Sustained color breathing
        # ===============================
        self.sustain_energy = 0.0
        self.sustain_attack = 0.08
        self.sustain_release = 0.02

        # Beat detection
        self.bass_history = np.zeros(40)
        self.last_beat_time = 0.0
        self.beat_cooldown = 0.18  # seconds

        # ===============================
        # Beat-driven color breathing
        # ===============================
        self.breath_energy = 0.0
        self.breath_decay = 0.994

        # ===============================
        # Breath systems
        # ===============================
        self.bass_breath = 0.0
        self.vocal_breath = 0.0

        self.bass_breath_decay = 0.88
        self.vocal_breath_decay = 0.94

        # Ripple
        self.ripple_radius = 0.0
        self.ripple_strength = 0.0
        # Beat color ripple
        self.color_ripple_radius = 0.0
        self.color_ripple_strength = 0.0

        # =========================
        # Ripple system (bass + snare)
        # =========================
        self.ripples = []

        # Rotation
        self.rotation = 0.0

        # === Spring physics for orb ===
        self.orb_radius = 0.0
        self.orb_velocity = 0.0

        self.spring_strength = 0.12   # stiffness
        self.spring_damping = 0.88    # friction

        # ===============================
        # Color spring system (smooth kicks)
        # ===============================
        self.color_energy = 0.0     # current color intensity
        self.color_velocity = 0.0   # momentum
        self.color_damping = 0.88   # how quickly it settles
        self.color_spring = 0.12    # how strongly it pulls back

        # Audio stream
        self.stream = sd.InputStream(
            device=0,              # BlackHole 2ch
            channels=2,            # MUST be 2 for BlackHole
            samplerate=44100,
            blocksize=256,
            callback=self.audio_callback
        )
        self.stream.start()


        # Render loop
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(16)

        self.show()

    # =========================
    # Audio callback (REAL TIME)
    # =========================
    def audio_callback(self, indata, frames, time_info, status):
        if status:
            return

        samples = np.mean(indata, axis=1)  # downmix stereo → mono

        fft = np.abs(np.fft.rfft(samples))[:128]
        fft /= np.max(fft) + 1e-6

        # Frequency bands
        raw_bass = np.mean(fft[1:10])          # kick / sub
        raw_vocals = np.mean(fft[20:60])       # vocals / leads


        # Energy
        raw_volume = np.linalg.norm(samples)
        raw_bass = np.mean(fft[1:10])

        # Fast smoothing (low latency)
        self.smooth_volume = self.smooth_volume * 0.75 + raw_volume * 0.25
        # Track sustained sound energy (pads, vocals, bass holds)
        target = min(self.smooth_volume * 1.2, 1.0)

        if target > self.sustain_energy:
            self.sustain_energy += (target - self.sustain_energy) * self.sustain_attack
        else:
            self.sustain_energy += (target - self.sustain_energy) * self.sustain_release

        self.smooth_bass = self.smooth_bass * 0.75 + raw_bass * 0.25
        self.smooth_fft = self.smooth_fft * 0.85 + fft * 0.15

        # Beat detection
        self.bass_history = np.roll(self.bass_history, -1)
        self.bass_history[-1] = raw_bass
        avg_bass = np.mean(self.bass_history)

        now = time.time()

        # Bass breath (triggered, heavier)
        if raw_bass > np.mean(self.bass_history) * 1.25:
            self.bass_breath = min(self.bass_breath + raw_bass * 0.6, 1.0)

        # Vocal breath (continuous, smooth)
        self.vocal_breath += raw_vocals * 0.04
        self.vocal_breath = min(self.vocal_breath, 1.0)


        # =========================
        # Snare / transient (short ripple)
        # =========================
        high_energy = np.mean(fft[25:60])
        high_avg = np.mean(self.smooth_fft[25:60]) + 1e-6

        # === Snare energy (mid frequencies) ===
        snare_energy = np.mean(fft[20:45])
        # === Snare trigger (fast transient) ===
        if snare_energy > np.mean(self.smooth_fft[20:45]) * 1.6:
            self.trigger_snare()

        if high_energy > high_avg * 1.8:
            self.ripples.append({
                "radius": self.radius if hasattr(self, "radius") else 0,
                "strength": 0.7,
                "speed": 9.0,
                "decay": 0.90,
                "color": QColor(200, 220, 255)  # sharp white-blue
            })


    def trigger_beat(self, now):
        strength = min(self.smooth_bass * 1.6, 1.0)

        # Visual ripple (unchanged)
        self.ripples.append({
            "radius": self.orb_radius * 0.6,
            "strength": strength,
            "speed": 8,
            "decay": 0.94,
            "color": BASS_RIPPLE_COLOR
        })

        # Inject color breath (beat-locked)
        self.breath_energy = min(1.0, self.breath_energy + strength * 0.6)

    def trigger_snare(self):
        self.ripples.append({
            "radius": self.orb_radius * 0.85,
            "strength": min(self.smooth_volume * 1.2, 1.0),
            "speed": 14,          # fast
            "decay": 0.88,        # short-lived
            "color": SNARE_RIPPLE_COLOR
        })

    # =========================
    # Rendering
    # =========================
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # ===============================
        # Breath decay
        # ===============================
        self.bass_breath *= self.bass_breath_decay
        self.vocal_breath *= self.vocal_breath_decay


        w, h = self.width(), self.height()
        center = QPointF(w / 2, h / 2)

        # ===============================
        # Continuous rotation (360° loop)
        # ===============================
        self.rotation += 0.008 + self.smooth_bass * 0.04
        if self.rotation > 2 * math.pi:
            self.rotation -= 2 * math.pi
        # ===============================
        # Smooth color spring (bass-driven)
        # ===============================
        color_force = -self.color_energy * 0.08
        self.color_velocity += color_force
        self.color_velocity *= 0.88
        self.color_energy += self.color_velocity
        self.color_energy = max(0.0, min(self.color_energy, 1.0))


        t = time.time()

        # ===============================
        # Beat-locked breathing
        # ===============================
        self.breath_energy *= self.breath_decay
        breath = self.breath_energy

        breath_strength = self.sustain_energy * 0.35


        # ===============================
        # Warm drifting orb color palette
        # ===============================
        deep_purple = QColor(140, 60, 255)
        warm_orange = QColor(255, 150, 80)
        butter_yellow = QColor(255, 235, 160)
        cool_blue = QColor(120, 180, 255)

        phase = t * 0.03 + self.vocal_breath * 1.2
        s = (math.sin(phase) + 1) * 0.5

        warm_mix = self.vocal_breath

        base_color = lerp_color(deep_purple, warm_orange, s)
        highlight_color = lerp_color(butter_yellow, cool_blue, s * 0.6)
        orb_core = lerp_color(
            base_color,
            highlight_color,
            warm_mix * 0.4 + breath * 0.35
        )


        bass_energy = self.bass_breath

        # ===============================
        # Spring-based orb motion
        # ===============================
        base_radius = min(w, h) * 0.22
        target_radius = (
            base_radius
            + self.bass_breath * 220     # slower, intentional
            + self.vocal_breath * 40     # gentle lift
        )

        force = (target_radius - self.orb_radius) * self.spring_strength
        self.orb_velocity += force
        self.orb_velocity *= self.spring_damping
        self.orb_radius += self.orb_velocity

        radius = self.orb_radius
        painter.setPen(Qt.PenStyle.NoPen)

        # Smooth color energy (for gentle color transitions)
        self.color_energy = 0.0
        self.color_velocity = 0.0

        # ===============================
        # Layer 1: Outer halo
        # ===============================
        halo_radius = radius * 1.6
        halo_base = QColor(
            orb_core.red(),
            orb_core.green(),
            orb_core.blue(),
            int(50 + bass_energy * 60)
        )

        halo_color = ripple_color(
            halo_base,
            halo_radius,
            self.color_ripple_radius,
            self.color_ripple_strength
        )

        halo = QRadialGradient(center, halo_radius)
        halo.setColorAt(0.0, QColor(0, 0, 0, 0))
        halo.setColorAt(0.6, halo_color)
        halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(halo)
        painter.drawEllipse(center, halo_radius, halo_radius)

        # ===============================
        # Layer 2: Mid bloom
        # ===============================
        mid_radius = radius * 1.28
        mid_base = QColor(
            orb_core.red(),
            orb_core.green(),
            orb_core.blue(),
            int(90 + bass_energy * 70)
        )

        mid_color = ripple_color(
            mid_base,
            mid_radius,
            self.color_ripple_radius,
            self.color_ripple_strength
        )

        mid = QRadialGradient(center, mid_radius)
        mid.setColorAt(0.0, mid_color)
        mid.setColorAt(0.75, QColor(
            orb_core.red(),
            orb_core.green(),
            orb_core.blue(),
            80
        ))
        mid.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(mid)
        painter.drawEllipse(center, mid_radius, mid_radius)

        # ===============================
        # Layer 3: Inner glow
        # ===============================
        inner_base = QColor(
            orb_core.red(),
            orb_core.green(),
            orb_core.blue(),
            int(140 + bass_energy * 60)
        )

        inner_color = ripple_color(
            inner_base,
            radius,
            self.color_ripple_radius,
            self.color_ripple_strength
        )

        inner = QRadialGradient(center, radius)
        inner.setColorAt(0.0, inner_color)
        inner.setColorAt(0.7, QColor(
            orb_core.red(),
            orb_core.green(),
            orb_core.blue(),
            120
        ))
        inner.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(inner)
        painter.drawEllipse(center, radius, radius)

        # ===============================
        # Layer 4: Hot core
        # ===============================
        core_radius = radius * 0.45
        core_base = QColor(
            int(orb_core.red()   + (255 - orb_core.red())   * 0.35),
            int(orb_core.green() + (255 - orb_core.green()) * 0.35),
            int(orb_core.blue()  + (255 - orb_core.blue())  * 0.35),
            int(110 + bass_energy * 90)
        )


        core_color = ripple_color(
            core_base,
            core_radius,
            self.color_ripple_radius,
            self.color_ripple_strength
        )

        core = QRadialGradient(center, core_radius)
        core.setColorAt(0.0, core_color)
        core.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(core)
        painter.drawEllipse(center, core_radius, core_radius)

        # ===============================
        # Beat Ripples (Bass + Snare)
        # ===============================
        new_ripples = []

        for ripple in self.ripples:
            if ripple["strength"] < 0.02:
                continue

            grad = QRadialGradient(center, ripple["radius"])
            grad.setColorAt(0.0, QColor(0, 0, 0, 0))
            grad.setColorAt(
                0.7,
                QColor(
                    ripple["color"].red(),
                    ripple["color"].green(),
                    ripple["color"].blue(),
                    int(220 * ripple["strength"])
                )
            )
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))

            painter.setBrush(grad)
            painter.drawEllipse(center, ripple["radius"], ripple["radius"])

            ripple["radius"] += ripple["speed"]
            ripple["strength"] *= ripple["decay"]
            new_ripples.append(ripple)

        self.ripples = new_ripples[-12:]

        # ===============================
        # Frequency shoreline waves
        # ===============================
        slices = 96
        fft = self.smooth_fft
        fft_len = len(fft)
        max_height = 65

        for i in range(slices):
            a1 = (i / slices) * 2 * math.pi + self.rotation
            a2 = ((i + 1) / slices) * 2 * math.pi + self.rotation

            f0 = int((i / slices) ** 2 * fft_len)
            f1 = int(((i + 1) / slices) ** 2 * fft_len)
            f1 = max(f1, f0 + 1)

            energy = np.mean(fft[f0:f1])
            base_h = (energy ** 0.6) * max_height

            ripple_boost = 0.0
            for ripple in self.ripples:
                d = abs(ripple["radius"] - radius)
                if d < 40:
                    ripple_boost += (1.0 - d / 40.0) * ripple["strength"]

            h = base_h + ripple_boost * 35
            r1 = radius + h
            r2 = radius + h

            p1 = QPointF(center.x() + math.cos(a1) * r1, center.y() + math.sin(a1) * r1)
            p2 = QPointF(center.x() + math.cos(a2) * r2, center.y() + math.sin(a2) * r2)

            intensity = min(1.0, energy + ripple_boost)
            pen = QPen(color_for_band(i, slices, intensity))
            pen.setWidth(2 + int(energy * 2))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)

            painter.setPen(pen)
            painter.drawLine(p1, p2)

        self.color_ripple_radius += 9
        self.color_ripple_strength *= 0.965





# =========================
# App entry
# =========================
app = QApplication(sys.argv)
w = AudioVisualizer()
sys.exit(app.exec())
