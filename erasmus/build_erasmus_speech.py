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
            "Welcome to Istituto Lagrange in Milan! We are delighted to host visiting European colleagues through Erasmus Plus. "
            "Here in Northern Italy, technical education has deep historical roots. "
            "In this presentation, we take you inside our fourth-year telecommunications classroom, class 4B INF, "
            "where physics, history, and hands-on laboratory discovery come together. "
            "Every module in this deck includes an interactive simulator, so feel free to experiment as we go!"
        ),
    },
    2: {
        "title": "The Italian Technical High School System",
        "text": (
            "Italy's Istituto Tecnico Tecnologico offers a distinctive five-year journey. "
            "Following a two-year scientific and cultural foundation, students enter the three-year triennio to specialize in Computer Science and Telecommunications. "
            "By age nineteen, our students do not just memorize theory; through over one hundred and fifty hours of industry internships, "
            "they graduate as certified technical specialists, ready for the European high-tech workforce or university engineering degrees."
        ),
    },
    3: {
        "title": "Class 4B INF Syllabus Structure",
        "text": (
            "Our fourth-year curriculum bridges classical physics with contemporary communication networks across five thematic pillars: "
            "signal geometry, Fourier analysis, optical guided media, analog and digital modulation, and network protocols. "
            "Nearly half of our class time is spent in the laboratory, where students verify physical principles with oscilloscopes "
            "and circuit prototypes rather than just taking formulas on faith."
        ),
    },
    4: {
        "title": "Module 1: Signal Classification & Interactive Generator",
        "text": (
            "Did you know that signal analysis began in a cathedral? "
            "In 1581, a young Galileo Galilei timed a swinging chandelier in Pisa using his own heartbeat, "
            "discovering that harmonic oscillations maintain a constant period regardless of their swing size! "
            "In telecommunications, we represent this with a simple cosine wave. "
            "Peak voltage is how far the wave swings, while RMS voltage measures the real muscle of the wave—the equivalent DC battery power that would heat a resistor. "
            "Play with the virtual oscilloscope below to see Galileo's harmonic motion in action!"
        ),
    },
    5: {
        "title": "Module 2: Fourier Analysis & Live Interactive Synth",
        "text": (
            "In 1807, Jean-Baptiste Fourier presented a radical idea to the French Academy of Sciences: "
            "any repeating wave, no matter how jagged, can be built purely by adding together gentle sinusoidal flutes! "
            "The great mathematicians of his time, including Laplace and our school's namesake Joseph-Louis Lagrange, were openly skeptical! "
            "Fourier was originally trying to understand heat diffusion in Napoleon's artillery cannons, "
            "but his mathematical insight became the bedrock of modern telecommunications. "
            "In the simulator below, dial in harmonics to watch a jagged square wave emerge from pure sine waves!"
        ),
    },
    6: {
        "title": "Module 3: Fiber Optics & Total Internal Reflection",
        "text": (
            "Today, fiber optic cables carry over ninety-five percent of global internet traffic. "
            "But the principle behind it was first demonstrated in 1854 as a Victorian parlor trick! "
            "The Irish physicist John Tyndall illuminated a stream of water pouring from a bucket, showing that light remained trapped inside the curving water jet. "
            "Just like a flat pebble skipping across a calm lake, light bounces off the boundary between the glass core and cladding without leaking, "
            "provided the launch angle stays above the critical angle. "
            "Test the skipping stone principle live in the optical simulator below!"
        ),
    },
    7: {
        "title": "Module 4: Modulation Systems & Signal Transmission",
        "text": (
            "Imagine trying to transmit human speech across the continent using sound waves directly. "
            "At one kilohertz, an antenna would have to be seventy-five kilometers tall—higher than Mount Everest! "
            "Guglielmo Marconi and the radio pioneers solved this by inventing modulation. "
            "The human voice rides on top of a high-frequency carrier wave, like a passenger boarding an airplane. "
            "Whether we modulate the wave's height in AM, its rhythm in FM, or switch digital pulses in ASK and FSK, "
            "the carrier does the flying while our message arrives crystal clear. Try switching modulation modes below!"
        ),
    },
    8: {
        "title": "Module 5: DSO Bandwidth & Rule of 5",
        "text": (
            "When Karl Ferdinand Braun invented the cathode ray oscilloscope in 1897, signals were slow and analog. "
            "But in today's high-speed digital electronics, clock pulses jump between zero and five volts in mere nanoseconds. "
            "In the lab, students learn the Rule of Five: your oscilloscope's bandwidth must be at least five times faster than the clock frequency. "
            "If your scope is too slow, it acts like a blurry camera shutter, cutting off the high Fourier harmonics and turning sharp square clock pulses into sluggish rounded waves. "
            "Watch how bandwidth limits our view in the scope simulator below!"
        ),
    },
    9: {
        "title": "Pedagogical Methodology & Link Budget Calculator",
        "text": (
            "Why do telecom engineers speak in decibels instead of watts? "
            "In the 1920s, telephone engineers named the decibel after Alexander Graham Bell to match the natural logarithmic response of the human ear. "
            "A quiet whisper and a thunderclap differ in power by one hundred million times! "
            "Decibels transform difficult decimal multiplications into simple additions and subtractions. "
            "In our lab, students calculate the link budget: transmitter power in dBm, minus fiber cable loss, equals receiver power. "
            "Try the link budget calculator below to test single-mode versus multi-mode reach!"
        ),
    },
    10: {
        "title": "Our Digital Teaching Platform: fmorea.github.io",
        "text": (
            "To keep learning accessible, serverless, and private, we built our open-source platform on GitHub Pages. "
            "It features offline neural speech narration powered by Kokoro ONNX models, "
            "instant exam revision with high-density compressed QR codes, "
            "and authenticated student certificates generated client-side with jsPDF. "
            "Everything is designed with zero server overhead and full compliance with European privacy standards and the EU AI Act."
        ),
    },
    11: {
        "title": "Erasmus+ Bilateral Cooperation",
        "text": (
            "We believe technical education thrives on international dialogue. "
            "Through Erasmus Plus Key Action 1 and 2, we warmly invite your school to collaborate with IIS Luigi Lagrange. "
            "Whether through teacher job shadowing, bilingual CLIL co-teaching, reciprocal vocational student internships in Milan's IT sector, "
            "or shared open educational resources, we can build enduring bilateral partnerships across Europe."
        ),
    },
    12: {
        "title": "Conclusion & Contact Details",
        "text": (
            "Thank you so much for exploring our telecommunications curriculum and digital platform! "
            "You can scan the QR code to keep the interactive deck on your smartphone, "
            "or contact Professor Fernando Morea to explore Erasmus Plus cooperation. "
            "As the European motto reminds us: enriching lives, opening minds through education. We look forward to welcoming you to Milan!"
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
