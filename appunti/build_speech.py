import argparse
import json
import re
import tempfile
import unicodedata
import urllib.parse
import urllib.request
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
MAX_PHONEME_CHARACTERS = 400
CHUNK_PAUSE_SECONDS = 0.18


def translate_text(text, source_lang="it", target_lang="en"):
    cleaned = text.strip()
    if not cleaned:
        return ""
    # Dividi in frasi o paragrafi per non eccedere limiti dell'endpoint
    lines = [l.strip() for l in cleaned.splitlines() if l.strip()]
    translated_lines = []
    for line in lines:
        try:
            url = (
                "https://translate.googleapis.com/translate_a/single?client=gtx&sl="
                + source_lang
                + "&tl="
                + target_lang
                + "&dt=t&q="
                + urllib.parse.quote(line)
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                translated = "".join(part[0] for part in res[0] if part and part[0])
                translated_lines.append(translated)
        except Exception as e:
            print(f"Avviso traduzione fallita per riga ('{line[:40]}...'): {e}")
            translated_lines.append(line)
    return "\n".join(translated_lines)


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


def synthesize_slide(kokoro, slide, voice, speed, lang="it"):
    title = slide.get("title", "")
    text = slide.get("text", "")
    if not text.strip():
        return None, None

    if lang == "en":
        print(f"Traduzione in corso della pagina {slide.get('number', '?')} in inglese...")
        title = translate_text(title, "it", "en")
        text = translate_text(text, "it", "en")
        tokenizer_lang = "en-us"
    else:
        tokenizer_lang = "it"

    spoken_text = normalize_spoken_text(title, text)
    text_chunks = split_text(spoken_text)
    phoneme_chunks = [
        phoneme_chunk
        for text_chunk in text_chunks
        for phoneme_chunk in split_phonemes(
            kokoro.tokenizer.phonemize(text_chunk, tokenizer_lang)
        )
    ]
    if not phoneme_chunks:
        raise RuntimeError(
            f"La pagina {slide.get('number', '?')} non ha prodotto fonemi."
        )
    audio_chunks = []
    sample_rate = None
    for chunk_index, chunk in enumerate(phoneme_chunks):
        samples, chunk_sample_rate = kokoro.create(
            chunk, voice=voice, speed=speed, lang=tokenizer_lang, is_phonemes=True
        )
        if sample_rate is not None and chunk_sample_rate != sample_rate:
            raise RuntimeError("Il modello ha restituito frequenze audio non coerenti.")
        sample_rate = chunk_sample_rate
        audio_chunks.append(np.asarray(samples, dtype=np.float32))
        if chunk_index < len(phoneme_chunks) - 1:
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


def build_course(kokoro, course, pages, voice, speed, overwrite, lang="it"):
    manifest_path = SLIDE_ROOT / course / "slides.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    slides = data["slides"]
    if pages and any(page < 1 or page > len(slides) for page in pages):
        raise ValueError(f"{course}: pagina richiesta fuori intervallo 1-{len(slides)}.")

    selected_pages = set(pages) if pages else set(range(1, len(slides) + 1))
    changed = False

    target_dir = SLIDE_ROOT / course / "audio" / "en" if lang == "en" else SLIDE_ROOT / course / "audio"
    audio_key = "audio_en" if lang == "en" else "audio"

    for slide in slides:
        page_number = slide["number"]
        if page_number not in selected_pages:
            continue
        audio_name = f"slide-{page_number:03}.ogg"
        audio_path = target_dir / audio_name
        if not slide.get("text", "").strip():
            print(f"{course} pagina {page_number}: saltata, testo OCR assente")
            continue
        audio_reference = f"audio/en/{audio_name}" if lang == "en" else f"audio/{audio_name}"
        if audio_path.is_file() and not overwrite:
            if slide.get(audio_key) != audio_reference:
                slide[audio_key] = audio_reference
                changed = True
            print(f"{course} pagina {page_number}: audio ({lang}) già presente")
            if changed:
                save_manifest(manifest_path, data)
                changed = False
            continue
        if kokoro is None:
            print(f"{course} pagina {page_number}: audio ({lang}) non presente")
            continue

        samples, sample_rate = synthesize_slide(kokoro, slide, voice, speed, lang=lang)
        write_audio(audio_path, samples, sample_rate)
        slide[audio_key] = audio_reference
        save_manifest(manifest_path, data)
        changed = False
        print(f"{course} pagina {page_number}: creato {audio_path.name} ({lang})")

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
        "--lang",
        choices=["it", "en"],
        default="it",
        help="Lingua per la sintesi audio (it o en).",
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
    parser.add_argument("--voice", default=None, help="Voce Kokoro da usare.")
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

    voice = args.voice
    if not voice:
        voice = "am_adam" if args.lang == "en" else "im_nicola"

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
        build_course(kokoro, course, args.page, voice, args.speed, args.overwrite, lang=args.lang)


if __name__ == "__main__":
    main()
