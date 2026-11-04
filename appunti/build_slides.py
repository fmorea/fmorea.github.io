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


def build_course(course_key, pdf_name):
    pdf_path = ROOT / pdf_name
    output_dir = SLIDE_ROOT / course_key
    output_dir.mkdir(parents=True, exist_ok=True)
    page_texts = extract_page_texts(pdf_path)
    while page_texts and not page_texts[-1].strip():
        page_texts.pop()

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

        pages = []
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
            title, text = get_page_title_and_text(extracted_text)
            pages.append(
                {
                    "number": page_number,
                    "title": title or f"Slide {page_number}",
                    "text": text,
                    "image": image_name,
                }
            )

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
    for course_key, pdf_name in COURSES.items():
        build_course(course_key, pdf_name)

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
