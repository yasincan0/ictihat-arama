"""Resmî kaynaktan elle indirilen dosyalardan düz metin çıkarır.

Desteklenen biçimler:
- .txt
- .htm / .html  (Resmî Gazete'nin eski sayıları; çoğunlukla windows-1254 kodlu)
- .pdf          (metin katmanı varsa pypdf; yoksa sayfa sayfa OCR)
- .png / .jpg / .jpeg / .tif / .tiff  (taranmış sayfa; OCR)

OCR için sistemde `pdftoppm` (poppler-utils) ve `tesseract` + Türkçe dil paketi
(tesseract-ocr-tur) kurulu olmalıdır.

OCR pahalı olduğundan sonuçlar dosyanın SHA-256 özetine göre
data/processed/metin/ altında önbelleğe alınır; aynı dosya ikinci kez işlenmez.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path

SUPPORTED_SUFFIXES = {".txt", ".htm", ".html", ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}

# Bir PDF sayfasında bundan az harf varsa metin katmanı yok/yetersiz sayılır ve OCR yapılır.
MIN_LETTERS_PER_PAGE = 200
OCR_DPI = 300
OCR_LANG = "tur"


class ExtractionError(RuntimeError):
    """Dosyadan metin çıkarılamadı."""


@dataclass
class ExtractedText:
    sha256: str
    source_name: str
    text: str
    # "metin" (dosyada hazır metin), "pdf" (metin katmanı), "ocr" veya "pdf+ocr"
    method: str
    pages: int


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def clean_text(text: str) -> str:
    """Unicode normalleştirme, satır sonu ve boşluk düzeltmesi."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    # Satır sonunda tireyle bölünmüş kelimeleri birleştir (OCR ve eski dizgide sık görülür)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def decode_bytes(raw: bytes) -> str:
    """Önce UTF-8, olmazsa Türkçe Windows kod sayfası (cp1254) dener."""
    for enc in ("utf-8-sig", "cp1254"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


class _HTMLTextParser(HTMLParser):
    BLOCK_TAGS = {"p", "br", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table"}
    SKIP_TAGS = {"script", "style", "head", "title"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip += 1
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self._skip:
            self._skip -= 1
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _HTMLTextParser()
    parser.feed(html)
    parser.close()
    return "".join(parser.parts)


def _letters(text: str) -> int:
    return sum(1 for ch in text if ch.isalpha())


def _require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise ExtractionError(
            f"OCR için '{name}' bulunamadı. Kurulum: apt-get install -y poppler-utils "
            "tesseract-ocr tesseract-ocr-tur"
        )
    return path


def ocr_image(path: Path, lang: str = OCR_LANG) -> str:
    tesseract = _require_tool("tesseract")
    proc = subprocess.run(
        [tesseract, str(path), "-", "-l", lang],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ExtractionError(f"tesseract hata verdi: {proc.stderr.strip()[:300]}")
    return proc.stdout


def ocr_pdf_page(path: Path, page_no: int, lang: str = OCR_LANG) -> str:
    """page_no 1'den başlar."""
    pdftoppm = _require_tool("pdftoppm")
    with tempfile.TemporaryDirectory() as tmp:
        prefix = Path(tmp) / "sayfa"
        proc = subprocess.run(
            [pdftoppm, "-f", str(page_no), "-l", str(page_no), "-r", str(OCR_DPI), "-png",
             str(path), str(prefix)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise ExtractionError(f"pdftoppm hata verdi: {proc.stderr.strip()[:300]}")
        images = sorted(Path(tmp).glob("sayfa*.png"))
        if not images:
            raise ExtractionError(f"pdftoppm {page_no}. sayfa için görüntü üretmedi")
        return ocr_image(images[0], lang)


def extract_pdf(path: Path) -> tuple[str, str, int]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(path))
        page_texts = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # bozuk veya şifreli PDF
        raise ExtractionError(f"PDF okunamadı: {exc}") from exc

    used_ocr = used_text = False
    out: list[str] = []
    for i, text in enumerate(page_texts, start=1):
        if _letters(text) >= MIN_LETTERS_PER_PAGE:
            out.append(text)
            used_text = True
        else:
            out.append(ocr_pdf_page(path, i))
            used_ocr = True
    method = "pdf+ocr" if used_ocr and used_text else ("ocr" if used_ocr else "pdf")
    return "\n\n".join(out), method, len(page_texts)


def extract_text_uncached(path: Path) -> tuple[str, str, int]:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ExtractionError(f"Desteklenmeyen dosya türü: {suffix}")
    if suffix == ".txt":
        return decode_bytes(path.read_bytes()), "metin", 1
    if suffix in {".htm", ".html"}:
        return html_to_text(decode_bytes(path.read_bytes())), "metin", 1
    if suffix == ".pdf":
        return extract_pdf(path)
    return ocr_image(path), "ocr", 1


def extract_text(path: Path, cache_dir: Path | None) -> ExtractedText:
    """Metni çıkarır; cache_dir verilmişse önbellekten okur/önbelleğe yazar."""
    sha = file_sha256(path)
    cache_file = cache_dir / f"{sha}.json" if cache_dir else None
    if cache_file and cache_file.exists():
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        data["source_name"] = path.name
        return ExtractedText(**data)

    raw, method, pages = extract_text_uncached(path)
    result = ExtractedText(
        sha256=sha, source_name=path.name, text=clean_text(raw), method=method, pages=pages
    )
    if cache_file:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(result), ensure_ascii=False), encoding="utf-8")
        tmp.replace(cache_file)
    return result
