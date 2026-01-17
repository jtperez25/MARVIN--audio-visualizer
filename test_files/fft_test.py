import sounddevice as sd
import numpy as np

SAMPLE_RATE = 44100
BLOCK_SIZE = 1024

window = np.hanning(BLOCK_SIZE)
bass_env = 0.0

def audio_callback(indata, frames, time, status):
    global bass_env

    if status:
        print(status)

    samples = indata[:, 0]  # mono
    windowed = samples * window
    fft = np.abs(np.fft.rfft(windowed))
    freqs = np.fft.rfftfreq(BLOCK_SIZE, 1 / SAMPLE_RATE)

    bass = fft[(freqs > 20) & (freqs < 150)].mean()
    bass = bass / 100  # crude normalization
    bass = np.clip(bass, 0, 1)

    # envelope follower
    if bass > bass_env:
        bass_env = bass
    else:
        bass_env *= 0.92

    print(f"Bass: {bass_env:.3f}")

print("Listening for bass... Play music with bass. Ctrl+C to stop.")

with sd.InputStream(
    samplerate=SAMPLE_RATE,
    blocksize=BLOCK_SIZE,
    channels=1,
    callback=audio_callback,
):
    while True:
        sd.sleep(1000)
