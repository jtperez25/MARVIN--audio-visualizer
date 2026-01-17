import sounddevice as sd
import numpy as np

SAMPLE_RATE = 44100
BLOCK_SIZE = 1024

def audio_callback(indata, frames, time, status):
    if status:
        print(status)
    volume = np.sqrt(np.mean(indata**2))
    print(f"Volume: {volume:.4f}")

print("Listening... Play some music. Press Ctrl+C to stop.")

with sd.InputStream(
    samplerate=SAMPLE_RATE,
    blocksize=BLOCK_SIZE,
    channels=1,
    callback=audio_callback,
):
    while True:
        sd.sleep(1000)
