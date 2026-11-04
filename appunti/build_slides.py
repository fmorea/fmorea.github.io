import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SLIDE_ROOT = ROOT / "slides"
COURSES = {
    "3a_ele_sistemi": "3Ae SIST.AUT.pdf",
    "3b_inf_telecomunicazioni": "Appunti 3B TLC.pdf",
    "4a_ele_tpsee": "Appunti 4AELET TPS.pdf",
    "4b_inf_telecomunicazioni": "Appunti 4Binf TLC.pdf",
}
COURSE_ALIASES = {
    "3c_inf_telecomunicazioni": "3b_inf_telecomunicazioni",
}
IMAGE_MAX_DIMENSION = "1500"
WEBP_QUALITY = "72"
PAGE_FOOTER = re.compile(r"^(?:.+\s+)?(?:page|pagina)\s+\d+\s*$", re.IGNORECASE)
REPEATED_HEADER = re.compile(
    r"(?:giuseppe luigi lagrange|istituto istruzione superiore|"
    r"g\.?\s*l\.?\s*lagrange)",
    re.IGNORECASE,
)
REPEATED_HEADER_TEXT = ("giuseppeluigilagrange", "istitutoistruzionesuperiore")


def find_tool(name):
    executable = shutil.which(name)
    if not executable:
        raise RuntimeError(
            f"Programma '{name}' non trovato. Installare Poppler e ImageMagick."
        )
    return executable


def run_tool(name, *arguments, capture_output=False):
    completed = subprocess.run(
        [find_tool(name), *map(str, arguments)],
        check=True,
        capture_output=capture_output,
    )
    return completed.stdout if capture_output else None


def extract_page_texts(pdf_path):
    contents = run_tool(
        "pdftotext", "-layout", pdf_path, "-", capture_output=True
    ).decode("utf-8", errors="replace")
    return contents.split("\f")


def get_page_title_and_text(contents):
    lines = [line.strip() for line in contents.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    lines = [line for line in lines if not PAGE_FOOTER.match(line)]
    title = lines[0] if lines else ""
    text = "\n".join(line for line in lines[1:] if line).strip()
    return title, text


def extract_ocr_text(image_path, ocr):
    results, _ = ocr(str(image_path))
    if not results:
        return "", ""

    text_rows = []
    for box, text, confidence in results:
        cleaned_text = text.strip()
        if cleaned_text and float(confidence) >= 0.35:
            center_y = sum(point[1] for point in box) / len(box)
            center_x = sum(point[0] for point in box) / len(box)
            text_rows.append((center_y, center_x, cleaned_text))
    text_rows.sort(key=lambda row: (row[0], row[1]))

    lines = []
    for _, _, text in text_rows:
        normalized_text = re.sub(r"[^a-z]", "", text.casefold())
        is_repeated_header = (
            REPEATED_HEADER.search(text)
            or any(header in normalized_text for header in REPEATED_HEADER_TEXT)
        )
        if PAGE_FOOTER.match(text) or is_repeated_header:
            continue
        lines.append(text)
    if not lines:
        return "", ""
    return get_page_title_and_text("\n".join(lines))


def build_course(course_key, pdf_name, ocr, reuse_images=False):
    pdf_path = ROOT / pdf_name
    output_dir = SLIDE_ROOT / course_key
    output_dir.mkdir(parents=True, exist_ok=True)
    page_texts = extract_page_texts(pdf_path)
    while page_texts and not page_texts[-1].strip():
        page_texts.pop()

    existing_images = [
        output_dir / f"slide-{page_number:03}.webp"
        for page_number in range(1, len(page_texts) + 1)
    ]
    use_existing_images = reuse_images and all(image.is_file() for image in existing_images)
    pages = []

    def process_page(page_number, image_path, extracted_text):
        image_name = f"slide-{page_number:03}.webp"
        title, text = get_page_title_and_text(extracted_text)
        text_source = "pdf"
        ocr_title, ocr_text = extract_ocr_text(image_path, ocr)
        if ocr_title and len(ocr_text) > len(text):
            title = ocr_title
            text = ocr_text
            text_source = "ocr"
        pages.append(
            {
                "number": page_number,
                "title": title or f"Slide {page_number}",
                "text": text,
                "image": image_name,
                "textSource": text_source,
            }
        )

    if use_existing_images:
        for page_number, (image_path, extracted_text) in enumerate(
            zip(existing_images, page_texts), start=1
        ):
            process_page(page_number, image_path, extracted_text)
    else:
        with tempfile.TemporaryDirectory(prefix="fmorea-slides-") as temp_dir:
            image_prefix = Path(temp_dir) / "page"
            run_tool(
                "pdftoppm",
                "-scale-to",
                IMAGE_MAX_DIMENSION,
                "-jpeg",
                "-jpegopt",
                "quality=86",
                pdf_path,
                image_prefix,
            )
            generated_images = sorted(Path(temp_dir).glob("page-*.jpg"))
            if len(generated_images) != len(page_texts):
                raise RuntimeError(
                    f"{pdf_name}: attese {len(page_texts)} pagine, "
                    f"generate {len(generated_images)} immagini."
                )

            for page_number, (source_image, extracted_text) in enumerate(
                zip(generated_images, page_texts), start=1
            ):
                image_name = f"slide-{page_number:03}.webp"
                image_path = output_dir / image_name
                run_tool(
                    "magick",
                    source_image,
                    "-define",
                    "webp:method=5",
                    "-quality",
                    WEBP_QUALITY,
                    image_path,
                )
                process_page(page_number, image_path, extracted_text)

    manifest_path = output_dir / "slides.json"
    manifest_path.write_text(
        json.dumps(
            {"source": pdf_name, "slides": pages},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    print(f"{course_key}: estratte {len(pages)} slide da {pdf_name}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Estrae testo e immagini dalle slide PDF.")
    parser.add_argument(
        "--reuse-images",
        action="store_true",
        help="Riconosce il testo senza rigenerare immagini WebP già presenti.",
    )
    args = parser.parse_args()

    from rapidocr_onnxruntime import RapidOCR

    ocr = RapidOCR()
    for course_key, pdf_name in COURSES.items():
        build_course(course_key, pdf_name, ocr, reuse_images=args.reuse_images)

    course_manifest = {
        course_key: f"{course_key}/slides.json" for course_key in COURSES
    }
    for alias, original in COURSE_ALIASES.items():
        course_manifest[alias] = course_manifest[original]

    (SLIDE_ROOT / "manifest.json").write_text(
        json.dumps(course_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
