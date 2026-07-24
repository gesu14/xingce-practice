#!/usr/bin/env python3
"""Export question figure clips (without answers) for graphic/chart items."""

from __future__ import annotations

import json
import re
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public" / "data" / "questions.json"
IMG_ROOT = ROOT / "public" / "images"

SOURCE_PDFS = {
    "beisen": Path("/Users/gesu/Desktop/26秋招/行测题目/TogoCareer北森题库（解析版）.pdf"),
    "plan-w1": Path(
        "/Users/gesu/Desktop/26秋招/行测题目/行测学习计划（30天）/行测学习计划（第一周）解析版.pdf"
    ),
    "plan-w2": Path(
        "/Users/gesu/Desktop/26秋招/行测题目/行测学习计划（30天）/行测学习计划（第二周）解析版.pdf"
    ),
    "plan-w3": Path(
        "/Users/gesu/Desktop/26秋招/行测题目/行测学习计划（30天）/行测学习计划（第三周）解析版.pdf"
    ),
    "mock1": Path(
        "/Users/gesu/Desktop/26秋招/行测题目/行测学习计划（30天）/行测学习计划（第四周）模拟卷1-解析版.pdf"
    ),
    "mock2": Path(
        "/Users/gesu/Desktop/26秋招/行测题目/行测学习计划（30天）/行测学习计划（第四周）模拟卷2-解析版.pdf"
    ),
}

ANSWER_RE = re.compile(r"参考答案|正确答案|【解析】")
QSTART_RE = re.compile(r"^(\d{1,3})[\.、．]")


def needs_figure(q: dict) -> bool:
    if q.get("needsImage"):
        return True
    if q.get("module") in {"图形推理", "资料分析"}:
        return True
    stem = q.get("stem") or ""
    return bool(re.search(r"第一个|第二个|空缺图形|下图|？处|根据图形", stem))


def qnum_from_id(qid: str) -> int | None:
    m = re.search(r"-(\d+)$", qid)
    return int(m.group(1)) if m else None


def find_question_anchor(page: fitz.Page, num: int):
    """Return (y0, matched_text, quality) for question `num` on page."""
    candidates = []
    for w in page.get_text("words"):
        word = w[4]
        if word.startswith(f"{num}.") or word.startswith(f"{num}、") or word.startswith(f"{num}．"):
            quality = 100 + min(len(word), 40)
            candidates.append((w[1], word, quality, abs(w[0] - 90)))
        elif word == str(num):
            candidates.append((w[1], word, 5, abs(w[0] - 90)))
    for b in page.get_text("blocks"):
        if b[6] != 0:
            continue
        text = (b[4] or "").strip().replace("\n", "")
        m = re.match(rf"^({num})[\.、．]\s*(.*)$", text)
        if m:
            quality = 120 + min(len(m.group(2)), 50)
            candidates.append((b[1], text[:60], quality, abs(b[0] - 90)))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x[2], x[3], x[0]))
    y0, label, quality, _ = candidates[0]
    return y0, label, quality


def find_answer_y(page: fitz.Page, after_y: float = 0) -> float | None:
    ys = []
    for w in page.get_text("words"):
        if ANSWER_RE.search(w[4]) and w[1] >= after_y - 2:
            ys.append(w[1])
    for b in page.get_text("blocks"):
        if b[6] != 0:
            continue
        text = b[4] or ""
        if ANSWER_RE.search(text) and b[1] >= after_y - 2:
            ys.append(b[1])
    return min(ys) if ys else None


def find_next_question_y(page: fitz.Page, num: int, after_y: float = 0) -> float | None:
    ys = []
    for b in page.get_text("blocks"):
        if b[6] != 0:
            continue
        text = (b[4] or "").strip()
        m = re.match(r"^(\d{1,3})[\.、．]", text)
        if m and int(m.group(1)) > num and b[1] > after_y + 8:
            ys.append(b[1])
    for w in page.get_text("words"):
        m = re.match(r"^(\d{1,3})[\.、．]", w[4])
        if m and int(m.group(1)) > num and w[1] > after_y + 8:
            ys.append(w[1])
    return min(ys) if ys else None


def is_watermark_image(page: fitz.Page, bbox) -> bool:
    """Large decorative overlays that aren't the actual figure."""
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    pw, ph = page.rect.width, page.rect.height
    area_ratio = (w * h) / max(pw * ph, 1)
    # watermark-like: covers a big chunk of page but not full page scan
    if area_ratio > 0.28 and w > pw * 0.55 and h > ph * 0.45:
        return True
    if w > pw * 0.95 and h > ph * 0.9:
        return True
    return False


def real_images_in_band(page: fitz.Page, y0: float, y1: float) -> list:
    imgs = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 1:
            continue
        bb = b["bbox"]
        by0, by1 = bb[1], bb[3]
        if by1 < y0 or by0 > y1:
            continue
        w = bb[2] - bb[0]
        h = by1 - by0
        if w * h < 60 * 60:
            continue
        if is_watermark_image(page, bb):
            continue
        imgs.append(bb)
    return imgs


def page_has_images_in_band(page: fitz.Page, y0: float, y1: float) -> bool:
    return bool(real_images_in_band(page, y0, y1))


def find_end_on_page(page: fitz.Page, num: int, after_y: float) -> float | None:
    """Earliest of 参考答案 / next question after after_y."""
    ans = find_answer_y(page, after_y)
    nxt = find_next_question_y(page, num, after_y)
    cands = [c for c in (ans, nxt) if c is not None]
    return min(cands) if cands else None


def render_band(page: fitz.Page, y0: float, y1: float, scale: float) -> "Image.Image":
    from PIL import Image
    import io

    x0 = max(36, page.rect.x0 + 40)
    x1 = min(page.rect.x1 - 36, page.rect.width - 40)
    top = max(page.rect.y0 + 16, y0)
    bottom = min(page.rect.y1 - 16, y1)
    if bottom <= top + 20:
        bottom = min(page.rect.y1 - 16, top + 40)
    clip = fitz.Rect(x0, top, x1, bottom)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def clip_question(doc: fitz.Document, num: int, out_path: Path, scale: float = 2.0) -> bool:
    from PIL import Image

    anchors = []
    for i in range(doc.page_count):
        hit = find_question_anchor(doc[i], num)
        if hit:
            anchors.append((i, hit[0], hit[1], hit[2]))
    if not anchors:
        return False

    # Prefer high-quality title match
    anchors.sort(key=lambda x: (-x[3], x[0]))
    start_i, y0, label, quality = anchors[0]
    if quality < 50:
        return False

    # If a shared "材料/资料" header sits above the question, include it
    page0 = doc[start_i]
    for w in page0.get_text("words"):
        if re.search(r"材料分析|资料分析|根据下表|根据下列资料", w[4]) and w[1] < y0 and w[1] >= y0 - 120:
            y0 = min(y0, w[1] - 4)
            break

    # Walk forward up to 2 pages to find answer / collect figure bands
    bands: list[tuple[int, float, float]] = []
    found_end = False
    max_page = min(doc.page_count - 1, start_i + 2)

    for pi in range(start_i, max_page + 1):
        page = doc[pi]
        after = y0 if pi == start_i else page.rect.y0 + 20
        end_y = find_end_on_page(page, num, after + (5 if pi == start_i else 0))

        if pi == start_i:
            # Include figures placed just above the title (common in this PDF)
            expand_top = y0 - 6
            for bb in real_images_in_band(page, max(page.rect.y0 + 16, y0 - 260), y0 + 10):
                # only pull in if close to / overlapping the title band
                if bb[3] >= y0 - 36:
                    expand_top = min(expand_top, bb[1] - 4)
            y1 = end_y if end_y is not None else page.rect.height - 24
            bands.append((pi, max(page.rect.y0 + 16, expand_top), y1 - 2 if end_y else page.rect.height - 24))
            if end_y is not None:
                found_end = True
                break
        else:
            # Continuation page: from top until answer/next question
            y1 = end_y if end_y is not None else page.rect.height - 24
            bands.append((pi, page.rect.y0 + 20, y1 - 2 if end_y else page.rect.height - 24))
            if end_y is not None:
                found_end = True
                break

    if not bands:
        return False

    # Ensure at least one band has real figures; if only title page with no figures,
    # and we have a continuation, drop empty title-only if continuation has figures
    has_any_fig = False
    for pi, a, b in bands:
        if page_has_images_in_band(doc[pi], a, b):
            has_any_fig = True
            break

    if not has_any_fig:
        # Try extending one more page if not found_end
        if not found_end and max_page + 1 < doc.page_count:
            pi = max_page + 1
            page = doc[pi]
            end_y = find_end_on_page(page, num, page.rect.y0 + 20)
            y1 = end_y if end_y is not None else min(page.rect.height - 24, page.rect.y0 + 520)
            bands.append((pi, page.rect.y0 + 20, y1 - 2))
            has_any_fig = page_has_images_in_band(doc[pi], page.rect.y0 + 20, y1)

    if not has_any_fig and not re.search(r"图形|下图|空缺|？|特殊|资料|图表", label):
        return False
    if not has_any_fig:
        return False

    # Render & stitch
    slices = []
    for pi, a, b in bands:
        if b <= a + 15:
            continue
        # Skip nearly empty title-only band if later pages have the figures
        # Keep title band if it has figures OR it's the only band OR height is meaningful with figures nearby
        page = doc[pi]
        band_has = page_has_images_in_band(page, a, b)
        if not band_has and len(bands) > 1 and pi == start_i and (b - a) < 80:
            # keep short title for context
            pass
        slices.append(render_band(page, a, b, scale))

    if not slices:
        return False

    width = max(im.width for im in slices)
    height = sum(im.height for im in slices)
    canvas = Image.new("RGB", (width, height), (255, 255, 255))
    y = 0
    for im in slices:
        canvas.paste(im, (0, y))
        y += im.height

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, format="PNG", optimize=True)
    return True


def main() -> None:
    questions = json.loads(DATA.read_text(encoding="utf-8"))
    open_docs: dict[str, fitz.Document] = {}
    exported = 0
    failed = []

    targets = [q for q in questions if needs_figure(q) and q.get("sourceKey") in SOURCE_PDFS]
    print(f"targets={len(targets)}")

    for q in targets:
        key = q["sourceKey"]
        pdf = SOURCE_PDFS[key]
        if not pdf.exists():
            failed.append((q["id"], "missing pdf"))
            continue
        if key not in open_docs:
            open_docs[key] = fitz.open(pdf)
        num = qnum_from_id(q["id"])
        if num is None:
            failed.append((q["id"], "bad id"))
            continue
        rel = f"/images/{key}/{q['id']}.png"
        out = ROOT / "public" / rel.lstrip("/")
        ok = clip_question(open_docs[key], num, out)
        if ok:
            q["stemImage"] = rel
            q["needsImage"] = False
            exported += 1
            print(f"OK {q['id']} -> {rel}")
        else:
            failed.append((q["id"], "no clip"))
            print(f"FAIL {q['id']}")

    for doc in open_docs.values():
        doc.close()

    DATA.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")

    # cleanup probe folder
    probe = IMG_ROOT / "_probe"
    if probe.exists():
        for p in probe.glob("*"):
            p.unlink()
        probe.rmdir()

    print(f"\nexported={exported} failed={len(failed)}")
    if failed:
        print("failures:", failed[:30])


if __name__ == "__main__":
    main()
