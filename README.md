# 🎵 WiZ Music Sync

**WiZ Music Sync** is a high-performance Python application that synchronizes your **WiZ smart bulbs** with your music in real-time.

## ✨ Features

*   **🚀 Ultra-Low Latency:** Optimized for speed (~11ms audio processing) using UDP broadcast.
*   **🥁 Bass-Reactive Strobe:** Lights pulsate and flash in perfect sync with the kick drum.
*   **🎨 Dynamic Color Changing:** Automatically detects beat drops and switches colors on the fly.
*   **🧠 Smart Auto-Gain:** Automatically adjusts sensitivity, so it works with both quiet jazz and loud techno.
*   **🔌 Plug & Play:** Automatically discovers all WiZ bulbs on your network—no IP configuration needed.
*   **🌑 Noise Gate:** Keeps lights pitch black during silent parts of songs.
*   **💾 State Restoration:** Remembers your original light settings and restores them when you stop the music.

---

## 🛠️ Setup (MacOS)

To capture your system audio (Spotify, YouTube, etc.) and send it to Python, you need a virtual audio driver.

1.  **Install BlackHole** (Virtual Audio Driver):
    ```bash
    brew install --cask blackhole-2ch
    ```

2.  **Configure Audio Routing:**
    *   Open **Audio MIDI Setup** (Cmd + Space, type "Audio MIDI Setup").
    *   Click the **+** icon (bottom left) → **Create Multi-Output Device**.
    *   Check both **BlackHole 2ch** and your **MacBook Speakers** (or Headphones).
    *   *(Optional)* Rename this new device to **"Loopback"**.

3.  **Set System Output:**
    *   Click your Sound icon in the menu bar.
    *   Select the **"Loopback"** (Multi-Output Device) you just created.

4.  **Install Dependencies:**
    Run the setup script to create a virtual environment and install Python libraries:
    ```bash
    ./setup.sh
    ```

5.  **Start the Party:**
    ```bash
    ./run.sh
    ```
---

## ⚙️ Configuration

You can tweak the behavior by editing the constants at the top of `main.py`:

*   `AUDIO_DEVICE_NAME`: The name of the input device to listen to (e.g., "BlackHole").
*   `LIGHT_CUTOFF_THRESHOLD`: Minimum bass level to turn the lights on (higher = more "strobe" effect).
*   `BEAT_TRIGGER_THRESHOLD`: How hard the beat needs to hit to change colors.
*   `WIZ_UPDATE_INTERVAL`: Speed of network packets (Default: 0.04s).

## 📦 Requirements

*   Python 3.8+
*   Philips WiZ Smart Bulbs (connected to the same WiFi network)

## 🤝 Contributing

Feel free to open issues or submit pull requests if you have ideas for new visualization modes!

---

*Made with ❤️ and too much loud music.*
