#!/usr/bin/env python3
"""Import 行测 questions/tips/sprint packs from local study materials."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data"
SOURCE = Path("/Users/gesu/Desktop/26秋招/行测题目")

MODULE_RE = re.compile(
    r"(?:^|\n)\s*(言语理解|数量关系|判断推理|资料分析|材料分析|常识判断|"
    r"数字推理|图形推理|数学运算|逻辑推理|思维策略|逻辑判断|"
    r"类比推理|定义判断)[：:\s]*",
    re.M,
)
# 行首可用 "A." / "A:" / "A、" / "A，" / "A 选项"；行中必须带标点，避免把「A 型号」「B 厂」当成选项
OPT_RE = re.compile(
    r"(?:^|\n)\s*([A-E])(?:\s*[\.．、，,\)：:]\s*|\s+)(?=[\u4e00-\u9fff0-9A-Za-z（(“\"])"
    r"|(?<![A-Za-z0-9])([A-E])\s*[\.．、，,\)：:]\s*(?=[\u4e00-\u9fff0-9A-Za-z（(“\"])",
    re.M,
)

# 选项正文若以这些词开头，多半是题干里的「A 型号 / B 厂」误伤
_OPT_FALSE_START = re.compile(
    r"^(型号|厂|地|车|队|班|组|级|公司|企业|部门|工程|方案|产品|商品)"
)


def split_options(body: str) -> tuple[str, list[dict[str, str]]]:
    matches = list(OPT_RE.finditer(body))
    # 过滤「答案为 C 选项 / 故选 A」这类解析收尾，避免当成选项锚点
    filtered: list[re.Match[str]] = []
    for m in matches:
        letter_i = 1 if m.group(1) else 2
        letter_start = m.start(letter_i)
        ctx = body[max(0, letter_start - 8) : letter_start]
        if re.search(r"(答案为|答案是|答案选|本题选|故选|选择)$", ctx):
            continue
        filtered.append(m)
    matches = filtered
    if len(matches) < 2:
        return body.strip(), []
    # Prefer the last contiguous A-D/E block
    start_idx = 0
    for i, m in enumerate(matches):
        key = m.group(1) or m.group(2)
        if key == "A":
            start_idx = i
    matches = matches[start_idx:]
    stem = body[: matches[0].start()].strip()
    options: list[dict[str, str]] = []
    for i, m in enumerate(matches):
        key = m.group(1) or m.group(2)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        text = body[m.end() : end].strip()
        text = re.split(r"\n\s*参考答案|\n\s*[A-E]【解析】", text)[0].strip()
        options.append({"key": key, "text": text})
    # Deduplicate keys keeping first
    seen = set()
    uniq = []
    for opt in options:
        if opt["key"] in seen:
            continue
        # 丢掉「A 型号」这类假选项
        if _OPT_FALSE_START.match(opt["text"] or ""):
            continue
        seen.add(opt["key"])
        uniq.append(opt)
    # 假选项过滤后不足，视为失败，交给其他解析器
    if len(uniq) < 2:
        return body.strip(), []
    return stem, uniq


def split_plain_option_lines(chunk: str) -> tuple[str, list[dict[str, str]]]:
    """无 A/B/C/D 标记的四行短选项（如「高 50 元 / 低 50 元 …」）。"""
    lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
    if len(lines) < 5:
        return chunk.strip(), []

    def pack(stem_lines: list[str], opt_lines: list[str]) -> tuple[str, list[dict[str, str]]] | None:
        if len(opt_lines) != 4:
            return None
        if not all(2 <= len(ln) <= 40 for ln in opt_lines):
            return None
        if any(re.search(r"答案|解析|因此|所以选择|解法", ln) for ln in opt_lines):
            return None
        if any(re.match(r"^[A-E](?:\s*[\.．、\)]|\s+)", ln) for ln in opt_lines):
            return None
        stem = "\n".join(stem_lines).strip()
        if len(stem) < 8:
            return None
        if not re.search(r"[（(]\s*[）)]|？|\?|问", stem):
            return None
        options = [{"key": k, "text": t} for k, t in zip("ABCD", opt_lines)]
        return stem, options

    # 常见：最后 4 行是选项；或倒数第 5 行是单独的「（ ）」
    trial = pack(lines[:-4], lines[-4:])
    if trial:
        return trial
    if len(lines) >= 6 and re.fullmatch(r"[（(]\s*[）)][。.]?", lines[-5]):
        trial = pack(lines[:-4], lines[-4:])
        if trial:
            return trial
    return chunk.strip(), []


MODULE_ALIAS = {
    "材料分析": "资料分析",
}


def pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml")
    text = re.sub(rb"</w:p>", b"\n", xml)
    text = re.sub(rb"<[^>]+>", b"", text)
    return text.decode("utf-8", errors="ignore")


def fingerprint(stem: str, extra: str = "") -> str:
    cleaned = re.sub(r"\s+", "", (stem or "") + "|" + (extra or ""))[:100]
    return hashlib.md5(cleaned.encode("utf-8")).hexdigest()[:12]


def module_at(text: str, pos: int, default: str = "未分类") -> str:
    before = text[:pos]
    mods = list(MODULE_RE.finditer(before))
    if not mods:
        return default
    raw = mods[-1].group(1)
    return MODULE_ALIAS.get(raw, raw)


def parse_ref_answer(text: str, source: str, source_label: str) -> list[dict[str, Any]]:
    matches = list(re.finditer(r"参考答案[：:]\s*([A-E])\s*\n?解析[：:]?\s*", text))
    if not matches:
        matches = list(re.finditer(r"参考答案[：:]\s*([A-E])", text))
    questions: list[dict[str, Any]] = []
    for i, m in enumerate(matches):
        prev_end = matches[i - 1].end() if i else 0
        chunk = text[prev_end : m.start()]
        qnums = list(re.finditer(r"(?:^|\n)\s*(\d{1,3})[\.、．]\s*", chunk))
        if not qnums:
            continue
        qn = qnums[-1]
        body = chunk[qn.end() :].strip()
        stem, options = split_options(body)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        expl = text[m.end() : end]
        # PDF often has "68.下表" / "63.NEO" with no space after the dot
        expl = re.split(r"(?:^|\n)\s*\d{1,3}[\.、．]\s*", expl, maxsplit=1)[0].strip()
        # Also cut if a following question's options leaked in
        expl = re.split(
            r"(?:^|\n)\s*[A-E][\.．、\)]\s*\S+\s*\n\s*[A-E][\.．、\)]",
            expl,
            maxsplit=1,
        )[0].strip()
        # Drop trailing stem-like lines before an option block remnant
        if re.search(r"(?:^|\n)\s*[A-D][\.．、\)]\s*\S+", expl):
            expl = re.split(r"(?:^|\n)\s*(?=[A-D][\.．、\)]\s*\S)", expl, maxsplit=1)[0].strip()
            # also drop last paragraph if it looks like a new question prompt
            parts = [p for p in re.split(r"\n\s*\n+", expl) if p.strip()]
            if len(parts) >= 2 and re.search(r"[？?]|（\s*）|\(\s*\)", parts[-1]) and not re.search(
                r"因此|所以|故|答案|选择", parts[-1]
            ):
                expl = "\n\n".join(parts[:-1]).strip()
        module = module_at(text, prev_end + qn.start())
        needs_image = bool(
            re.search(r"第一个|第二个|第三个|第四个|图形|下图|？处", body)
        ) or (not options and module in {"图形推理", "资料分析"})
        qid = f"{source}-{int(qn.group(1)):03d}"
        questions.append(
            {
                "id": qid,
                "source": source_label,
                "sourceKey": source,
                "module": module,
                "stem": stem or body[:200],
                "options": options,
                "answer": m.group(1),
                "explanation": expl,
                "needsImage": needs_image,
                "highYield": source == "beisen",
                "fp": fingerprint(stem or body, m.group(1)+(options[0]['text'] if options else '')),
            }
        )
    return questions


def parse_bracket_answer(text: str, source: str, source_label: str) -> list[dict[str, Any]]:
    matches = list(re.finditer(r"(?:^|\n)\s*([A-E])【解析】", text))
    questions: list[dict[str, Any]] = []
    for i, m in enumerate(matches):
        prev_end = matches[i - 1].end() if i else 0
        chunk = text[prev_end : m.start()]
        qnums = list(re.finditer(r"(?:^|\n)\s*(\d{1,3})[\.、．]?\s*", chunk))
        qn = None
        for cand in reversed(qnums):
            n = int(cand.group(1))
            if 1 <= n <= 100:
                qn = cand
                break
        if not qn:
            continue
        body = chunk[qn.end() :].strip()
        stem, options = split_options(body)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        expl = text[m.end() : end]
        expl = re.split(r"(?:^|\n)\s*\d{1,3}[\.、．]\s*", expl, maxsplit=1)[0].strip()
        if re.search(r"(?:^|\n)\s*[A-D][\.．、\)]\s*\S+", expl):
            expl = re.split(r"(?:^|\n)\s*(?=[A-D][\.．、\)]\s*\S)", expl, maxsplit=1)[0].strip()
        module = module_at(text, prev_end + qn.start(), default="综合")
        # Heuristic for mocks without section headers
        if module == "综合":
            if re.search(r"图形|第一个|第二个|下图|？处|方格|阴影", body) or len(body) < 40:
                module = "图形推理"
            elif re.search(r"%|增长|比重|万元|统计|同比", body):
                module = "资料分析"
            elif re.search(r"多少|几人|公里|利率|速度|元|岁|小时", body):
                module = "数量关系"
            elif re.search(r"意在|主旨|说明|填入|推断|指代|理解正确", body):
                module = "言语理解"
            elif re.search(r"推出|前提|削弱|加强|论证", body):
                module = "逻辑判断"
        needs_image = bool(
            re.search(r"第一个|第二个|第三个|第四个|图形|下图|？处", body)
        ) or (not options and module in {"图形推理", "资料分析"})
        qid = f"{source}-{int(qn.group(1)):03d}"
        questions.append(
            {
                "id": qid,
                "source": source_label,
                "sourceKey": source,
                "module": module,
                "stem": stem or body[:200],
                "options": options,
                "answer": m.group(1),
                "explanation": expl,
                "needsImage": needs_image,
                "highYield": False,
                "fp": fingerprint(stem or body, m.group(1)+(options[0]['text'] if options else '')),
            }
        )
    return questions


def split_inline_abcd(chunk: str) -> tuple[str, list[dict[str, str]]]:
    """Parse compact 'A.1 B.2 C.3 D.4' / 'A:… B:…' / 'A、… B、…' option blocks."""
    sep = r"[\.．、，,\)：:]"
    pattern = re.compile(
        rf"([A-D]){sep}\s*([^A-D]*?)(?=(?:\s*[A-D]{sep})|$)"
    )
    # Find the last complete A..D run (allow : / 、 / ， as separator — 拼多多常见)
    runs = list(re.finditer(rf"A{sep}\s*.*?D{sep}\s*\S+", chunk, re.S))
    if not runs:
        return chunk.strip(), []
    run = runs[-1]
    block = chunk[run.start() :]
    stem = chunk[: run.start()].strip()
    opts = []
    for m in pattern.finditer(block):
        opts.append({"key": m.group(1), "text": m.group(2).strip()})
    # Keep first A-D only
    seen: set[str] = set()
    uniq = []
    for o in opts:
        if o["key"] in seen:
            continue
        seen.add(o["key"])
        uniq.append(o)
        if len(uniq) >= 4:
            break
    return stem, uniq


def _fix_char_per_line_noise(text: str) -> str:
    """修正常见 OCR/抽取噪点：每个字单独一行。"""
    lines = text.splitlines()
    out: list[str] = []
    buf: list[str] = []
    for ln in lines:
        s = ln.strip()
        if len(s) == 1 and re.match(r"[\u4e00-\u9fffA-Za-z0-9]", s):
            buf.append(s)
            continue
        if buf:
            out.append("".join(buf))
            buf = []
        out.append(ln)
    if buf:
        out.append("".join(buf))
    return "\n".join(out)


# Word 题库常见收尾语：上一题解析与本题题干挤在同一段里，靠这些标记切开。
DOCX_EXPL_END_RE = re.compile(
    r"(?:"
    r"因此[，,\s]*本题(?:正确答案|答案)?(?:为|选择|选)\s*[A-E]\s*选项?|"
    r"因此[，,\s]*本题选择\s*[A-E]\s*选项?|"
    r"因此本题选择\s*[A-E]\s*选项?|"
    r"因此[，,\s]*答案(?:为|选择|选)\s*[A-E]\s*选项?|"
    r"所以(?:本题)?(?:答案)?(?:为|选择|选)\s*[A-E]\s*选项?|"
    r"所以选择\s*[A-E]|"
    r"故(?:本题)?(?:答案为|选择|选)\s*[A-E]\s*选项?|"
    r"答案(?:为|选择|选)\s*[A-E]\s*选项?|"
    r"本题(?:正确答案|答案为|选择|选)\s*[A-E]\s*选项?|"
    r"正确答案(?:为|是)?\s*[A-E]"
    r")[。.．]?"
)


def _looks_like_docx_explanation(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if re.match(r"^(【解析】|解析[一二三四五六七八九十]+|解法|方法[一二三]|第一种|第二种|第三种)", t):
        return True
    if DOCX_EXPL_END_RE.search(t) and not re.search(r"[（(]\s*[）)]|？|\?", t):
        return True
    if len(t) > 180 and not re.search(r"[（(]\s*[）)]|？|\?|（\s*）", t):
        return True
    return False


def _docx_question_body(chunk: str) -> str:
    """去掉粘在前面的上一题解析，只保留本题题干+选项区域。"""
    chunk = chunk.strip()
    ends = list(DOCX_EXPL_END_RE.finditer(chunk))
    if ends:
        after = chunk[ends[-1].end() :].strip()
        if len(after) >= 3:
            return after
    parts = [p.strip() for p in re.split(r"\n\s*\n+", chunk) if p.strip()]
    if len(parts) >= 2:
        for i in range(len(parts) - 1, -1, -1):
            if _looks_like_docx_explanation(parts[i]):
                continue
            if re.search(r"题库|讲义|详解|目录", parts[i]) and len(parts[i]) < 40:
                continue
            return "\n\n".join(parts[i:])
    return chunk


def _docx_stem_and_options(chunk: str) -> tuple[str, list[dict[str, str]]]:
    work = _docx_question_body(chunk)
    stem, options = split_inline_abcd(work)
    if len(options) < 4:
        stem2, options2 = split_options(work)
        if len(options2) >= len(options):
            stem, options = stem2, options2
    if len(options) < 4:
        stem3, options3 = split_plain_option_lines(work)
        if len(options3) > len(options):
            stem, options = stem3, options3
    # 选项残缺时回退到整段再试一次
    if len(options) < 2:
        stem, options = split_inline_abcd(chunk)
        if len(options) < 4:
            stem2, options2 = split_options(chunk)
            if len(options2) >= len(options):
                stem, options = stem2, options2
        if len(options) < 4:
            stem3, options3 = split_plain_option_lines(chunk)
            if len(options3) > len(options):
                stem, options = stem3, options3
    return stem, options


def take_docx_stem(before_options: str) -> str:
    """从「上一题解析 + 本题题干」中只留下本题题干。"""
    text = _docx_question_body(before_options)
    text = re.sub(r"^能力测试提分题库[^\n]*\n*", "", text).strip()
    text = re.sub(r"^【解析】\s*", "", text).strip()

    parts = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    if len(parts) > 1:
        for part in reversed(parts):
            if re.search(r"题库|讲义|详解|目录", part) and len(part) < 40:
                continue
            if _looks_like_docx_explanation(part):
                continue
            text = part
            break
        else:
            text = parts[-1]

    if _looks_like_docx_explanation(text) or re.match(r"^(解法|解析|方法|第[一二三])", text):
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for ln in reversed(lines):
            if len(ln) <= 120 and re.search(r"[（(]\s*[）)]|？|\?|，|,", ln):
                text = ln
                break

    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    text = re.sub(r"^能力测试提分题库[^\n]*\n+", "", text).strip()
    return text


def take_docx_explanation(region: str) -> str:
    """从「本题解析 + 下一题题干选项」中只留下本题解析。"""
    region = region.strip()
    if not region:
        return ""

    body = re.sub(r"^【解析】\s*", "", region)
    ends = list(DOCX_EXPL_END_RE.finditer(body))
    if ends:
        return body[: ends[-1].end()].strip()

    # 无收尾语：用下一题选项块定位，再丢掉最后一块题干
    before_opts, next_opts = _docx_stem_and_options(body)
    if len(next_opts) >= 2:
        parts = [p.strip() for p in re.split(r"\n\s*\n+", before_opts) if p.strip()]
        if len(parts) >= 2:
            return "\n\n".join(parts[:-1]).strip()
        return before_opts.strip()

    parts = [p.strip() for p in re.split(r"\n\s*\n+", body) if p.strip()]
    if len(parts) >= 2:
        return "\n\n".join(parts[:-1]).strip()

    if len(body) < 100 and re.search(r"[（(]\s*[）)]|？|\?", body) and not re.search(
        r"解法|作差|递推|设|根据题意|赋值", body
    ):
        return ""

    runs = list(re.finditer(r"(?:^|\n)\s*A[\.．、\)]\s*.*?D[\.．、\)]\s*\S+", body, re.S))
    if runs:
        body = body[: runs[0].start()].strip()
    return body.strip()


def clean_docx_stem(stem: str) -> str:
    return take_docx_stem(stem)


def parse_docx_bank(text: str, source: str, source_label: str, module: str) -> list[dict[str, Any]]:
    """Word 精选题库：版式是 题干+选项 → 答案/解析 → 下一题题干+选项。

    旧逻辑把「上一题解析」算进本题题干、把「下一题题干」算进本题解析。
    这里按选项块与解析收尾语把两端切开。
    """
    matches = list(re.finditer(r"答案[：:]\s*([A-E])\s*解析[：:]?\s*", text))
    questions: list[dict[str, Any]] = []
    seq = 0
    for i, m in enumerate(matches):
        prev_end = matches[i - 1].end() if i else 0
        chunk = text[prev_end : m.start()].strip()

        stem_raw, options = _docx_stem_and_options(chunk)
        stem = take_docx_stem(stem_raw)

        if i + 1 < len(matches):
            expl = take_docx_explanation(text[m.end() : matches[i + 1].start()])
        else:
            expl = re.sub(r"^【解析】\s*", "", text[m.end() :].strip())
            expl_ends = list(DOCX_EXPL_END_RE.finditer(expl))
            if expl_ends:
                expl = expl[: expl_ends[-1].end()].strip()

        if len(options) < 2 or len(stem) < 3:
            continue
        if re.fullmatch(r".{0,30}(题库|讲义|详解).{0,30}", stem):
            continue
        # 过滤仍明显是解析残片的「题干」
        if re.match(r"^(解法|解析|方法|第一种|第二种|因此|×)", stem) and not re.search(
            r"[（(]\s*[）)]|？|\?", stem
        ):
            continue
        if len(stem) < 10 and not re.search(r"[（(]\s*[）)]|？|\?", stem):
            continue
        seq += 1
        questions.append(
            {
                "id": f"{source}-{seq:03d}",
                "source": source_label,
                "sourceKey": source,
                "module": module,
                "stem": stem,
                "options": options[:5],
                "answer": m.group(1),
                "explanation": expl,
                "needsImage": False,
                "highYield": False,
                "fp": fingerprint(stem, m.group(1) + options[0]["text"]),
            }
        )
    # 配对修复：若第 i 题解析末尾粘着第 i+1 题题干，截断；若整段都是下一题，清空
    for i in range(len(questions) - 1):
        expl = questions[i].get("explanation") or ""
        nxt = (questions[i + 1].get("stem") or "").strip()
        if len(nxt) < 12 or not expl:
            continue
        cut_at = -1
        for length in (min(48, len(nxt)), 36, 28, 20, 16):
            needle = nxt[:length].strip()
            if len(needle) < 12:
                continue
            idx = expl.find(needle)
            if idx >= 0:
                cut_at = idx
                break
            compact_needle = re.sub(r"\s+", "", needle)
            compact_expl = re.sub(r"\s+", "", expl)
            pos = compact_expl.rfind(compact_needle)
            if pos >= 0 and pos >= len(compact_expl) - len(compact_needle) - 8:
                ch = needle[0]
                approx = expl.rfind(ch)
                while approx >= 0:
                    window = re.sub(r"\s+", "", expl[approx:])
                    if window.startswith(compact_needle):
                        cut_at = approx
                        break
                    approx = expl.rfind(ch, 0, approx)
                if cut_at >= 0:
                    break
        if cut_at == 0:
            # 原文缺解析，整段其实是下一题题干
            questions[i]["explanation"] = ""
        elif cut_at > 0:
            questions[i]["explanation"] = expl[:cut_at].strip()
    return questions


def dedupe(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Prefer beisen > plan > docx when fingerprints collide
    priority = {
        "beisen": 0,
        "pdd": 1,
        "plan-w1": 2,
        "plan-w2": 2,
        "plan-w3": 2,
        "mock1": 3,
        "mock2": 3,
    }
    by_fp: dict[str, dict[str, Any]] = {}
    for q in questions:
        fp = q["fp"]
        if fp not in by_fp:
            by_fp[fp] = q
            continue
        old = by_fp[fp]
        old_p = priority.get(old["sourceKey"], 9)
        new_p = priority.get(q["sourceKey"], 9)
        # Prefer richer explanation / more options
        if new_p < old_p:
            by_fp[fp] = q
        elif new_p == old_p and len(q.get("explanation", "")) > len(old.get("explanation", "")):
            by_fp[fp] = q
    # Keep beisen highYield even after dedupe
    out = []
    for q in by_fp.values():
        q = dict(q)
        if q["sourceKey"] == "beisen":
            q["highYield"] = True
        q.pop("fp", None)
        out.append(q)
    out.sort(key=lambda x: (x["module"], x["id"]))
    return out


def build_tips() -> list[dict[str, Any]]:
    tips = [
        {
            "id": "tip-yy-zhuti",
            "module": "言语理解",
            "title": "主旨概括：抓住论述对象",
            "summary": "找文段核心论述对象（谁/什么）与作者态度，排除无中生有、偷换对象、过度推断。",
            "points": [
                "首句或尾句常点明对象；并列结构看共同指向",
                "双主语时选项也需覆盖双对象",
                "干扰项常见：只说手段不说对象、把例子当主旨",
            ],
        },
        {
            "id": "tip-yy-tiankong",
            "module": "言语理解",
            "title": "逻辑填空：对象搭配与语义轻重",
            "summary": "近义词先看搭配对象，再看轻重、感情色彩、侧重点。",
            "points": [
                "对象搭配：肤浅（学识）vs 浮浅（品德）",
                "语义轻重：搜集重于收集",
                "感情色彩：敦促（褒）vs 督促（中）",
            ],
        },
        {
            "id": "tip-sl-rongchi",
            "module": "数量关系",
            "title": "容斥原理速记",
            "summary": "两集合：总数-都不=A+B-AB；三集合按已知量选公式或画图。",
            "points": [
                "两集合：总−都不=A+B−AB",
                "三集合标准：总−都不=A+B+C−(AB+AC+BC)+ABC",
                "选项尾数不同可先用尾数法",
            ],
        },
        {
            "id": "tip-sl-sixiang",
            "module": "思维策略",
            "title": "思维策略：极端与构造",
            "summary": "问最多/最少时，构造极端情况；比赛得分类先算总分守恒。",
            "points": [
                "最多没比：先构造分数尽量小且互不相同",
                "行程相遇：时间差×速度差/和",
                "先定性再计算，能排除先排除",
            ],
        },
        {
            "id": "tip-tx-shuliang",
            "module": "图形推理",
            "title": "图形推理：数量类",
            "summary": "元素凌乱优先数点、线、角、面、素；注意一笔画与奇点。",
            "points": [
                "点：交点/端点；线：直曲/笔画数",
                "面：封闭空间个数；素：种类与部分",
                "九宫格常见 A+B=C 或常数和",
            ],
        },
        {
            "id": "tip-tx-weizhi",
            "module": "图形推理",
            "title": "图形推理：位置与样式",
            "summary": "相同元素看平移旋转翻转；相似元素看加减同异与黑白运算。",
            "points": [
                "平移：方向+步数（常数/等差/周期）",
                "样式：遍历、求同求异、黑白运算",
                "属性：对称、曲直、开闭",
            ],
        },
        {
            "id": "tip-zl-zengzhang",
            "module": "资料分析",
            "title": "资料分析：增长率与比重",
            "summary": "增长率=(现期-基期)/基期；比重比较看部分增速与整体增速。",
            "points": [
                "现期=基期×(1+r)",
                "部分增速>整体增速 → 比重上升",
                "先看材料单位与时间口径再算",
            ],
        },
        {
            "id": "tip-sz-duiji",
            "module": "数字推理",
            "title": "数字推理：作差与递推",
            "summary": "优先作差/作和看多级数列；再试递推、倍数、位运算。",
            "points": [
                "两次作差成等差/等比很常见",
                "前两项运算得第三项（加/乘/取个位）",
                "分式数列拆分子分母分别找规律",
            ],
        },
    ]
    return tips


def reclassify_question(q: dict[str, Any]) -> None:
    """Fix module drift after 图形推理 section bleeds into later topics."""
    blob = "\n".join(
        [
            q.get("stem") or "",
            q.get("explanation") or "",
            " ".join(o.get("text") or "" for o in q.get("options") or []),
        ]
    )
    # Graphic cues first — more specific
    if re.search(r"空缺图形|根据图形规律|上图第|哪一个图形|灰色正方形|？号的图形|找出不同|特殊的", blob):
        q["module"] = "图形推理"
        return
    if re.search(r"根据下表|根据图表|下图是|材料分析|资产负债|营业收入|同比增速|流动资产|销售额|股票的涨跌", blob):
        q["module"] = "资料分析"
        q["patternTag"] = "资料计算"
        q["tipIds"] = ["tip-zl-zengzhang"]
        return
    if re.search(r"意在说明|这段文字|主旨|填入|最恰当", blob) and q.get("module") == "图形推理":
        q["module"] = "言语理解"


def assign_tips(questions: list[dict[str, Any]]) -> None:
    tip_by_module = {
        "言语理解": ["tip-yy-zhuti", "tip-yy-tiankong"],
        "数量关系": ["tip-sl-rongchi", "tip-sl-sixiang"],
        "思维策略": ["tip-sl-sixiang", "tip-sl-rongchi"],
        "图形推理": ["tip-tx-shuliang", "tip-tx-weizhi"],
        "资料分析": ["tip-zl-zengzhang"],
        "数字推理": ["tip-sz-duiji"],
        "逻辑判断": ["tip-yy-zhuti"],
        "判断推理": ["tip-tx-shuliang"],
        "数学运算": ["tip-sl-rongchi", "tip-sl-sixiang"],
    }
    for q in questions:
        reclassify_question(q)
        tips = tip_by_module.get(q["module"], [])
        q["tipIds"] = tips
        # pattern tags for sprint grouping
        stem = q.get("stem", "") + q.get("explanation", "")
        if q["module"] == "言语理解":
            if re.search(r"意在说明|主旨|主要说明|这段文字", stem):
                q["patternTag"] = "主旨概括"
            elif re.search(r"填入|空格|横线", stem):
                q["patternTag"] = "逻辑填空"
            elif re.search(r"推断|推出|正确的是|无法推出", stem):
                q["patternTag"] = "细节推断"
            else:
                q["patternTag"] = "言语综合"
        elif q["module"] == "图形推理":
            if re.search(r"数量|交点|黑点|封闭", stem):
                q["patternTag"] = "数量规律"
            elif re.search(r"位置|旋转|平移|顺时针", stem):
                q["patternTag"] = "位置规律"
            elif re.search(r"特殊|不同于|找不同", stem):
                q["patternTag"] = "找不同"
            else:
                q["patternTag"] = "图形综合"
        elif q["module"] in {"数量关系", "思维策略", "数学运算"}:
            if re.search(r"容斥|既.*又|都不", stem):
                q["patternTag"] = "容斥原理"
            else:
                q["patternTag"] = "数量思维"
        elif q["module"] == "资料分析":
            q["patternTag"] = "资料计算"
        elif q["module"] == "数字推理":
            q["patternTag"] = "数列规律"
        else:
            q["patternTag"] = q["module"]


def build_sprint_packs(questions: list[dict[str, Any]], tips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    beisen = [q for q in questions if q.get("sourceKey") == "beisen"]
    tip_ids = {t["id"] for t in tips}
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for q in beisen:
        key = (q["module"], q.get("patternTag") or "综合")
        groups[key].append(q)

    must_remember = {
        ("言语理解", "主旨概括"): [
            "先找论述对象，再看作者想强调什么",
            "双主语选项也要双覆盖",
            "例子、背景不是主旨",
        ],
        ("言语理解", "细节推断"): [
            "忠于原文，不脑补因果",
            "绝对化表述优先排除",
            "问‘无法推出’时找无中生有项",
        ],
        ("言语理解", "言语综合"): [
            "先判断题型再下笔",
            "选项对比差异点",
            "不确定时回原文定位",
        ],
        ("资料分析", "资料计算"): [
            "先看清单位、时间和问法",
            "增长率=(现期-基期)/基期",
            "能口算先估算再精算",
        ],
        ("图形推理", "数量规律"): [
            "元素乱 → 数点线面素",
            "注意一笔画与奇点",
            "九宫格先看行/列运算",
        ],
        ("图形推理", "位置规律"): [
            "相同元素看平移旋转",
            "记录方向与步数",
            "翻转别和旋转混淆",
        ],
        ("图形推理", "找不同"): [
            "先排除数量，再看位置/属性",
            "对称、曲直、开闭常考",
            "只找一项特殊即可",
        ],
        ("图形推理", "图形综合"): [
            "先看元素是否相同",
            "相同走位置，凌乱走数量，相似走样式",
            "实在不行看属性",
        ],
    }

    packs: list[dict[str, Any]] = []
    pack_i = 1
    for (module, tag), qs in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1])):
        chunk_size = 6 if len(qs) > 8 else max(len(qs), 1)
        chunks = [qs[start : start + chunk_size] for start in range(0, len(qs), chunk_size)]
        multi = len(chunks) > 1
        for part_i, chunk in enumerate(chunks, start=1):
            if not chunk:
                continue
            tip_list = []
            for q in chunk:
                for tid in q.get("tipIds") or []:
                    if tid in tip_ids and tid not in tip_list:
                        tip_list.append(tid)
            title = f"{module}·{tag}"
            if multi:
                title += f"（{part_i}）"
            packs.append(
                {
                    "id": f"sprint-{pack_i:02d}",
                    "title": title,
                    "module": module,
                    "estMinutes": max(8, min(15, len(chunk) * 2)),
                    "tipIds": tip_list[:3],
                    "questionIds": [q["id"] for q in chunk],
                    "mustRemember": must_remember.get(
                        (module, tag),
                        [
                            "先定性题型再做题",
                            "对照解析沉淀套路",
                            "错题当天再过一遍",
                        ],
                    ),
                }
            )
            pack_i += 1
    return packs


def pdf_text_pages(path: Path, start: int = 0, end: int | None = None) -> str:
    """Extract text from a page range via PyMuPDF (better for mixed PDFs)."""
    try:
        import fitz
    except ImportError:
        # pypdf 回退也必须尊重页码，否则会把「无解析」前半本整本读进来
        reader = PdfReader(str(path))
        last = end if end is not None else len(reader.pages)
        parts = []
        for i in range(max(0, start), min(last, len(reader.pages))):
            parts.append(reader.pages[i].extract_text() or "")
        return "\n".join(parts)
    doc = fitz.open(path)
    try:
        last = end if end is not None else doc.page_count
        parts = []
        for i in range(max(0, start), min(last, doc.page_count)):
            parts.append(doc[i].get_text() or "")
        return "\n".join(parts)
    finally:
        doc.close()


PDD_ANSWER_RE = re.compile(
    # 「正确答案A / 正确答案：A」
    r"正确答案\s*[：:;；]?\s*([A-E])(?:\s*[\.．、)]?)?"
    # 「答案：A / 答案:B」（须有冒号，避免「答案为B」）
    r"|(?<![为是选正确])答案\s*[：:;；]\s*([A-E])(?:\s*[\.．、)]?)?"
    # 「答案B / 答案A 该小店…」（无冒号紧贴字母；排除「答案是/选」）
    r"|(?<![为是选正确])答案\s*([A-E])(?=[\s\.．、，,）)\]]|$)"
    r"|答\s*[：:;；]\s*([A-E])",
)
PDD_NEXT_Q_RE = re.compile(
    r"(?:^|\n)\s*(?:"
    r"\d{1,3}\s*[、．.\)]\s*"
    r"|\d{1,3}\s*\.\s*"
    r"|\d{1,3}\s*\(?\s*单选题\s*\)?"
    r"|\(\s*单选题\s*\)"
    r"|第\s*\d+\s*题"
    r")",
)
PDD_EXPL_START_RE = re.compile(
    r"(?:题目解析|文本解析|解析\s*[：:]|解\s*[：:])",
)
# 解析 / 题干边界：裸「(单选题)」在拼多多 PDF 里很常见
PDD_Q_BOUNDARY_RE = re.compile(
    r"(?:^|\n)\s*(?:"
    r"\d{1,3}\s*[、．.\)]\s*"
    r"|\d{1,3}\s*\(?\s*单选题\s*\)?"
    r"|\(\s*单选题\s*\)"
    r"|第\s*\d+\s*题"
    r")"
)


def _strip_leading_pdd_explanation(stem: str) -> str:
    """题干若粘了上一题解析，取最后一个题号 / (单选题) 之后的正文。"""
    s = (stem or "").strip()
    if not s:
        return s
    # 「文本解析：」残留的开头冒号
    s = re.sub(r"^：\s*", "", s).strip()
    heads = list(PDD_Q_BOUNDARY_RE.finditer(s))
    if heads:
        # 取最后一个题号后的内容（前面是粘连的解析）
        s = s[heads[-1].end() :].strip()
        s = re.sub(r"^：\s*", "", s).strip()
    # 仍像解析开头则再切一次常见收尾
    if re.match(
        r"^(由题意可知|文段|题干中|题中意思|所以答案选|故选|选择\s*[A-E]|A\s*项|B\s*项)",
        s,
    ):
        # 找不到题号时，若整段都是解析则交给后续过滤
        cut = re.search(
            r"(?:所以答案选\s*[A-E]|故选\s*[A-E]|选择\s*[A-E]|正确答案\s*[A-E])[。.]?\s*",
            s,
        )
        if cut:
            rest = s[cut.end() :].strip()
            if len(rest) >= 12:
                s = rest
    s = re.sub(r"^\(?\s*单选题\s*\)?\s*", "", s).strip()
    return s


def _cut_pdd_explanation(expl: str) -> str:
    """解析截止到下一题题号 / (单选题)，并去掉选项块粘连。"""
    expl = (expl or "").strip()
    if not expl:
        return expl
    parts = PDD_Q_BOUNDARY_RE.split(expl, maxsplit=1)
    expl = parts[0].strip()
    expl = re.sub(r"^[\.．、)\s：:]+", "", expl).strip()
    bleed = re.search(
        r"(?:^|\n)\s*A[\.．、\)：:]\s*\S[\s\S]{0,200}?\n\s*B[\.．、\)：:]\s*\S[\s\S]{0,200}?\n\s*C[\.．、\)：:]",
        expl,
    )
    if bleed and bleed.start() > 20:
        expl = expl[: bleed.start()].strip()
    return expl


def _scrub_pdd_noise(text: str) -> str:
    text = re.sub(r"笔试代答[^\n]*\n?", "", text)
    text = re.sub(r"全题库皆可[^\n]*\n?", "", text)
    text = re.sub(r"考试助攻[^\n]*\n?", "", text)
    text = re.sub(r"\+V\s*咨询[^\n]*\n?", "", text)
    text = re.sub(r"加V[：:][^\n]*\n?", "", text)
    return text


def parse_pdd_bank(
    text: str,
    source: str,
    source_label: str,
    module: str,
    id_prefix: str,
) -> list[dict[str, Any]]:
    """拼多多题库：答案 / 正确答案 / 答：X + 解析。"""
    text = _scrub_pdd_noise(text)
    text = _fix_char_per_line_noise(text)
    matches = list(PDD_ANSWER_RE.finditer(text))
    questions: list[dict[str, Any]] = []
    seq = 0
    for i, m in enumerate(matches):
        answer = next((g for g in m.groups() if g), None)
        if not answer:
            continue
        prev_end = matches[i - 1].end() if i else 0
        chunk = text[prev_end : m.start()].strip()
        # 先找题号：解析在题干前面时，不能先按「解析」切开（会把题干一起丢掉）
        qheads = list(PDD_NEXT_Q_RE.finditer(chunk))
        if qheads:
            body = chunk[qheads[-1].start() :].strip()
        else:
            parts = re.split(
                r"(?:题目解析|文本解析|解析\s*[：:]|解\s*[：:])",
                chunk,
                maxsplit=1,
            )
            body = (parts[-1] if len(parts) > 1 else parts[0]).strip()
            paras = [p.strip() for p in re.split(r"\n\s*\n+", body) if p.strip()]
            if len(paras) > 1 and not re.search(
                r"[（(]\s*[）)]|？|\?|上图|空缺|问号|根据|下列|这段|填入", paras[0]
            ):
                body = "\n\n".join(paras[1:]) if re.search(r"因此|所以|故|错误|正确", paras[0]) else paras[-1]

        body = _fix_char_per_line_noise(body)
        stem, options = split_inline_abcd(body)
        if len(options) < 2:
            stem2, options2 = split_options(body)
            if len(options2) >= len(options):
                stem, options = stem2, options2
        if len(options) < 2:
            stem3, options3 = split_plain_option_lines(body)
            if len(options3) > len(options):
                stem, options = stem3, options3

        stem = re.sub(r"^\d{1,3}\s*[、．.\)]\s*", "", stem).strip()
        stem = re.sub(r"^\d{1,3}\s*\(?\s*单选题\s*\)?\s*", "", stem).strip()
        stem = re.sub(r"^第\s*\d+\s*题\s*", "", stem).strip()
        stem = re.sub(r"^\(?\s*单选题\s*\)?\s*", "", stem).strip()
        stem = re.sub(r"^单选题\)\s*", "", stem).strip()
        stem = _strip_leading_pdd_explanation(stem)
        stem = re.sub(r"\n{3,}", "\n\n", stem).strip()
        # 清掉选项文字里残留的解析开头 / 下一选项粘连
        for opt in options:
            t = opt["text"] or ""
            t = re.split(r"\n\s*(?:正确答案|答案\s*[：:]|文本解析|题目解析)", t)[0]
            t = re.split(r"(?:\n\s*|(?<=\S)\s+)[A-E][\.．、，,\)：:]\s*", t)[0]
            opt["text"] = t.strip()
        # 空选项补占位（图在图里）
        if options and all(not (o.get("text") or "").strip() for o in options):
            options = [{"key": o["key"], "text": f"选项 {o['key']}"} for o in options]

        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        after = text[m.end() : end]
        # 答案后常见「C.文本解析：」——只去掉句点/空白，勿整行删掉解析
        after = re.sub(r"^[\.．、)\s]+", "", after)
        first_nl = after.find("\n")
        first_line = after[:first_nl] if first_nl >= 0 else after
        # 同行若无解析标记且像「选项残余」，再丢掉到换行
        if (
            first_line
            and not PDD_EXPL_START_RE.search(first_line)
            and not re.search(r"[\u4e00-\u9fff]{6,}", first_line)
            and len(first_line) < 12
        ):
            after = after[first_nl + 1 :] if first_nl >= 0 else ""
        expl_m = PDD_EXPL_START_RE.search(after)
        if expl_m:
            expl = after[expl_m.end() :].strip()
        else:
            expl = after.strip()
        expl = _cut_pdd_explanation(expl)
        expl = _scrub_pdd_noise(expl)

        if len(stem) < 4:
            # 题干落在选项块前：body 只剩 A-D 时仍可从 chunk 回找
            if len(options) >= 4 and module == "言语理解":
                stem = "根据以上材料，选择最恰当的一项"
            elif module == "图形推理" and answer:
                stem = "根据图形规律，选择正确答案"
            elif module == "资料分析" and answer:
                stem = "根据资料，选择正确答案"
            else:
                continue

        if len(options) < 2:
            if module in {"图形推理", "资料分析"}:
                # 选项在图里或未标注字母：占位，仍可作答
                keys = ["A", "B", "C", "D"]
                if answer.upper() == "E":
                    keys.append("E")
                labels = ["一", "二", "三", "四", "五"]
                options = [
                    {"key": k, "text": f"上图第{labels[j]}项" if module == "图形推理" else f"选项 {k}"}
                    for j, k in enumerate(keys)
                ]
            else:
                continue

        if module == "图形推理":
            keys = ["A", "B", "C", "D"] + (["E"] if answer.upper() == "E" else [])
            labels = ["一", "二", "三", "四", "五"]
            have = {o["key"]: o for o in options}
            options = []
            for j, k in enumerate(keys):
                if k in have and have[k].get("text"):
                    options.append(have[k])
                else:
                    options.append({"key": k, "text": f"上图第{labels[j]}项"})

        needs_image = module in {"图形推理", "资料分析"} or bool(
            re.search(r"下图|图表|根据(图|表)|空缺图形|？号|问号处|\?号", stem)
        )
        seq += 1
        questions.append(
            {
                "id": f"{id_prefix}-{seq:03d}",
                "source": source_label,
                "sourceKey": source,
                "module": module,
                "stem": stem or body[:200],
                "options": options[:5],
                "answer": answer.upper(),
                "explanation": expl,
                "needsImage": needs_image,
                "highYield": True,
                "fp": fingerprint(stem or body, answer + (options[0]["text"] if options else "")),
            }
        )

    # 配对修复：解析末尾粘下一题题干则截断；题干开头粘上一题解析则剥离
    for i in range(len(questions) - 1):
        questions[i]["explanation"] = _cut_pdd_explanation(questions[i].get("explanation") or "")
        questions[i + 1]["stem"] = _strip_leading_pdd_explanation(questions[i + 1].get("stem") or "")
        expl = questions[i].get("explanation") or ""
        nxt = (questions[i + 1].get("stem") or "").strip()
        if len(nxt) < 16 or not expl:
            continue
        cut_at = -1
        compact_expl = re.sub(r"\s+", "", expl)
        for length in (min(40, len(nxt)), 28, 20, 16):
            needle = re.sub(r"\s+", "", nxt[:length])
            if len(needle) < 12:
                continue
            idx = compact_expl.find(needle)
            if idx >= 0:
                # 映射回带空白的 expl：用原 needle 近似定位
                raw_needle = nxt[:length].strip()
                cut_at = expl.find(raw_needle) if raw_needle in expl else idx
                break
        if cut_at == 0:
            questions[i]["explanation"] = ""
        elif cut_at > 0:
            questions[i]["explanation"] = expl[:cut_at].strip()

    # 再扫一遍题干，清掉仍像解析的粘连
    for q in questions:
        q["stem"] = _strip_leading_pdd_explanation(q.get("stem") or "")
        q["explanation"] = _cut_pdd_explanation(q.get("explanation") or "")

    # 丢掉解析体冒充题干 / 过短碎片；同文指纹去重（图推题干常相同，不做指纹去重）
    cleaned: list[dict[str, Any]] = []
    seen_fp: set[str] = set()
    for q in questions:
        stem = (q.get("stem") or "").strip()
        stem = _strip_leading_pdd_explanation(stem)
        # 题干前噪声：页码/残留数字 / 「5%、1.8B 亿人  下图…」
        stem = re.sub(r"^[\d\s.,，、%%]+(?=[\u4e00-\u9fff])", "", stem).strip()
        stem = re.sub(r"^答案[A-E][\d.]*\s*", "", stem).strip()
        if (
            re.search(r"下图|下表|根据", stem)
            and not re.match(r"^(下图|下表|根据|下列)", stem)
            and re.match(r"^[\d%％.,A-Za-z\s]+", stem)
        ):
            stem2 = re.sub(r"^.*?(?=下图|下表|根据)", "", stem)
            if len(stem2) >= 12:
                stem = stem2
        q["stem"] = stem
        q["explanation"] = _cut_pdd_explanation(q.get("explanation") or "")
        if re.match(
            r"^(正确答案|题目解析|文本解析|解析\s*[：:]|解\s*[：:]|况[。．.]|由题意可知|：\s*)",
            stem,
        ):
            continue
        if "(单选题)" in stem or re.search(r"所以答案选\s*[A-E]", stem):
            continue
        if re.search(r"答案为\s*[A-E].{0,40}\d+\s*[\.、(（]?选择题", stem, re.S):
            continue
        if re.search(r"(增长幅度|销售额占|营业收入).{0,40}答案为\s*[A-E]", stem) and len(stem) < 280:
            if not re.search(r"[？?]|下列|根据|哪|多少|是\s*[（(]", stem):
                continue
        hans = len(re.findall(r"[\u4e00-\u9fff]", stem))
        if q.get("module") != "图形推理" and hans < 8:
            continue
        if re.fullmatch(r"[\d\s.,，、.%％A-Za-z]+", stem or ""):
            continue
        fp = q.get("fp") or ""
        placeholder_stem = bool(
            re.match(r"^根据(图形规律|资料|以上材料)，选择", stem)
            or q.get("module") == "图形推理"
        )
        if fp and not placeholder_stem and fp in seen_fp:
            prev_i = next(i for i, x in enumerate(cleaned) if x.get("fp") == fp)
            if len(q.get("explanation") or "") > len(cleaned[prev_i].get("explanation") or ""):
                q["id"] = cleaned[prev_i]["id"]
                cleaned[prev_i] = q
            continue
        if fp and not placeholder_stem:
            seen_fp.add(fp)
        cleaned.append(q)
    # 重编号
    for i, q in enumerate(cleaned, 1):
        prefix = re.sub(r"-\d+$", "", q["id"])
        q["id"] = f"{prefix}-{i:03d}"
    return cleaned


def build_pdd_graphic_questions() -> list[dict[str, Any]]:
    """拼多多图推：无解析页（图+答案）全量导入，有解析页补题干/解析。"""
    try:
        import fitz
    except ImportError:
        print("PyMuPDF missing, skip graphic image import")
        return []

    path = SOURCE / "拼多多在线测评题库" / "拼多多图推26新题整理.pdf"
    if not path.exists():
        print(f"MISSING {path}")
        return []

    print("Parsing PDD graphic explained pages ...")
    explained_text = pdf_text_pages(path, 153, None)
    explained = parse_pdd_bank(
        explained_text,
        "pdd",
        "拼多多26年真题·图形",
        "图形推理",
        "pdd-tx-exp",
    )
    print(f"  -> explained text questions: {len(explained)}")

    doc = fitz.open(path)
    img_root = OUT_DIR.parent / "images" / "pdd-tx"
    img_root.mkdir(parents=True, exist_ok=True)

    def answers_on_page(page: Any) -> list[tuple[float, str]]:
        hits: list[tuple[float, str]] = []
        for w in page.get_text("words"):
            m = re.match(r"(?:正确答案|答案|答)\s*[：:;；]?\s*([A-E])\b", w[4])
            if m:
                hits.append((float(w[1]), m.group(1).upper()))
        hits.sort(key=lambda x: x[0])
        uniq: list[tuple[float, str]] = []
        for y, a in hits:
            if uniq and abs(uniq[-1][0] - y) < 12:
                continue
            uniq.append((y, a))
        return uniq

    def images_on_page(page: Any) -> list[tuple[float, float, float, float]]:
        out = []
        for b in page.get_text("dict")["blocks"]:
            if b.get("type") != 1:
                continue
            x0, y0, x1, y1 = b["bbox"]
            if (x1 - x0) * (y1 - y0) < 70 * 70:
                continue
            out.append((x0, y0, x1, y1))
        out.sort(key=lambda b: b[1])
        return out

    front_items: list[dict[str, Any]] = []
    for pi in range(1, min(153, doc.page_count)):
        page = doc[pi]
        ans_list = answers_on_page(page)
        imgs = images_on_page(page)
        if not ans_list:
            continue
        for ai, (ay, ans) in enumerate(ans_list):
            chosen = None
            for bb in reversed(imgs):
                if bb[1] <= ay + 8:
                    chosen = bb
                    break
            if chosen is None and imgs:
                chosen = imgs[min(ai, len(imgs) - 1)]
            prev_y = ans_list[ai - 1][0] if ai else page.rect.y0 + 20
            y0 = prev_y + 4
            if chosen is not None:
                y0 = min(y0, chosen[1] - 8)
            y1 = ay - 2
            if chosen is not None:
                y1 = max(y1, chosen[3] + 6)
            y0 = max(page.rect.y0 + 10, y0)
            y1 = min(page.rect.y1 - 10, max(y1, y0 + 40))
            front_items.append(
                {
                    "answer": ans,
                    "page": pi,
                    "clip": (
                        max(page.rect.x0 + 30, 36),
                        y0,
                        min(page.rect.x1 - 30, page.rect.width - 36),
                        y1,
                    ),
                }
            )

    print(f"  -> front image answers: {len(front_items)}")

    questions: list[dict[str, Any]] = []
    n = max(len(front_items), len(explained))
    for i in range(n):
        exp = explained[i] if i < len(explained) else None
        fr = front_items[i] if i < len(front_items) else None
        seq = i + 1
        qid = f"pdd-tx-{seq:03d}"

        stem_image = None
        answer = "A"
        if fr is not None:
            page = doc[fr["page"]]
            clip = fitz.Rect(*fr["clip"])
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip, alpha=False)
            out_path = img_root / f"{qid}.png"
            pix.save(str(out_path))
            stem_image = f"/images/pdd-tx/{qid}.png?v=6"
            answer = fr["answer"]

        if exp is not None:
            stem = exp.get("stem") or "根据图形规律，选择正确答案"
            options = list(exp.get("options") or [])
            expl = exp.get("explanation") or ""
            answer = exp.get("answer") or answer
        else:
            stem = "根据图形规律，选择正确答案"
            options = []
            expl = ""

        if len(options) < 2:
            keys = ["A", "B", "C", "D"] + (["E"] if answer == "E" else [])
            labels = ["一", "二", "三", "四", "五"]
            options = [{"key": k, "text": f"上图第{labels[j]}项"} for j, k in enumerate(keys)]

        q: dict[str, Any] = {
            "id": qid,
            "source": "拼多多26年真题·图形",
            "sourceKey": "pdd",
            "module": "图形推理",
            "stem": stem,
            "options": options[:5],
            "answer": answer,
            "explanation": expl,
            "needsImage": stem_image is None,
            "highYield": True,
            "fp": fingerprint(f"pdd-tx-{seq}", answer + stem[:40]),
        }
        if stem_image:
            q["stemImage"] = stem_image
        questions.append(q)

    doc.close()
    print(f"  -> merged graphic questions: {len(questions)}")
    return questions


def build_pdd_questions() -> list[dict[str, Any]]:
    """Import 拼多多 26 年新题（言语 / 资料数量 / 图形）。

    说明：同目录下 2025 套卷是扫描件，无法抽文字，本轮不导入。
    言语 / 数学 PDF 均「前半无解析、后半有解析」——只导入有解析段，避免重复与粘连。
    """
    root = SOURCE / "拼多多在线测评题库"
    banks = [
        (
            "pdd",
            "拼多多26年真题·言语",
            root / "拼多多言语26新题整理可以搜.pdf",
            "言语理解",
            "pdd-yy",
            104,  # 有解析：P105
            None,
        ),
        (
            "pdd",
            "拼多多26年真题·资料/数量",
            root / "拼多多数学26新题整理可以搜.pdf",
            "资料分析",
            "pdd-sx",
            231,  # 有解析：P232
            None,
        ),
    ]
    out: list[dict[str, Any]] = []
    for source, label, path, module, id_prefix, start, end in banks:
        if not path.exists():
            print(f"MISSING {path}")
            continue
        print(f"Parsing PDD {path.name} (pages {start + 1}+) ...")
        text = pdf_text_pages(path, start, end)
        qs = parse_pdd_bank(text, source, label, module, id_prefix)
        if module == "资料分析":
            # 前半「无解析」与后半「有解析」基本是两套题，合并去重（优先保留有解析）
            front_text = pdf_text_pages(path, 0, start)
            front_qs = parse_pdd_bank(front_text, source, label, module, id_prefix)
            print(f"  -> explained {len(qs)}, front {len(front_qs)}")

            def stem_key(stem: str) -> str:
                return re.sub(r"\s+", "", stem or "")[:24]

            merged: list[dict[str, Any]] = []
            seen: set[str] = set()
            for q in qs + front_qs:  # 有解析在前
                k = stem_key(q.get("stem") or "")
                if len(k) >= 12 and k in seen:
                    continue
                if len(k) >= 12:
                    seen.add(k)
                merged.append(q)
            for i, q in enumerate(merged, 1):
                q["id"] = f"{id_prefix}-{i:03d}"
            qs = merged

            for q in qs:
                blob = q["stem"] + q.get("explanation", "")
                if re.search(r"空缺图形|？号|问号处|下图哪个图形", blob):
                    q["module"] = "图形推理"
                    q["needsImage"] = True
                elif re.search(r"多少|几人|速度|效率|行程|浓度|利润|概率", blob) and not re.search(
                    r"根据(图|表|材料|资料)|下图|图表|同比|环比|比重", blob
                ):
                    q["module"] = "数量关系"
                    if not re.search(r"下图|图表|根据图", q["stem"]):
                        q["needsImage"] = False
            attach_pdd_math_images(qs, path)
        print(f"  -> {len(qs)} questions")
        out.extend(qs)

    out.extend(build_pdd_graphic_questions())
    return out


def attach_pdd_math_images(questions: list[dict[str, Any]], path: Path) -> None:
    """按题干在 PDF 中定位并截取图表（拼多多数学题号会重置，不能靠序号）。"""
    try:
        import fitz
    except ImportError:
        print("  PyMuPDF missing, skip math chart clips")
        return
    if not path.exists() or not questions:
        return

    doc = fitz.open(path)
    img_root = OUT_DIR.parent / "images" / "pdd-sx"
    img_root.mkdir(parents=True, exist_ok=True)

    # 页文本索引（有解析段为主，前半无解析段作图源补充）
    page_text: list[str] = []
    for i in range(doc.page_count):
        page_text.append(re.sub(r"\s+", "", doc[i].get_text() or ""))

    def find_page(stem: str, prefer_from: int = 231) -> int | None:
        key = re.sub(r"\s+", "", stem or "")
        if len(key) < 10:
            return None
        needles = [key[:28], key[:20], key[:14]]
        # 先搜有解析段，再搜前半（图往往更清晰）
        ranges = [range(prefer_from, doc.page_count), range(1, prefer_from)]
        for needle in needles:
            if len(needle) < 10:
                continue
            for rg in ranges:
                for pi in rg:
                    if needle in page_text[pi]:
                        return pi
        return None

    def images_in_band(page: Any, y0: float, y1: float) -> list[tuple[float, float, float, float]]:
        out = []
        for b in page.get_text("dict")["blocks"]:
            if b.get("type") != 1:
                continue
            x0, by0, x1, by1 = b["bbox"]
            if by1 < y0 - 8 or by0 > y1 + 8:
                continue
            if (x1 - x0) * (by1 - by0) < 60 * 60:
                continue
            out.append((x0, by0, x1, by1))
        return out

    attached = 0
    for q in questions:
        if not q.get("needsImage"):
            continue
        if q.get("stemImage"):
            continue
        pi = find_page(q.get("stem") or "")
        if pi is None:
            # 短题干（「下列说法…」）用解析关键词再试
            pi = find_page((q.get("explanation") or "")[:40], prefer_from=231)
        if pi is None:
            continue
        page = doc[pi]
        stem_key = re.sub(r"\s+", "", (q.get("stem") or ""))[:18]
        # 题干锚点 y
        y0 = page.rect.y0 + 40
        for w in page.get_text("words"):
            if stem_key and stem_key[:8] in re.sub(r"\s+", "", w[4]):
                y0 = max(page.rect.y0 + 20, float(w[1]) - 10)
                break
        # 答案锚点 y
        y1 = page.rect.y1 - 30
        for w in page.get_text("words"):
            if re.match(r"(?:正确答案|答案|答)\s*[：:;；]?[A-E]?", w[4]) and float(w[1]) > y0 + 20:
                y1 = min(y1, float(w[1]) - 4)
                break
        imgs = images_in_band(page, y0 - 30, y1 + 20)
        # 题干页无图时，常见图在上一页
        if not imgs and pi > 0:
            prev = doc[pi - 1]
            prev_imgs = images_in_band(prev, prev.rect.y0 + 40, prev.rect.y1 - 40)
            if prev_imgs:
                page = prev
                pi = pi - 1
                imgs = prev_imgs
                y0 = min(b[1] for b in imgs) - 10
                y1 = max(b[3] for b in imgs) + 10
        if imgs:
            x0 = min(b[0] for b in imgs) - 8
            by0 = min(b[1] for b in imgs) - 8
            x1 = max(b[2] for b in imgs) + 8
            by1 = max(b[3] for b in imgs) + 8
            # 若图在题干上方（材料图），仍纳入
            y0 = min(y0, by0)
            y1 = max(y1, by1)
            clip = fitz.Rect(
                max(page.rect.x0 + 20, x0),
                max(page.rect.y0 + 16, y0),
                min(page.rect.x1 - 20, x1),
                min(page.rect.y1 - 16, y1),
            )
        else:
            clip = fitz.Rect(
                page.rect.x0 + 36,
                max(page.rect.y0 + 16, y0),
                page.rect.x1 - 36,
                min(page.rect.y1 - 16, y1),
            )
        if clip.height < 40 or clip.width < 40:
            continue
        qid = q["id"]
        out_path = img_root / f"{qid}.png"
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip, alpha=False)
        pix.save(str(out_path))
        q["stemImage"] = f"/images/pdd-sx/{qid}.png?v=6"
        q["needsImage"] = False
        attached += 1

    doc.close()
    still = sum(1 for q in questions if q.get("needsImage") and not q.get("stemImage"))
    print(f"  -> attached math charts: {attached}; still need image: {still}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_q: list[dict[str, Any]] = []

    sources = [
        (
            "beisen",
            "北森题库（TogoCareer解析版）",
            SOURCE / "TogoCareer北森题库（解析版）.pdf",
            "ref",
        ),
        (
            "plan-w1",
            "行测学习计划·第一周",
            SOURCE / "行测学习计划（30天）/行测学习计划（第一周）解析版.pdf",
            "ref",
        ),
        (
            "plan-w2",
            "行测学习计划·第二周",
            SOURCE / "行测学习计划（30天）/行测学习计划（第二周）解析版.pdf",
            "ref",
        ),
        (
            "plan-w3",
            "行测学习计划·第三周",
            SOURCE / "行测学习计划（30天）/行测学习计划（第三周）解析版.pdf",
            "ref",
        ),
        (
            "mock1",
            "行测学习计划·模拟卷1",
            SOURCE / "行测学习计划（30天）/行测学习计划（第四周）模拟卷1-解析版.pdf",
            "bracket",
        ),
        (
            "mock2",
            "行测学习计划·模拟卷2",
            SOURCE / "行测学习计划（30天）/行测学习计划（第四周）模拟卷2-解析版.pdf",
            "bracket",
        ),
    ]

    for key, label, path, kind in sources:
        if not path.exists():
            print(f"MISSING {path}")
            continue
        print(f"Parsing {path.name} ...")
        text = pdf_text(path)
        qs = parse_ref_answer(text, key, label) if kind == "ref" else parse_bracket_answer(text, key, label)
        print(f"  -> {len(qs)} questions")
        all_q.extend(qs)

    docx_dir = SOURCE / "通用行测各类型题目答题技巧(13)/通用行测各类型题目答题技巧"
    docx_banks = [
        (
            "docx-sz",
            "数字推理精选300",
            docx_dir / "能力测试提分题库之数字推理题精选300道详解.docx",
            "数字推理",
        ),
        (
            "docx-sl",
            "数学运算思维策略精选400",
            docx_dir / "能力测试提分题库之数学运算思维策略题精选400道详解.docx",
            "数学运算",
        ),
    ]
    for key, label, path, module in docx_banks:
        if not path.exists():
            print(f"MISSING {path}")
            continue
        print(f"Parsing {path.name} ...")
        text = docx_text(path)
        qs = parse_docx_bank(text, key, label, module)
        print(f"  -> {len(qs)} questions")
        all_q.extend(qs)

    all_q.extend(build_pdd_questions())

    raw_count = len(all_q)
    questions = dedupe(all_q)
    assign_tips(questions)
    tips = build_tips()
    packs = build_sprint_packs(questions, tips)

    (OUT_DIR / "questions.json").write_text(
        json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "tips.json").write_text(
        json.dumps(tips, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "sprint-packs.json").write_text(
        json.dumps(packs, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Boundary QA: catch stem←prev-expl / expl→next-stem glue
    qa: dict[str, Any] = {"stemGlue": 0, "explGlue": 0, "samples": []}
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for q in questions:
        by_source[q["sourceKey"]].append(q)
    for _key, subset in by_source.items():
        for i, q in enumerate(subset):
            stem = q.get("stem") or ""
            expl = q.get("explanation") or ""
            if re.match(r"^(解法|解析|方法|第一种|第二种|因此|【解析】|正确答案|题目解析|由题意可知|：\s*由题意)", stem):
                qa["stemGlue"] += 1
                if len(qa["samples"]) < 8:
                    qa["samples"].append({"id": q["id"], "kind": "stem", "text": stem[:80]})
            elif "(单选题)" in stem or re.search(r"所以答案选\s*[A-E]", stem):
                qa["stemGlue"] += 1
                if len(qa["samples"]) < 8:
                    qa["samples"].append({"id": q["id"], "kind": "stem-glue", "text": stem[:80]})
            # 解析里出现完整 A-D 选项块，才算粘上下一题
            if re.search(
                r"A[\.．、\)：:]\s*\S+.{0,60}B[\.．、\)：:]\s*\S+.{0,60}C[\.．、\)：:]\s*\S+.{0,60}D[\.．、\)：:]",
                expl,
                re.S,
            ):
                qa["explGlue"] += 1
                if len(qa["samples"]) < 8:
                    qa["samples"].append({"id": q["id"], "kind": "expl-opts"})
            elif i + 1 < len(subset):
                nxt = subset[i + 1].get("stem") or ""
                # 下一题题干较长且几乎整段出现在解析末尾
                compact_nxt = re.sub(r"\s+", "", nxt)
                compact_expl = re.sub(r"\s+", "", expl)
                if (
                    len(compact_nxt) >= 28
                    and compact_nxt[:28] in compact_expl
                    and compact_expl.rfind(compact_nxt[:28]) > len(compact_expl) - 40
                    and not re.search(
                        r"(选项|选择\s*[A-E]|答案为\s*[A-E]|故选\s*[A-E])[。.]?\s*$",
                        expl.strip(),
                    )
                ):
                    qa["explGlue"] += 1
                    if len(qa["samples"]) < 8:
                        qa["samples"].append(
                            {"id": q["id"], "kind": "expl", "next": subset[i + 1]["id"]}
                        )

    meta = {
        "rawCount": raw_count,
        "uniqueCount": len(questions),
        "beisenCount": sum(1 for q in questions if q.get("sourceKey") == "beisen"),
        "pddCount": sum(1 for q in questions if q.get("sourceKey") == "pdd"),
        "sprintPackCount": len(packs),
        "sprintQuestionCount": len({qid for p in packs for qid in p["questionIds"]}),
        "modules": dict(Counter(q["module"] for q in questions)),
        "sources": dict(Counter(q["sourceKey"] for q in questions)),
        "qa": qa,
    }
    (OUT_DIR / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\nDONE")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
