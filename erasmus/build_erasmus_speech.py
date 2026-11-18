"""
Generatore di tracce audio neurali (Kokoro ONNX) per la presentazione Erasmus+ (erasmus/index.html).
Lingua: Inglese (voce: am_adam o a scelta).
Salva i file in erasmus/audio/slide-{01..12}.ogg e aggiorna erasmus/audio/manifest.json.
"""

import argparse
import json
import re
import tempfile
import unicodedata
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro


ROOT = Path(__file__).resolve().parent
AUDIO_DIR = ROOT / "audio"
MODEL_ROOT = Path.home() / ".cache" / "kokoro-onnx"

MAX_CHUNK_CHARACTERS = 220
MAX_PHONEME_CHARACTERS = 400
CHUNK_PAUSE_SECONDS = 0.22

# Testi delle narrazioni per le 12 diapositive della presentazione Erasmus+
SLIDE_SCRIPTS = {
    1: {
        "title": "Welcome & Erasmus+ Context",
        "text": (
            "Welcome to Istituto di Istruzione Superiore Luigi Lagrange in Milan. "
            "We are delighted to welcome European educators and international partners participating in the Erasmus+ staff mobility programme. "
            "In this presentation, we introduce our fourth-year Telecommunications curriculum in class 4B INF, our laboratory teaching methodology, "
            "and bilateral collaboration opportunities. Every technical module in this deck includes an interactive simulator."
        ),
    },
    2: {
        "title": "The Italian Technical High School System",
        "text": (
            "The Italian technical high school, or Istituto Tecnico Tecnologico, provides a comprehensive five-year pathway. "
            "The first two years form a common biennial foundation in sciences, mathematics, and humanities. "
            "In the three-year triennio, students in class 4B specialize in Computer Science and Telecommunications, "
            "with five weekly hours devoted to telecommunications theory and laboratory. "
            "Upon graduation at age nineteen, students earn an EQF Level 4 diploma as certified industrial technical experts, "
            "complemented by over one hundred and fifty hours of workplace internships."
        ),
    },
    3: {
        "title": "Class 4B INF Syllabus Structure",
        "text": (
            "The fourth-year telecommunications syllabus is built around five core pillars: "
            "signal theory and time-domain analysis; Fourier spectral decomposition; guided transmission media and optical fibers; "
            "analog and digital modulation systems; and network architectures and protocols. "
            "Forty percent of instructional time is hands-on laboratory practice, "
            "where students work in pairs with digital storage oscilloscopes, signal generators, and network simulation software."
        ),
    },
    4: {
        "title": "Module 1: Signal Classification & Interactive Generator",
        "text": (
            "Module one covers signal classification and time-domain parameters. "
            "Signals are classified as deterministic or random, continuous-time analog, sampled, or discrete digital. "
            "Key physical voltage metrics include peak voltage, peak-to-peak amplitude, DC average offset, and root mean square voltage. "
            "In the interactive generator below, you can select sine, square, or triangle waveforms "
            "and adjust amplitude, frequency, and offset to observe live physical telemetry."
        ),
    },
    5: {
        "title": "Module 2: Fourier Analysis & Live Interactive Synth",
        "text": (
            "Module two explores Fourier analysis. "
            "According to Jean-Baptiste Fourier's theorem, any periodic signal can be decomposed into an infinite sum of harmonically related sinusoidal components. "
            "Understanding the harmonic spectrum is essential for determining bandwidth requirements in transmission channels. "
            "In the interactive synthesizer, you can dynamically vary the number of harmonics "
            "and observe the Gibbs phenomenon and waveform convergence in real time."
        ),
    },
    6: {
        "title": "Module 3: Fiber Optics & Total Internal Reflection",
        "text": (
            "Module three examines transmission media, with an emphasis on fiber optics. "
            "Guided transmission relies on Snell's Law and total internal reflection at the boundary between the glass core and outer cladding. "
            "Total internal reflection occurs when the incidence angle exceeds the critical angle. "
            "In the simulator, you can adjust the launch angle and core refractive index "
            "to see how optical pulses travel down the waveguide without light escaping."
        ),
    },
    7: {
        "title": "Module 4: Modulation Systems & Signal Transmission",
        "text": (
            "Module four introduces modulation techniques required to transmit information over transmission media and radio channels. "
            "We analyze analog schemes including amplitude modulation and frequency modulation, "
            "as well as digital shift keying schemes such as ASK and FSK. "
            "Carson's rule governs the necessary transmission bandwidth. "
            "In the simulator, you can toggle modulation modes and carrier frequencies to view the resulting modulated waveform."
        ),
    },
    8: {
        "title": "Module 5: DSO Bandwidth & Rule of 5",
        "text": (
            "Module five focuses on measurement instruments in the electronics laboratory. "
            "When measuring high-speed digital clocks with a digital storage oscilloscope, engineers follow the Rule of 5. "
            "The oscilloscope's analog bandwidth must be at least five times the clock frequency "
            "in order to capture up to the fifth harmonic and avoid severe rise-time attenuation and edge rounding. "
            "The interactive oscilloscope below illustrates this bandwidth limitation live."
        ),
    },
    9: {
        "title": "Pedagogical Methodology & Link Budget Calculator",
        "text": (
            "Our pedagogical methodology emphasizes learning by doing through structured laboratory experiments. "
            "Students work in collaborative pairs, conducting pre-lab simulations in LTspice and Cisco Packet Tracer, "
            "testing physical circuits on hardware benches, and producing professional engineering reports with decibel power budget calculations. "
            "The simulator below lets you calculate optical power attenuation and link margin across single-mode and multi-mode fibers."
        ),
    },
    10: {
        "title": "Our Digital Teaching Platform: fmorea.github.io",
        "text": (
            "To facilitate continuous assessment and self-paced study, we built our open-source digital teaching platform, "
            "hosted serverless on GitHub Pages. It features offline neural audio synthesis using Kokoro ONNX models, "
            "high-density exam revision powered by compressed QR codes, instant client-side PDF certificates, "
            "and strict privacy by design in full compliance with the European AI Act."
        ),
    },
    11: {
        "title": "Erasmus+ Bilateral Cooperation",
        "text": (
            "We warmly invite visiting European institutions to establish bilateral Erasmus+ partnerships with our school. "
            "Opportunities include teacher job shadowing under Key Action 1, reciprocal student vocational internships in Milan's IT sector, "
            "joint STEM telemetry and IoT projects, and shared open educational resources. "
            "Together, we can foster European cooperation and innovation in technical education."
        ),
    },
    12: {
        "title": "Conclusion & Contact Details",
        "text": (
            "Thank you for exploring our Telecommunications curriculum and digital platform. "
            "You can scan the QR code to access the platform directly from your mobile phone, "
            "or get in touch with course coordinator Professor Fernando Morea at Istituto Lagrange in Milan. "
            "We look forward to collaborating with your school on future Erasmus+ mobilities. "
            "Enriching lives, opening minds through European cooperation."
        ),
    },
}


class SpeedInputCompatibilitySession:
    def __init__(self, session):
        self.session = session
        self.input_types = {item.name: item.type for item in session.get_inputs()}

    def get_inputs(self):
        return self.session.get_inputs()

    def run(self, output_names, inputs):
        speed = inputs.get("speed")
        if (
            speed is not None
            and self.input_types.get("speed") == "tensor(float)"
            and speed.dtype != np.float32
        ):
            inputs = dict(inputs)
            inputs["speed"] = np.asarray(speed, dtype=np.float32)
        return self.session.run(output_names, inputs)


def split_text(text, max_characters=MAX_CHUNK_CHARACTERS):
    sentences = re.split(r"(?<=[.!?;:])\s+", text)
    chunks = []
    current = ""
    for sentence in sentences:
        words = sentence.split()
        while words:
            word = words.pop(0)
            if current and len(current) + len(word) + 1 > max_characters:
                chunks.append(current)
                current = ""
            if len(word) > max_characters:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(word)
            else:
                current = word if not current else current + " " + word
    if current:
        chunks.append(current)
    return chunks


def split_phonemes(phonemes, max_characters=MAX_PHONEME_CHARACTERS):
    chunks = []
    current = ""
    for word in phonemes.split():
        if len(word) > max_characters:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(
                word[start : start + max_characters]
                for start in range(0, len(word), max_characters)
            )
        elif current and len(current) + len(word) + 1 > max_characters:
            chunks.append(current)
            current = word
        else:
            current = word if not current else f"{current} {word}"
    if current:
        chunks.append(current)
    return chunks


def synthesize_script(kokoro, text, voice="am_adam", speed=1.0, lang="en-us"):
    text_chunks = split_text(text)
    phoneme_chunks = []
    for tc in text_chunks:
        ph = kokoro.tokenizer.phonemize(tc, lang)
        for pch in split_phonemes(ph):
            phoneme_chunks.append(pch)

    audio_chunks = []
    sample_rate = None
    for i, pch in enumerate(phoneme_chunks):
        samples, sr = kokoro.create(pch, voice=voice, speed=speed, lang=lang, is_phonemes=True)
        if sample_rate is not None and sr != sample_rate:
            raise RuntimeError("Frequenza audio non coerente")
        sample_rate = sr
        audio_chunks.append(np.asarray(samples, dtype=np.float32))
        if i < len(phoneme_chunks) - 1:
            pause = np.zeros(int(sr * CHUNK_PAUSE_SECONDS), dtype=np.float32)
            audio_chunks.append(pause)

    if not audio_chunks:
        return None, 24000
    return np.concatenate(audio_chunks), sample_rate


def write_ogg_file(path: Path, samples, sample_rate):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as tf:
        tmp_path = Path(tf.name)
    try:
        with sf.SoundFile(
            tmp_path,
            mode="w",
            samplerate=sample_rate,
            channels=1,
            format="OGG",
            subtype="VORBIS",
            compression_level=0.35,
        ) as f:
            for start in range(0, len(samples), 8192):
                f.write(samples[start : start + 8192])
        tmp_path.replace(path)
    finally:
        tmp_path.unlink(missing_ok=True)


def build_erasmus_audio(slides_to_build=None, voice="am_adam", speed=1.0, overwrite=False):
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    manifest_file = AUDIO_DIR / "manifest.json"

    manifest_data = {}
    if manifest_file.is_file():
        try:
            manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception:
            manifest_data = {}

    if "slides" not in manifest_data:
        manifest_data = {
            "title": "Erasmus+ Presentation Audio Narration",
            "voice": voice,
            "lang": "en-us",
            "slides": {}
        }

    # Inizializza Kokoro
    model_path = MODEL_ROOT / "kokoro-v1.0.onnx"
    voices_path = MODEL_ROOT / "voices-v1.0.bin"
    if not model_path.is_file() or not voices_path.is_file():
        raise FileNotFoundError(
            f"Modello Kokoro non trovato in {MODEL_ROOT}. Assicurarsi che i file siano presenti."
        )

    print("Inizializzazione del modello Kokoro ONNX...")
    kokoro = Kokoro(str(model_path), str(voices_path))
    kokoro.sess = SpeedInputCompatibilitySession(kokoro.sess)

    target_slides = slides_to_build if slides_to_build else list(SLIDE_SCRIPTS.keys())

    for num in sorted(target_slides):
        if num not in SLIDE_SCRIPTS:
            print(f"Slide {num} non trovata nei testi.")
            continue

        info = SLIDE_SCRIPTS[num]
        ogg_name = f"slide-{num:02d}.ogg"
        ogg_path = AUDIO_DIR / ogg_name

        if ogg_path.is_file() and not overwrite:
            print(f"Slide {num:02d}: {ogg_name} già esistente, salto (usa --overwrite per rigenerare).")
            # Assicura che sia nel manifest
            duration = sf.info(str(ogg_path)).duration
            manifest_data["slides"][str(num)] = {
                "number": num,
                "title": info["title"],
                "file": f"audio/{ogg_name}",
                "duration": round(duration, 2),
                "text": info["text"]
            }
            continue

        print(f"Slide {num:02d}: Sintesi vocale in corso ({len(info['text'])} caratteri)...")
        samples, sr = synthesize_script(kokoro, info["text"], voice=voice, speed=speed, lang="en-us")
        write_ogg_file(ogg_path, samples, sr)
        duration = len(samples) / sr
        print(f"Slide {num:02d}: Creato {ogg_name} ({duration:.1f}s)")

        manifest_data["slides"][str(num)] = {
            "number": num,
            "title": info["title"],
            "file": f"audio/{ogg_name}",
            "duration": round(duration, 2),
            "text": info["text"]
        }

        # Salva progressivamente il manifest
        manifest_file.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")

    manifest_file.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nManifest aggiornato con successo in: {manifest_file}")


def main():
    parser = argparse.ArgumentParser(description="Genera audio neurale per le slide Erasmus+.")
    parser.add_argument("--slide", type=int, action="append", help="Numero slide da generare (1-12).")
    parser.add_argument("--voice", default="am_adam", help="Voce Kokoro (es. am_adam, af_bella, bm_george).")
    parser.add_argument("--speed", type=float, default=1.0, help="Velocità parlato (default 1.0).")
    parser.add_argument("--overwrite", action="store_true", help="Rigenera audio anche se già presente.")
    args = parser.parse_args()

    build_erasmus_audio(slides_to_build=args.slide, voice=args.voice, speed=args.speed, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
