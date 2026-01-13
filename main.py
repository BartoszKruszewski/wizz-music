import soundcard as sc
import numpy as np
import sys
from collections import deque

# --- KONFIGURACJA ---
SAMPLE_RATE = 44100
CHUNK_SIZE = 1024  
FREQ_BIN = SAMPLE_RATE / CHUNK_SIZE

BASS_RANGE = (20, 250)
MID_RANGE  = (250, 4000)
HIGH_RANGE = (4000, 20000)

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

BAR_WIDTH_MINI = 20
CONTRAST = 2.5       

# --- NOWE PARAMETRY WYGŁADZANIA ---
# Attack: Jak szybko pasek rośnie (1.0 = natychmiast, 0.1 = wolno)
# Chcemy 1.0, żeby zawsze dobijał do 100% przy uderzeniu!
ATTACK_FACTOR = 0.85

# Release: Jak szybko pasek opada (im mniej, tym wolniej opada/dłuższy ogon)
RELEASE_FACTOR = 0.15

C_RED = '\033[91m'
C_GREEN = '\033[92m'
C_BLUE = '\033[94m'
C_RESET = '\033[0m'

class BandProcessor:
    def __init__(self, name, color):
        self.name = name
        self.color = color
        self.val = 0.0
        self.max_history = deque(maxlen=200) 
        
    def process(self, magnitude_spectrum, idx_range):
        start, end = idx_range
        band_data = magnitude_spectrum[start:end]
        
        if len(band_data) == 0:
            energy = 0.0
        else:
            energy = np.mean(band_data)

        # Normalizacja
        self.max_history.append(energy)
        if len(self.max_history) > 10:
            local_max = np.percentile(self.max_history, 95)
        else:
            local_max = 1.0
        if local_max < 0.001: local_max = 0.001 

        norm = energy / local_max
        norm = min(max(norm, 0.0), 1.0)
        
        # Kontrast
        target = (norm ** CONTRAST) * 100
        
        # --- ASYMETRYCZNE WYGŁADZANIE (Attack / Release) ---
        if target > self.val:
            # ATAK: Jeśli nowy cel jest wyższy, używamy ATTACK_FACTOR (szybko)
            # Dzięki temu krótkie piki są od razu rejestrowane
            self.val = (self.val * (1 - ATTACK_FACTOR)) + (target * ATTACK_FACTOR)
        else:
            # OPADANIE: Jeśli cel jest niższy, używamy RELEASE_FACTOR (wolno)
            # Dzięki temu pasek płynnie wraca do zera
            self.val = (self.val * (1 - RELEASE_FACTOR)) + (target * RELEASE_FACTOR)
        
        return self.val

    def draw_mini(self):
        filled = int((self.val / 100) * BAR_WIDTH_MINI)
        filled = min(filled, BAR_WIDTH_MINI)
        bar = '█' * filled
        spaces = ' ' * (BAR_WIDTH_MINI - filled)
        return f"{self.color}{self.name[:1]}|{bar}{spaces}|{C_RESET}"

def main():
    TARGET_NAME = "BlackHole" 

    try:
        target_mic = None
        for mic in sc.all_microphones():
            if TARGET_NAME.lower() in mic.name.lower():
                target_mic = mic
                break

        if target_mic is None:
            print(f"[BŁĄD] Brak '{TARGET_NAME}'.")
            return

        print(f"Start: Attack={ATTACK_FACTOR}, Release={RELEASE_FACTOR}")
        
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

                bass_proc.process(spectrum, BASS_IDX)
                mid_proc.process(spectrum, MID_IDX)
                high_proc.process(spectrum, HIGH_IDX)

                out_line = f"\r{bass_proc.draw_mini()}   {mid_proc.draw_mini()}   {high_proc.draw_mini()}"
                sys.stdout.write(out_line)
                sys.stdout.flush()

    except KeyboardInterrupt:
        print(f"\n{C_RESET}Zakończono.")

if __name__ == "__main__":
    main()
