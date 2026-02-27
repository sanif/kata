#!/usr/bin/env python3
"""Generate distinct notification sounds for kata — 3 sound packs.

Packs:
- default: Quirky & characterful (retro coin, fanfare, cartoon boing, sci-fi boot)
- gentle:  Soft & minimal (warm bell, soft chime, wooden knock, music box)
- arcade:  8-bit retro game (power-up, level clear, alert, warp)

Each sound has 5 variants: task-complete, review-complete, question, plan-ready, error.
"""

import math
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

SAMPLE_RATE = 44100
SOUNDS_DIR = Path(__file__).parent.parent / "kata" / "services" / "notifications" / "sounds"


# ── Utilities ──────────────────────────────────────────────


def generate_tone(
    freq: float,
    duration: float,
    volume: float = 0.5,
    fade_in: float = 0.005,
    fade_out: float = 0.02,
    waveform: str = "sine",
) -> list[float]:
    """Generate a tone with envelope."""
    n_samples = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n_samples):
        t = i / SAMPLE_RATE
        if waveform == "sine":
            val = math.sin(2 * math.pi * freq * t)
        elif waveform == "square":
            val = (1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0) * 0.6
        elif waveform == "triangle":
            phase = (freq * t) % 1.0
            val = 4 * abs(phase - 0.5) - 1.0
        elif waveform == "sawtooth":
            phase = (freq * t) % 1.0
            val = (2 * phase - 1.0) * 0.5
        else:
            val = math.sin(2 * math.pi * freq * t)

        progress = i / n_samples
        if t < fade_in:
            val *= t / fade_in
        elif progress > 1.0 - (fade_out / duration):
            remaining = (1.0 - progress) * duration
            val *= max(0, remaining / fade_out)

        samples.append(val * volume)
    return samples


def mix_samples(*sample_lists: list[float]) -> list[float]:
    """Mix multiple sample lists together."""
    max_len = max(len(s) for s in sample_lists)
    result = [0.0] * max_len
    for samples in sample_lists:
        for i, s in enumerate(samples):
            result[i] += s
    peak = max(abs(s) for s in result) if result else 1.0
    if peak > 0.95:
        result = [s * 0.9 / peak for s in result]
    return result


def concat_samples(*sample_lists: list[float]) -> list[float]:
    """Concatenate sample lists sequentially."""
    result = []
    for samples in sample_lists:
        result.extend(samples)
    return result


def add_silence(duration: float) -> list[float]:
    return [0.0] * int(SAMPLE_RATE * duration)


def pitch_sweep(
    freq_start: float,
    freq_end: float,
    duration: float,
    volume: float = 0.5,
    waveform: str = "sine",
) -> list[float]:
    """Generate a pitch sweep."""
    n_samples = int(SAMPLE_RATE * duration)
    samples = []
    phase = 0.0
    for i in range(n_samples):
        t = i / n_samples
        freq = freq_start + (freq_end - freq_start) * t
        phase += 2 * math.pi * freq / SAMPLE_RATE

        if waveform == "sine":
            val = math.sin(phase)
        elif waveform == "square":
            val = (1.0 if math.sin(phase) >= 0 else -1.0) * 0.6
        elif waveform == "triangle":
            p = (phase / (2 * math.pi)) % 1.0
            val = 4 * abs(p - 0.5) - 1.0
        else:
            val = math.sin(phase)

        env = 1.0
        if t < 0.02:
            env = t / 0.02
        elif t > 0.9:
            env = (1.0 - t) / 0.1
        samples.append(val * volume * env)
    return samples


def write_wav(samples: list[float], filepath: Path):
    with wave.open(str(filepath), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        for s in samples:
            s = max(-1.0, min(1.0, s))
            wf.writeframes(struct.pack("<h", int(s * 32767)))


def wav_to_mp3(wav_path: Path, mp3_path: Path):
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(wav_path),
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "64k",
            "-ar",
            "44100",
            str(mp3_path),
        ],
        capture_output=True,
        check=True,
    )


# ══════════════════════════════════════════════════════════════
# DEFAULT PACK — Quirky & characterful
# ══════════════════════════════════════════════════════════════


def default_task_complete() -> list[float]:
    """Retro game power-up: fast ascending chiptune arpeggio with sparkle."""
    notes = [523.25, 659.25, 783.99, 1046.50]
    parts = []
    for freq in notes:
        note = generate_tone(freq, 0.08, volume=0.35, waveform="square", fade_out=0.01)
        harmonic = generate_tone(freq * 2, 0.08, volume=0.12, waveform="sine", fade_out=0.01)
        parts.append(mix_samples(note, harmonic))
    final = generate_tone(1046.50, 0.18, volume=0.3, waveform="sine", fade_out=0.12)
    final_oct = generate_tone(2093.0, 0.18, volume=0.1, waveform="sine", fade_out=0.12)
    parts.append(mix_samples(final, final_oct))
    return concat_samples(*parts)


def default_review_complete() -> list[float]:
    """Triumphant fanfare: two-part brass-like chord with resolution."""
    c1a = generate_tone(261.63, 0.15, volume=0.3, waveform="sawtooth", fade_out=0.03)
    c1b = generate_tone(329.63, 0.15, volume=0.25, waveform="sawtooth", fade_out=0.03)
    chord1 = mix_samples(c1a, c1b)
    gap = add_silence(0.04)
    c2a = generate_tone(329.63, 0.15, volume=0.3, waveform="sawtooth", fade_out=0.03)
    c2b = generate_tone(392.00, 0.15, volume=0.25, waveform="sawtooth", fade_out=0.03)
    chord2 = mix_samples(c2a, c2b)
    r1 = generate_tone(261.63, 0.30, volume=0.25, waveform="sawtooth", fade_out=0.15)
    r2 = generate_tone(329.63, 0.30, volume=0.20, waveform="sawtooth", fade_out=0.15)
    r3 = generate_tone(392.00, 0.30, volume=0.20, waveform="sawtooth", fade_out=0.15)
    r4 = generate_tone(523.25, 0.30, volume=0.15, waveform="sine", fade_out=0.15)
    resolution = mix_samples(r1, r2, r3, r4)
    return concat_samples(chord1, gap, chord2, gap, resolution)


def default_question() -> list[float]:
    """Cartoon 'huh?' — bouncy rising pitch with wobble."""
    thump = generate_tone(180, 0.06, volume=0.4, waveform="sine", fade_out=0.03)
    rise = pitch_sweep(300, 900, 0.18, volume=0.35, waveform="triangle")
    n_wobble = int(SAMPLE_RATE * 0.12)
    wobble = []
    for i in range(n_wobble):
        t = i / SAMPLE_RATE
        vibrato = 8 * math.sin(2 * math.pi * 12 * t)
        freq = 850 + vibrato
        val = math.sin(2 * math.pi * freq * t)
        phase = (freq * t) % 1.0
        tri = 4 * abs(phase - 0.5) - 1.0
        val = val * 0.5 + tri * 0.5
        env = 1.0 - (i / n_wobble) ** 0.5
        wobble.append(val * 0.3 * env)
    return concat_samples(thump, rise, wobble)


def default_plan_ready() -> list[float]:
    """Sci-fi boot-up: ascending digital tones."""
    parts = []
    freqs = [440, 554.37, 659.25]
    for freq in freqs:
        sq = generate_tone(freq, 0.06, volume=0.2, waveform="square", fade_out=0.01)
        sn = generate_tone(freq * 1.5, 0.06, volume=0.1, waveform="sine", fade_out=0.01)
        parts.append(mix_samples(sq, sn))
        parts.append(add_silence(0.03))
    a = generate_tone(440.0, 0.25, volume=0.2, waveform="sine", fade_out=0.15)
    cs = generate_tone(554.37, 0.25, volume=0.18, waveform="sine", fade_out=0.15)
    e = generate_tone(659.25, 0.25, volume=0.18, waveform="sine", fade_out=0.15)
    sub = generate_tone(220.0, 0.25, volume=0.12, waveform="sine", fade_out=0.15)
    parts.append(mix_samples(a, cs, e, sub))
    return concat_samples(*parts)


def default_error() -> list[float]:
    """Descending 'womp womp'."""
    womp1 = pitch_sweep(400, 250, 0.22, volume=0.35, waveform="sawtooth")
    buzz1 = pitch_sweep(403, 253, 0.22, volume=0.15, waveform="sawtooth")
    part1 = mix_samples(womp1, buzz1)
    gap = add_silence(0.08)
    womp2 = pitch_sweep(300, 150, 0.30, volume=0.35, waveform="sawtooth")
    buzz2 = pitch_sweep(303, 153, 0.30, volume=0.15, waveform="sawtooth")
    part2 = mix_samples(womp2, buzz2)
    return concat_samples(part1, gap, part2)


# ══════════════════════════════════════════════════════════════
# GENTLE PACK — Soft & minimal
# ══════════════════════════════════════════════════════════════


def gentle_task_complete() -> list[float]:
    """Warm bell: two soft sine tones, major third, long decay."""
    t1 = generate_tone(523.25, 0.4, volume=0.25, waveform="sine", fade_out=0.30)
    t2 = generate_tone(659.25, 0.4, volume=0.18, waveform="sine", fade_out=0.30)
    # Subtle octave shimmer
    t3 = generate_tone(1046.50, 0.3, volume=0.06, waveform="sine", fade_out=0.25)
    return mix_samples(t1, t2, t3)


def gentle_review_complete() -> list[float]:
    """Soft chime: descending two-note with warmth."""
    n1 = generate_tone(659.25, 0.25, volume=0.22, waveform="sine", fade_out=0.18)
    gap = add_silence(0.06)
    n2 = generate_tone(523.25, 0.35, volume=0.20, waveform="sine", fade_out=0.28)
    # Warm fifth underneath
    n3 = generate_tone(392.00, 0.35, volume=0.10, waveform="sine", fade_out=0.28)
    return concat_samples(n1, gap, mix_samples(n2, n3))


def gentle_question() -> list[float]:
    """Wooden knock: two quick percussive tones rising."""
    # Short percussive hits with fast decay
    k1 = generate_tone(800, 0.04, volume=0.3, waveform="sine", fade_out=0.03)
    gap = add_silence(0.08)
    k2 = generate_tone(1000, 0.05, volume=0.25, waveform="sine", fade_out=0.04)
    # Trailing resonance
    res = generate_tone(1000, 0.15, volume=0.08, waveform="sine", fade_out=0.14)
    return concat_samples(k1, gap, mix_samples(k2, res))


def gentle_plan_ready() -> list[float]:
    """Music box: delicate ascending three-note motif."""
    notes = [659.25, 783.99, 1046.50]  # E5, G5, C6
    parts = []
    for i, freq in enumerate(notes):
        vol = 0.20 - i * 0.03
        n = generate_tone(freq, 0.18, volume=vol, waveform="sine", fade_out=0.14)
        parts.append(n)
        if i < len(notes) - 1:
            parts.append(add_silence(0.05))
    return concat_samples(*parts)


def gentle_error() -> list[float]:
    """Soft low tone: single warm descending note."""
    sweep = pitch_sweep(350, 220, 0.35, volume=0.25, waveform="sine")
    return sweep


# ══════════════════════════════════════════════════════════════
# ARCADE PACK — 8-bit retro game
# ══════════════════════════════════════════════════════════════


def arcade_task_complete() -> list[float]:
    """Coin collect: classic 8-bit ascending two-note."""
    n1 = generate_tone(988, 0.06, volume=0.35, waveform="square", fade_out=0.01)
    n2 = generate_tone(1319, 0.10, volume=0.35, waveform="square", fade_out=0.06)
    return concat_samples(n1, n2)


def arcade_review_complete() -> list[float]:
    """Level clear: 8-bit victory jingle — fast ascending scale."""
    notes = [523.25, 587.33, 659.25, 783.99, 880.0, 1046.50]
    parts = []
    for i, freq in enumerate(notes):
        dur = 0.05 if i < len(notes) - 1 else 0.15
        fade = 0.01 if i < len(notes) - 1 else 0.10
        n = generate_tone(freq, dur, volume=0.30, waveform="square", fade_out=fade)
        parts.append(n)
    return concat_samples(*parts)


def arcade_question() -> list[float]:
    """Alert: classic 8-bit two-tone alarm beep."""
    beeps = []
    for _ in range(2):
        hi = generate_tone(880, 0.07, volume=0.30, waveform="square", fade_out=0.01)
        lo = generate_tone(660, 0.07, volume=0.30, waveform="square", fade_out=0.01)
        beeps.extend([hi, lo])
    return concat_samples(*beeps)


def arcade_plan_ready() -> list[float]:
    """Warp: 8-bit ascending sweep with digital shimmer."""
    sweep = pitch_sweep(220, 880, 0.20, volume=0.30, waveform="square")
    # Hold the high note briefly
    hold = generate_tone(880, 0.12, volume=0.25, waveform="square", fade_out=0.08)
    return concat_samples(sweep, hold)


def arcade_error() -> list[float]:
    """Game over: descending 8-bit three-note."""
    notes = [440, 330, 220]
    parts = []
    for freq in notes:
        n = generate_tone(freq, 0.10, volume=0.30, waveform="square", fade_out=0.04)
        parts.append(n)
        parts.append(add_silence(0.03))
    return concat_samples(*parts)


# ── Pack definitions ──────────────────────────────────────────

PACKS = {
    "default": {
        "task-complete": default_task_complete,
        "review-complete": default_review_complete,
        "question": default_question,
        "plan-ready": default_plan_ready,
        "error": default_error,
    },
    "gentle": {
        "task-complete": gentle_task_complete,
        "review-complete": gentle_review_complete,
        "question": gentle_question,
        "plan-ready": gentle_plan_ready,
        "error": gentle_error,
    },
    "arcade": {
        "task-complete": arcade_task_complete,
        "review-complete": arcade_review_complete,
        "question": arcade_question,
        "plan-ready": arcade_plan_ready,
        "error": arcade_error,
    },
}


def main():
    tmpdir = Path(tempfile.mkdtemp())

    for pack_name, generators in PACKS.items():
        if pack_name == "default":
            out_dir = SOUNDS_DIR
        else:
            out_dir = SOUNDS_DIR / pack_name
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n── {pack_name} pack ──")
        for sound_name, generator in generators.items():
            print(f"  Generating {sound_name}...")
            samples = generator()
            wav_path = tmpdir / f"{sound_name}.wav"
            mp3_path = out_dir / f"{sound_name}.mp3"
            write_wav(samples, wav_path)
            wav_to_mp3(wav_path, mp3_path)
            print(f"    -> {mp3_path} ({mp3_path.stat().st_size} bytes)")

    # Cleanup
    for f in tmpdir.iterdir():
        f.unlink()
    tmpdir.rmdir()
    print("\nDone! All sound packs generated.")


if __name__ == "__main__":
    main()
