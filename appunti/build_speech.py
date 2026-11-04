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
SLIDE_ROOT = ROOT / "slides"
MODEL_ROOT = Path.home() / ".cache" / "kokoro-onnx"
COURSES = (
    "3a_ele_sistemi",
    "3b_inf_telecomunicazioni",
    "4a_ele_tpsee",
    "4b_inf_telecomunicazioni",
)
MAX_CHUNK_CHARACTERS = 200
CHUNK_PAUSE_SECONDS = 0.18


def normalize_spoken_text(title, text):
    cleaned_text = re.sub(r"(?<=\w)-\s*\r?\n\s*(?=\w)", "", text)
    cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()
    cleaned_title = re.sub(r"\s+", " ", title).strip()
    normalized_title = re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", cleaned_title).casefold())
    first_line = cleaned_text.split(".", 1)[0].strip()
    normalized_first_line = re.sub(
        r"[\W_]+", "", unicodedata.normalize("NFKC", first_line).casefold()
    )
    if normalized_title and normalized_title == normalized_first_line:
        cleaned_title = ""
    return ". ".join(part for part in (cleaned_title, cleaned_text) if part)


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


def synthesize_slide(kokoro, slide, voice, speed):
    spoken_text = normalize_spoken_text(slide.get("title", ""), slide.get("text", ""))
    if not slide.get("text", "").strip():
        return None, None

    chunks = split_text(spoken_text)
    audio_chunks = []
    sample_rate = None
    for chunk_index, chunk in enumerate(chunks):
        samples, chunk_sample_rate = kokoro.create(
            chunk, voice=voice, speed=speed, lang="it"
        )
        if sample_rate is not None and chunk_sample_rate != sample_rate:
            raise RuntimeError("Il modello ha restituito frequenze audio non coerenti.")
        sample_rate = chunk_sample_rate
        audio_chunks.append(np.asarray(samples, dtype=np.float32))
        if chunk_index < len(chunks) - 1:
            audio_chunks.append(
                np.zeros(
                    int(chunk_sample_rate * CHUNK_PAUSE_SECONDS), dtype=np.float32
                )
            )
    return np.concatenate(audio_chunks), sample_rate


def write_audio(output_path, samples, sample_rate):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=output_path.parent, suffix=".tmp", delete=False
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)
    try:
        with sf.SoundFile(
            temporary_path,
            mode="w",
            samplerate=sample_rate,
            channels=1,
            format="OGG",
            subtype="VORBIS",
            compression_level=0.35,
        ) as audio_file:
            for start in range(0, len(samples), 8192):
                audio_file.write(samples[start : start + 8192])
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def save_manifest(manifest_path, data):
    serialized = json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=manifest_path.parent,
        suffix=".json",
        delete=False,
    ) as temporary_file:
        temporary_file.write(serialized)
        temporary_path = Path(temporary_file.name)
    try:
        temporary_path.replace(manifest_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def build_course(kokoro, course, pages, voice, speed, overwrite):
    manifest_path = SLIDE_ROOT / course / "slides.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    slides = data["slides"]
    if pages and any(page < 1 or page > len(slides) for page in pages):
        raise ValueError(f"{course}: pagina richiesta fuori intervallo 1-{len(slides)}.")

    selected_pages = set(pages) if pages else set(range(1, len(slides) + 1))
    changed = False
    for slide in slides:
        page_number = slide["number"]
        if page_number not in selected_pages:
            continue
        audio_name = f"slide-{page_number:03}.ogg"
        audio_path = SLIDE_ROOT / course / "audio" / audio_name
        if not slide.get("text", "").strip():
            print(f"{course} pagina {page_number}: saltata, testo OCR assente")
            continue
        if audio_path.is_file() and not overwrite:
            audio_reference = f"audio/{audio_name}"
            if slide.get("audio") != audio_reference:
                slide["audio"] = audio_reference
                changed = True
            print(f"{course} pagina {page_number}: audio già presente")
            if changed:
                save_manifest(manifest_path, data)
                changed = False
            continue
        if kokoro is None:
            print(f"{course} pagina {page_number}: audio non presente")
            continue

        samples, sample_rate = synthesize_slide(kokoro, slide, voice, speed)
        write_audio(audio_path, samples, sample_rate)
        slide["audio"] = f"audio/{audio_name}"
        save_manifest(manifest_path, data)
        changed = False
        print(f"{course} pagina {page_number}: creato {audio_path.name}")

    if changed:
        save_manifest(manifest_path, data)


def main():
    parser = argparse.ArgumentParser(
        description="Genera localmente le tracce audio neurali delle schede."
    )
    parser.add_argument("--course", choices=COURSES, help="Genera solo questo corso.")
    parser.add_argument(
        "--page",
        type=int,
        action="append",
        help="Genera la pagina indicata (ripetibile; richiede --course).",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=MODEL_ROOT / "kokoro-v1.0.onnx",
        help="Percorso del modello ONNX Kokoro.",
    )
    parser.add_argument(
        "--voices",
        type=Path,
        default=MODEL_ROOT / "voices-v1.0.bin",
        help="Percorso del file delle voci Kokoro.",
    )
    parser.add_argument("--voice", default="im_nicola", help="Voce Kokoro da usare.")
    parser.add_argument("--speed", type=float, default=1.0, help="Velocità del parlato.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Rigenera anche gli audio già presenti.",
    )
    parser.add_argument(
        "--link-existing-only",
        action="store_true",
        help="Collega al manifest gli audio esistenti senza sintetizzare tracce nuove.",
    )
    args = parser.parse_args()
    if args.page and not args.course:
        parser.error("--page richiede --course.")
    if not 1 <= args.speed <= 2:
        parser.error("--speed deve essere compreso tra 1 e 2 per questo modello.")
    if args.link_existing_only and args.overwrite:
        parser.error("--link-existing-only non può essere usato con --overwrite.")
    kokoro = None
    if not args.link_existing_only:
        for model_path in (args.model, args.voices):
            if not model_path.is_file():
                raise FileNotFoundError(
                    f"File del modello non trovato: {model_path}. "
                    "Scarica i pesi ufficiali Kokoro e specifica i percorsi con --model e --voices."
                )

        kokoro = Kokoro(str(args.model), str(args.voices))
        kokoro.sess = SpeedInputCompatibilitySession(kokoro.sess)
    courses = (args.course,) if args.course else COURSES
    for course in courses:
        build_course(kokoro, course, args.page, args.voice, args.speed, args.overwrite)


if __name__ == "__main__":
    main()
