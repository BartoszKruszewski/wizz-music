import soundcard as sc
import numpy as np
import sys
import socket
import json
import threading
import time
import colorsys
import random
import logging
from collections import deque

# --- CONFIGURATION -----------------------------------------------------------

# Audio Input Device Name (substring matching)
# macOS: "BlackHole", Windows: "Stereo Mix" / "Loopback".
AUDIO_DEVICE_NAME = "BlackHole"

# WiZ Bulb UDP Port (Standard is 38899)
WIZ_PORT = 38899

# Audio Settings
SAMPLE_RATE = 44100
CHUNK_SIZE = 512 
FREQ_BIN = SAMPLE_RATE / CHUNK_SIZE

# WiZ Network Settings
WIZ_UPDATE_INTERVAL = 0.04

# Frequency Bands (Hz)
BASS_RANGE = (20, 250)
MID_RANGE  = (250, 4000)
HIGH_RANGE = (4000, 20000)

# Visualization Dynamics
ATTACK_FACTOR = 0.95  
RELEASE_FACTOR = 0.15 
CONTRAST = 3.0 
BAR_WIDTH_MINI = 20

# Noise Gate (NEW)
# Signals below this raw energy level are treated as absolute silence.
# Prevents auto-gain from amplifying background hiss during quiet parts.
MIN_VOLUME_THRESHOLD = 0.002

# Light Control Logic
LIGHT_CUTOFF_THRESHOLD = 20  
LIGHT_MAX_THRESHOLD = 90     
BEAT_TRIGGER_THRESHOLD = 80  
BEAT_COOLDOWN = 0.4          

# ANSI Colors
C_RED = '\033[91m'
C_GREEN = '\033[92m'
C_BLUE = '\033[94m'
C_RESET = '\033[0m'

# -----------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("WizMusicSync")

def get_bin_range(hz_range):
    start = int(hz_range[0] / FREQ_BIN)
    end = int(hz_range[1] / FREQ_BIN)
    start = max(1, start)
    end = min(CHUNK_SIZE // 2, end)
    if start >= end: end = start + 1
    return start, end

BASS_IDX = get_bin_range(BASS_RANGE)
MID_IDX  = get_bin_range(MID_RANGE)
HIGH_IDX = get_bin_range(HIGH_RANGE)

def discover_wiz_bulbs(timeout=2.0):
    logger.info("Discovering WiZ bulbs via UDP Broadcast...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    
    msg = {"method": "getPilot", "params": {}}
    try:
        sock.sendto(json.dumps(msg).encode('utf-8'), ('255.255.255.255', WIZ_PORT))
    except Exception:
        return []

    found_bulbs = []
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            data, addr = sock.recvfrom(1024)
            ip = addr[0]
            if not any(b['ip'] == ip for b in found_bulbs):
                found_bulbs.append({'ip': ip})
                logger.info(f"Found bulb: {ip}")
        except socket.timeout: break
        except Exception: continue
            
    sock.close()
    return found_bulbs

class WizController:
    def __init__(self, ips_list, port):
        self.ips = ips_list
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        self.original_states = {}
        self._save_initial_states()

        self.last_sent = 0
        self.min_interval = WIZ_UPDATE_INTERVAL  
        self.target_r = 255; self.target_g = 0; self.target_b = 0; self.target_dimming = 0
        self.last_beat_time = 0 
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def _save_initial_states(self):
        logger.info("Saving initial bulb states...")
        self.sock.settimeout(1.0)
        msg = json.dumps({"method": "getPilot", "params": {}}).encode('utf-8')
        for ip in self.ips:
            try:
                self.sock.sendto(msg, (ip, self.port))
                data, _ = self.sock.recvfrom(1024)
                resp = json.loads(data.decode('utf-8'))
                if "result" in resp: self.original_states[ip] = resp["result"]
            except Exception: pass
        self.sock.settimeout(None)

    def _restore_initial_states(self):
        logger.info("Restoring original bulb states...")
        for ip, state in self.original_states.items():
            params = {}
            if "state" in state: params["state"] = state["state"]
            if "dimming" in state: params["dimming"] = state["dimming"]
            if "r" in state: params.update({"r": state["r"], "g": state["g"], "b": state["b"]})
            elif "temp" in state: params["temp"] = state["temp"]
            elif "sceneId" in state: params["sceneId"] = state["sceneId"]
            
            if params:
                try: self.sock.sendto(json.dumps({"method": "setPilot", "params": params}).encode('utf-8'), (ip, self.port))
                except Exception: pass
        time.sleep(0.5)

    def update(self, bass_val):
        now = time.time()
        
        if bass_val < LIGHT_CUTOFF_THRESHOLD: self.target_dimming = 0
        elif bass_val > LIGHT_MAX_THRESHOLD: self.target_dimming = 100
        else:
            r = LIGHT_MAX_THRESHOLD - LIGHT_CUTOFF_THRESHOLD
            linear = (bass_val - LIGHT_CUTOFF_THRESHOLD) / r
            self.target_dimming = int(10 + (linear * 90))

        if bass_val > BEAT_TRIGGER_THRESHOLD:
            if now - self.last_beat_time > BEAT_COOLDOWN:
                self._randomize_color()
                self.last_beat_time = now

    def _randomize_color(self):
        hue = random.random()
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        self.target_r = int(r * 255); self.target_g = int(g * 255); self.target_b = int(b * 255)

    def _worker(self):
        while self.running:
            now = time.time()
            if now - self.last_sent > self.min_interval:
                is_blackout = (self.target_dimming < 5)
                safe_dimming = max(10, self.target_dimming)
                
                if is_blackout:
                    msg = {"method": "setPilot", "params": {"r": 0, "g": 0, "b": 0, "dimming": safe_dimming}}
                else:
                    msg = {"method": "setPilot", "params": {"r": self.target_r, "g": self.target_g, "b": self.target_b, "dimming": safe_dimming}}
                
                payload = json.dumps(msg).encode('utf-8')
                for ip in self.ips:
                    try: self.sock.sendto(payload, (ip, self.port))
                    except Exception: pass
                self.last_sent = now
            time.sleep(0.005)

    def close(self):
        self.running = False
        self.thread.join(timeout=1.0)
        self._restore_initial_states()
        self.sock.close()

class BandProcessor:
    def __init__(self, name, color):
        self.name = name; self.color = color; self.val = 0.0
        self.max_history = deque(maxlen=200) 
        
    def process(self, magnitude_spectrum, idx_range):
        start, end = idx_range
        band_data = magnitude_spectrum[start:end]
        energy = np.mean(band_data) if len(band_data) > 0 else 0.0

        # --- NOISE GATE ---
        if energy < MIN_VOLUME_THRESHOLD:
            energy = 0.0
        else:
            self.max_history.append(energy)

        # Auto-Gain
        if len(self.max_history) > 10:
            local_max = np.percentile(self.max_history, 95)
        else:
            local_max = 0.1 # Start slightly higher to avoid initial flash
            
        if local_max < 0.001: local_max = 0.001 

        norm = min(max(energy / local_max, 0.0), 1.0)
        target = (norm ** CONTRAST) * 100
        
        if target > self.val: self.val = (self.val * (1 - ATTACK_FACTOR)) + (target * ATTACK_FACTOR)
        else: self.val = (self.val * (1 - RELEASE_FACTOR)) + (target * RELEASE_FACTOR)
        return self.val

    def draw_mini(self):
        filled = min(int((self.val / 100) * BAR_WIDTH_MINI), BAR_WIDTH_MINI)
        return f"{self.color}{self.name[:1]}|{'█'*filled}{' '*(BAR_WIDTH_MINI-filled)}|{C_RESET}"

def main():
    wiz = None
    try:
        bulbs = discover_wiz_bulbs()
        ip_list = [b['ip'] for b in bulbs]
        if ip_list:
            logger.info(f"Connected to {len(ip_list)} bulbs: {ip_list}")
            wiz = WizController(ip_list, WIZ_PORT)
        else:
            logger.warning("No bulbs found. Visual mode only.")

        target_mic = None
        all_mics = sc.all_microphones()
        for mic in all_mics:
            if AUDIO_DEVICE_NAME.lower() in mic.name.lower():
                target_mic = mic
                break
        
        if not target_mic:
            logger.critical(f"Audio device '{AUDIO_DEVICE_NAME}' NOT FOUND.")
            print(f"\n{C_RED}!!! MISSING AUDIO DRIVER !!!{C_RESET}")
            print(f"You need to install '{AUDIO_DEVICE_NAME}' to route system audio to Python.")
            print(f"Install command: {C_GREEN}brew install --cask blackhole-2ch{C_RESET}")
            return

        logger.info(f"Audio Source: {target_mic.name}")
        logger.info("Running... Ctrl+C to stop.")

        bass_proc = BandProcessor("LOW", C_RED)
        mid_proc  = BandProcessor("MID", C_GREEN)
        high_proc = BandProcessor("HI ", C_BLUE)

        with target_mic.recorder(samplerate=SAMPLE_RATE) as recorder:
            while True:
                data = recorder.record(numframes=CHUNK_SIZE)
                if data.size == 0: continue

                audio_mono = np.mean(data, axis=1)
                windowed = audio_mono * np.hanning(len(audio_mono))
                spectrum = np.abs(np.fft.rfft(windowed))

                b = bass_proc.process(spectrum, BASS_IDX)
                m = mid_proc.process(spectrum, MID_IDX)
                h = high_proc.process(spectrum, HIGH_IDX)

                if wiz: wiz.update(b)

                sys.stdout.write(f"\r{bass_proc.draw_mini()}   {mid_proc.draw_mini()}   {high_proc.draw_mini()}")
                sys.stdout.flush()

    except KeyboardInterrupt:
        sys.stdout.write("\n")
        logger.info("Stopping...")
    except Exception:
        logger.exception("Critical error:")
    finally:
        if wiz: wiz.close()

if __name__ == "__main__":
    main()
