MARVIN
Live Audio Visualizer for Music & Voice
======================================

MARVIN is a real-time audio visualizer designed to translate music and vocals
into expressive motion rather than raw amplitude spikes. It focuses on emotion,
musical structure, and groove, using a breathing orb and controlled frequency
spikes that react intelligently to sound.

This project runs locally and visualizes live system audio. It is not a browser
application.


CORE CONCEPT
------------

Most audio visualizers treat all sound the same. MARVIN intentionally separates
musical roles and maps them to specific visual behaviors.

- Vocals control the orb’s size, breathing, and color
- Percussion (kick / snare) drives rhythmic spikes
- Piano and harmonic content add texture to the spikes
- Sidechain-style energy affects orb breathing
- Sustained vocals increase emotional bloom and glow

The result is a visualization that follows the feel of a song, not just volume.


VISUAL SYSTEM
-------------

ORB (PRIMARY FOCUS)
- Reacts only to vocal energy
- Grows with:
  - Vocal loudness
  - Pitch height
  - Sustained notes
  - Emotional intensity
- Uses smooth spring physics (no jitter)
- Breathing motion follows groove and sidechain energy

SPIKES (SECONDARY MOTION)
- Vertical frequency lines surrounding the orb
- Separate logic for:
  - Percussion transients
  - Piano / harmonic content
- Carefully damped so the orb remains the focus
- Designed to feel on-beat, not noisy

COLOR SYSTEM
- Color rotation is driven by pitch, sustain, and intensity
- Palette includes:
  - Deep purple
  - Warm orange
  - Moss green
  - Brownish red
  - Periwinkle Blue
  - Deep Purple
  - Golden Yellow
  - Cloud White
- Transitions are smooth and emotionally driven


TECH STACK
----------

- Python 3.9+
- PyQt6 (rendering and animation)
- NumPy / SciPy (audio analysis)
- SoundDevice (real-time audio input)
- BlackHole (macOS system audio routing)

Note: PyTorch is NOT used in this project.


LIVE AUDIO WORKFLOW
-------------------

MARVIN runs in live mode only.

System Audio -> BlackHole -> MARVIN

This allows visualization of:
- Spotify
- Apple Music
- YouTube
- DAWs
- Any system-level audio output

No file uploads.
No offline rendering.


BLACKHOLE INSTALLATION & SETUP (macOS)
-------------------------------------

1. Download BlackHole (2ch recommended):
   https://existential.audio/blackhole/

2. Install BlackHole following the installer instructions.

3. Open macOS System Settings:
   - Go to Sound
   - Under Output, select:
     "BlackHole 2ch"

4. (Optional but recommended)
   - If you want to hear audio while visualizing:
     - Create a Multi-Output Device in Audio MIDI Setup
     - Include:
       - BlackHole 2ch
       - Your speakers or headphones
     - Select the Multi-Output Device as system output

5. Ensure audio is playing through the system before launching MARVIN.

VERIFYING BLACKHOLE AUDIO INPUT (TERMINAL TEST)
----------------------------------------------

Before running MARVIN, you can verify that BlackHole is correctly installed
and receiving audio using the following terminal test.

1. Activate your virtual environment (if applicable):
```
   source .venv/bin/activate
```
2. Run this command from the project root:
```
   python3 -c "import sounddevice as sd; print(sd.query_devices())"
```
3. Confirm BlackHole appears in the device list:
   - Look for a device named "BlackHole 2ch"
   - It must have input channels available

4. Optional quick import test (confirms dependencies):
```
   python3 -c "import numpy, sounddevice; print('Audio dependencies OK')"
```
5. Set BlackHole as your system audio output and play audio:
   - Music, video, or DAW output

6. Run MARVIN:
```
   python3 main_visualizer.py
```
If BlackHole is working correctly:
- The terminal will NOT show input errors
- The orb will respond to vocals
- The spikes will react to rhythmic content

If BlackHole is not detected:
- Reinstall BlackHole
- Restart your terminal
- Confirm BlackHole is selected as system output

RUNNING THE PROJECT
-------------------
1. Clone the repository:
```bxsh
   git clone https://github.com/jtperez25/MARVIN.git
   cd MARVIN
```
3. Create a virtual environment:
```bxsh
   python3 -m venv .venv
   source .venv/bin/activate
```
5. Install dependencies:
```bxsh
   pip3 install -r requirements.txt
```
7. Run the visualizer:
```bxsh
   python3 main_visualizer.py
```
If BlackHole is not detected, the program will exit with a warning.


VERSIONING
----------

- main        -> Current active version (latest)
- marvin1.0   -> Archived milestone branch

Development follows an iterative tuning process focused on musical accuracy and
visual emotion.


DESIGN PHILOSOPHY
-----------------

MARVIN prioritizes:
- Musical awareness over raw amplitude
- Smooth motion over jitter
- Emotional response over strict technical accuracy
- Visual restraint over sensory overload

Every system (motion, color, glow, timing) is tuned to feel intentional, human,
and musically grounded.


CURRENT STATUS
--------------

- Live system audio visualization
- Vocal-driven orb animation
- Beat-aware frequency spikes
- Sidechain-inspired breathing motion
- Drop and intensity detection
- Downloadable app packaging planned


LICENSE
-------

MIT License
Free to explore, modify, and build upon.
