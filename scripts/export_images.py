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

# Prefer 学生版 for crops (no 解析/答案干扰); fall back to 解析版.
_PLAN = Path("/Users/gesu/Desktop/26秋招/行测题目/行测学习计划（30天）")
_PDD = Path("/Users/gesu/Desktop/26秋招/行测题目/拼多多在线测评题库")
SOURCE_PDFS = {
    "beisen": Path("/Users/gesu/Desktop/26秋招/行测题目/TogoCareer北森题库（解析版）.pdf"),
    "plan-w1": _PLAN / "行测学习计划（第一周）学生版.pdf",
    "plan-w2": _PLAN / "行测学习计划（第二周）学生版.pdf",
    "plan-w3": _PLAN / "行测学习计划（第三周）学生版.pdf",
    "mock1": _PLAN / "行测学习计划（第四周）模拟卷1-学生版.pdf",
    "mock2": _PLAN / "行测学习计划（第四周）模拟卷2-学生版.pdf",
    "pdd-yy": _PDD / "拼多多言语26新题整理可以搜.pdf",
    "pdd-sx": _PDD / "拼多多数学26新题整理可以搜.pdf",
    "pdd-tx": _PDD / "拼多多图推26新题整理.pdf",
}
SOURCE_PDF_FALLBACKS = {
    "plan-w1": _PLAN / "行测学习计划（第一周）解析版.pdf",
    "plan-w2": _PLAN / "行测学习计划（第二周）解析版.pdf",
    "plan-w3": _PLAN / "行测学习计划（第三周）解析版.pdf",
    "mock1": _PLAN / "行测学习计划（第四周）模拟卷1-解析版.pdf",
    "mock2": _PLAN / "行测学习计划（第四周）模拟卷2-解析版.pdf",
    "beisen": Path("/Users/gesu/Desktop/26秋招/行测题目/TogoCareer北森题库.pdf"),
}

ANSWER_RE = re.compile(r"参考答案|正确答案|【解析】")
QSTART_RE = re.compile(r"^(\d{1,3})[\.、．]")


def needs_figure(q: dict) -> bool:
    if q.get("needsImage"):
        return True
    stem = q.get("stem") or ""
    expl = q.get("explanation") or ""
    # 类比/定义等文字题即使误标成图形推理也不截图
    if re.search(r"∶|根据上述定义|最能削弱|最能加强|以下哪项", stem):
        return False
    if q.get("module") == "图形推理":
        return True
    if q.get("module") == "资料分析":
        # 资料分析常依赖材料图表；无图关键词的纯计算题可跳过
        return bool(
            re.search(r"根据(以上|下列|下图|下表|资料|材料)|图示|图表|统计图|材料", stem + expl)
            or q.get("needsImage")
        )
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


def figure_bottom_for_question(
    page: fitz.Page, y0: float, soft_end: float | None, hard_limit: float | None
) -> float | None:
    """Bottom of real figures that belong to this question.

    解析版常见「左文右图」：左侧「参考答案」很靠上，右侧选项图仍继续往下。
    soft_end 是答案/下一题的文字锚点；hard_limit 是下一题题号（不可越过）。
    """
    limit = hard_limit if hard_limit is not None else page.rect.y1 - 16
    # Search a bit past soft_end so right-column figures after 参考答案 are found
    search_to = limit
    bottoms: list[float] = []
    for bb in real_images_in_band(page, max(page.rect.y0 + 16, y0 - 40), search_to):
        by0, by1 = bb[1], bb[3]
        if by0 >= limit - 4:
            continue
        # Skip leftovers of the previous question (entirely above title)
        if by1 < y0 - 12:
            continue
        # Skip figures that start well after the early soft end *and* after any
        # body text — those usually belong to the next question on the page.
        if soft_end is not None and by0 > soft_end + 40 and by0 > y0 + 220:
            continue
        bottoms.append(min(by1 + 4, limit - 2))
    return max(bottoms) if bottoms else None


def scrub_answer_text(
    page: fitz.Page,
    img: "Image.Image",
    clip: fitz.Rect,
    scale: float,
) -> "Image.Image":
    """White-out 参考答案 / 解析 blocks so practice clips don't leak keys."""
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    for b in page.get_text("blocks"):
        if b[6] != 0:
            continue
        text = (b[4] or "").strip()
        if not text:
            continue
        if not (
            ANSWER_RE.search(text)
            or re.match(r"^解析\s*[：:]", text)
            or text.startswith("解析：")
            or text.startswith("解析:")
        ):
            continue
        bx0, by0, bx1, by1 = b[:4]
        if by1 < clip.y0 or by0 > clip.y1 or bx1 < clip.x0 or bx0 > clip.x1:
            continue
        # Map page coords → pixmap pixels; pad a little for descenders
        px0 = max(0, int((max(bx0, clip.x0) - clip.x0) * scale) - 2)
        py0 = max(0, int((max(by0, clip.y0) - clip.y0) * scale) - 2)
        px1 = min(img.width, int((min(bx1, clip.x1) - clip.x0) * scale) + 4)
        py1 = min(img.height, int((min(by1, clip.y1) - clip.y0) * scale) + 6)
        if px1 > px0 and py1 > py0:
            draw.rectangle([px0, py0, px1, py1], fill=(255, 255, 255))
    return img


def extract_narrow_option_images(
    doc: fitz.Document, page: fitz.Page, y0: float, y1: float
) -> list["Image.Image"]:
    """Pull raw embedded bitmaps for skinny option columns (higher res than page paint)."""
    from PIL import Image

    out: list[tuple[float, "Image.Image"]] = []
    for info in page.get_images(full=True):
        xref = info[0]
        try:
            rects = page.get_image_rects(xref)
        except Exception:
            continue
        for rect in rects:
            if rect.y1 < y0 - 8 or rect.y0 > y1 + 8:
                continue
            if is_watermark_image(page, (rect.x0, rect.y0, rect.x1, rect.y1)):
                continue
            # Option strips in this PDF are often ~40–90pt wide and tall
            if rect.width > 140 or rect.height < 80:
                continue
            try:
                pix = fitz.Pixmap(doc, xref)
            except Exception:
                continue
            if pix.n > 4:
                continue
            if pix.n == 4:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            elif pix.n == 1:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            if pix.width < 20 or pix.height < 40:
                continue
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            out.append((rect.y0, img))
    out.sort(key=lambda t: t[0])
    return [im for _, im in out]


def ink_width(img: "Image.Image", thr: int = 200) -> int:
    rgb = img.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    xs: list[int] = []
    step = 2 if max(w, h) > 900 else 1
    for y in range(0, h, step):
        for x in range(0, w, step):
            r, g, b = px[x, y]
            if r < thr or g < thr or b < thr:
                xs.append(x)
    if not xs:
        return 0
    return max(xs) - min(xs) + 1


def prefer_option_strip_canvas(
    doc: fitz.Document,
    bands: list[tuple[int, float, float]],
    fallback: "Image.Image",
) -> "Image.Image":
    """If the page clip is mostly empty with a skinny strip, use the raw strip instead."""
    from PIL import Image

    if ink_width(fallback) >= 260:
        return fallback

    strips: list[Image.Image] = []
    for pi, a, b in bands:
        strips.extend(extract_narrow_option_images(doc, doc[pi], a, b))
    if not strips:
        return fallback

    # Stack strips; usually one
    width = max(im.width for im in strips)
    height = sum(im.height for im in strips) + 12 * (len(strips) - 1)
    canvas = Image.new("RGB", (width, height), (255, 255, 255))
    y = 0
    for im in strips:
        canvas.paste(im, ((width - im.width) // 2, y))
        y += im.height + 12
    return canvas


def trim_whitespace(img: "Image.Image", pad: int = 16, thr: int = 210) -> "Image.Image":
    """Crop near-white margins so narrow option strips aren't lost in empty canvas.

    Threshold is ink-oriented (not watermark-gray) so light TogoCareer overlays
    don't keep the full page width.
    """
    from PIL import Image

    def upscale_if_narrow(cropped: "Image.Image") -> "Image.Image":
        if cropped.width >= 420:
            return cropped
        factor = min(4.0, 720 / max(cropped.width, 1))
        return cropped.resize(
            (max(1, int(cropped.width * factor)), max(1, int(cropped.height * factor))),
            Image.Resampling.LANCZOS,
        )

    rgb = img.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    xs: list[int] = []
    ys: list[int] = []
    # Subsample for speed on tall clips
    step = 2 if max(w, h) > 900 else 1
    for y in range(0, h, step):
        for x in range(0, w, step):
            r, g, b = px[x, y]
            if r < thr or g < thr or b < thr:
                xs.append(x)
                ys.append(y)
    if not xs:
        return upscale_if_narrow(img)
    x0 = max(0, min(xs) - pad)
    y0 = max(0, min(ys) - pad)
    x1 = min(w, max(xs) + pad + 1)
    y1 = min(h, max(ys) + pad + 1)
    if x1 - x0 < 40 or y1 - y0 < 40:
        return upscale_if_narrow(img)
    cropped = img.crop((x0, y0, x1, y1))
    return upscale_if_narrow(cropped)


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
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    return scrub_answer_text(page, img, clip, scale)


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

    # If a shared "材料/资料" header sits above the question, include it.
    # 资料分析材料可能在题号上方较远处，多向上扫一段。
    page0 = doc[start_i]
    material_y = None
    for w in page0.get_text("words"):
        if re.search(r"材料分析|资料分析|根据下表|根据下列资料|根据以下资料|根据上述资料|所给资料", w[4]) and w[1] < y0:
            if w[1] >= y0 - 420:
                material_y = w[1] - 4 if material_y is None else min(material_y, w[1] - 4)
    if material_y is not None:
        y0 = min(y0, material_y)
    # Also pull in large images/tables sitting above the question on the same page
    for bb in real_images_in_band(page0, max(page0.rect.y0 + 16, y0 - 380), y0 + 8):
        if bb[3] >= y0 - 80:
            y0 = min(y0, bb[1] - 4)

    # Walk forward up to 2 pages to find answer / collect figure bands
    bands: list[tuple[int, float, float]] = []
    found_end = False
    max_page = min(doc.page_count - 1, start_i + 2)

    for pi in range(start_i, max_page + 1):
        page = doc[pi]
        after = y0 if pi == start_i else page.rect.y0 + 20
        ans_y = find_answer_y(page, after + (5 if pi == start_i else 0))
        nxt_y = find_next_question_y(page, num, after + (5 if pi == start_i else 0))
        soft_end = min([c for c in (ans_y, nxt_y) if c is not None], default=None)
        hard_limit = nxt_y
        fig_bottom = figure_bottom_for_question(page, after if pi != start_i else y0, soft_end, hard_limit)

        # Prefer covering figures even when 参考答案 appears early (two-column layout).
        end_y = soft_end
        if fig_bottom is not None:
            end_y = max(end_y, fig_bottom) if end_y is not None else fig_bottom

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
            # Continuation page: from top until answer/next question / figures
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

    canvas = prefer_option_strip_canvas(doc, bands, canvas)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas = trim_whitespace(canvas)
    canvas.save(out_path, format="PNG", optimize=True)
    return True


def resolve_pdf_key(q: dict) -> str | None:
    """Map question to SOURCE_PDFS key (拼多多用 id 前缀区分多本 PDF)。"""
    key = q.get("sourceKey") or ""
    if key in SOURCE_PDFS:
        return key
    qid = q.get("id") or ""
    if key == "pdd":
        for prefix in ("pdd-yy", "pdd-sx", "pdd-tx"):
            if qid.startswith(prefix + "-"):
                return prefix
    return None


def main() -> None:
    questions = json.loads(DATA.read_text(encoding="utf-8"))
    open_docs: dict[str, fitz.Document] = {}
    exported = 0
    failed = []

    targets = []
    for q in questions:
        if not needs_figure(q):
            continue
        pdf_key = resolve_pdf_key(q)
        if pdf_key is None:
            continue
        targets.append((q, pdf_key))
    print(f"targets={len(targets)}")

    for q, key in targets:
        # 导入阶段已裁好的拼多多图推，不要覆盖
        if q.get("stemImage") and (ROOT / "public" / q["stemImage"].split("?")[0].lstrip("/")).exists():
            continue
        pdf = SOURCE_PDFS.get(key)
        if pdf is None or not pdf.exists():
            fb = SOURCE_PDF_FALLBACKS.get(key)
            if fb is not None and fb.exists():
                pdf = fb
            else:
                failed.append((q["id"], "missing pdf"))
                continue
        if key not in open_docs:
            open_docs[key] = fitz.open(pdf)
        num = qnum_from_id(q["id"])
        if num is None:
            failed.append((q["id"], "bad id"))
            continue
        rel = f"/images/{key}/{q['id']}.png?v=6"
        out = ROOT / "public" / rel.split("?")[0].lstrip("/")
        ok = clip_question(open_docs[key], num, out)
        if not ok and key in SOURCE_PDF_FALLBACKS:
            fb = SOURCE_PDF_FALLBACKS[key]
            if fb.exists():
                fb_key = f"{key}__fb"
                if fb_key not in open_docs:
                    open_docs[fb_key] = fitz.open(fb)
                ok = clip_question(open_docs[fb_key], num, out)
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
