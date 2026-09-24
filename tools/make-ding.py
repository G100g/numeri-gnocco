#!/usr/bin/env python3
"""Genera static/ding.wav: il campanello di cassa sentito alla TV.

Il suono era sintetizzato nel browser con le Web Audio API, ma un AudioContext
dal vivo resta sospeso finche' non arriva un gesto dell'utente e sulla TV non
arriva mai nessuno. Qui lo si rende una volta sola, offline, e la pagina lo
riproduce con un <audio src="/ding.wav">.

    python3 tools/make-ding.py        # riscrive static/ding.wav

Modificare il suono significa cambiare i parametri qui sotto e rilanciare.
"""
import math
import os
import random
import struct
import wave

SR = 44100
DUR = 2.0                      # due secondi: tanto basta per le due code
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "static", "ding.wav")

N = int(SR * DUR)
buf = [0.0] * N


def env_exp(start, peak, end, t0, t_peak, t_end):
    """Le rampe esponenziali della Web Audio API, campione per campione."""
    i0, i1, i2 = int(t0 * SR), int(t_peak * SR), int(t_end * SR)
    out = {}
    for i in range(max(i0, 0), min(i1, N)):
        k = (i - i0) / max(i1 - i0, 1)
        out[i] = start * (peak / start) ** k
    for i in range(max(i1, 0), min(i2, N)):
        k = (i - i1) / max(i2 - i1, 1)
        out[i] = peak * (end / peak) ** k
    return out


def add_clack(t):
    """Il "clack" del cassetto: rumore breve bandpassato, non una nota."""
    rnd = random.Random(1789)                 # seme fisso: file riproducibile
    # Biquad bandpass (RBJ) a 2600 Hz, Q 0.9 — gli stessi valori della pagina.
    w0 = 2 * math.pi * 2600 / SR
    alpha = math.sin(w0) / (2 * 0.9)
    b0, b1, b2 = alpha, 0.0, -alpha
    a0, a1, a2 = 1 + alpha, -2 * math.cos(w0), 1 - alpha
    b0, b1, b2, a1, a2 = b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0
    x1 = x2 = y1 = y2 = 0.0
    env = env_exp(0.0001, 0.5, 0.0001, t, t + 0.004, t + 0.07)
    for i in range(int(t * SR), min(int((t + 0.2) * SR), N)):
        x0 = rnd.random() * 2 - 1
        y0 = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, x0, y1, y0
        buf[i] += y0 * env.get(i, 0.0001)


# Parziali inarmoniche, le acute si spengono prima: e' questo che distingue un
# "deng" metallico da un bip.
PARTIALS = [(1, 1, 1), (2.01, 0.55, 0.7), (2.99, 0.38, 0.5),
            (4.21, 0.24, 0.35), (5.43, 0.15, 0.25)]


def add_strike(t, f0, vol, decay):
    for mult, amp, dec in PARTIALS:
        peak, length = vol * amp, decay * dec
        env = env_exp(0.0001, peak, 0.0001, t, t + 0.005, t + length)
        f = f0 * mult
        for i in range(int(t * SR), min(int((t + length) * SR), N)):
            buf[i] += math.sin(2 * math.pi * f * (i / SR - t)) * env.get(i, 0.0)


add_clack(0.0)                              # cassetto
add_strike(0.005, 1046.5, 0.30, 1.1)        # deng
add_strike(0.10, 1568.0, 0.26, 1.4)         # ...deng, una quinta sopra

# Al posto del DynamicsCompressor della pagina: i colpi sommano molte parziali e
# sugli altoparlanti della TV, a volume alto, gracchierebbero.
frames = bytearray()
for v in buf:
    s = math.tanh(v * 0.9 * 1.6) * 0.85
    frames += struct.pack("<h", max(-32767, min(32767, int(s * 32767))))

with wave.open(OUT, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(bytes(frames))

peak = max(abs(v) for v in buf)
print("scritto %s (%d byte, picco pre-compressore %.2f)"
      % (OUT, os.path.getsize(OUT), peak))
