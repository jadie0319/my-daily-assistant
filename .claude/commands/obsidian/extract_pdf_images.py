#!/usr/bin/env python3
"""PDF에서 이미지를 추출하여 지정 디렉토리에 저장하는 CLI 스크립트.

Usage:
    python3 extract_pdf_images.py \
        --pdf "/path/to/file.pdf" \
        --output-dir "/path/to/attachments/" \
        --prefix "20260319-article-title-slug" \
        --min-size 5120 \
        --max-images 20
"""

import argparse
import json
import os
import sys

try:
    import fitz
except ImportError:
    print(
        "PyMuPDF 라이브러리를 찾을 수 없습니다. "
        "설치하려면: pip3 install PyMuPDF",
        file=sys.stderr,
    )
    sys.exit(1)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg", "avif"}


def extract_images(pdf_path, output_dir, prefix, min_size, max_images):
    if not os.path.isfile(pdf_path):
        print(f"PDF 파일을 찾을 수 없습니다: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    pdf = fitz.open(pdf_path)
    saved = []
    skipped = 0
    seen_xrefs = set()

    for page_num in range(len(pdf)):
        if len(saved) >= max_images:
            break

        page = pdf[page_num]
        images = page.get_images(full=True)

        for img_info in images:
            if len(saved) >= max_images:
                break

            xref = img_info[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)

            try:
                extracted = pdf.extract_image(xref)
            except Exception:
                skipped += 1
                continue

            if not extracted or not extracted.get("image"):
                skipped += 1
                continue

            image_bytes = extracted["image"]
            ext = extracted.get("ext", "png").lower()

            if ext not in ALLOWED_EXTENSIONS:
                skipped += 1
                continue

            if len(image_bytes) < min_size:
                skipped += 1
                continue

            seq = f"{len(saved) + 1:02d}"
            filename = f"{prefix}-{seq}.{ext}"
            filepath = os.path.join(output_dir, filename)

            try:
                with open(filepath, "wb") as f:
                    f.write(image_bytes)
                saved.append(filename)
            except OSError as e:
                print(f"파일 저장 실패: {filepath} - {e}", file=sys.stderr)
                skipped += 1

    pdf.close()
    return saved, skipped


def main():
    parser = argparse.ArgumentParser(description="PDF에서 이미지 추출")
    parser.add_argument("--pdf", required=True, help="PDF 파일 경로")
    parser.add_argument("--output-dir", required=True, help="이미지 저장 디렉토리")
    parser.add_argument("--prefix", required=True, help="저장 파일명 접두사")
    parser.add_argument(
        "--min-size", type=int, default=5120, help="최소 이미지 크기 (bytes)"
    )
    parser.add_argument(
        "--max-images", type=int, default=20, help="최대 추출 이미지 수"
    )

    args = parser.parse_args()

    saved, skipped = extract_images(
        args.pdf, args.output_dir, args.prefix, args.min_size, args.max_images
    )

    result = {"images": saved, "skipped": skipped}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
