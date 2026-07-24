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
OPT_RE = re.compile(r"(?:^|\n)\s*([A-E])[\.．、\)]\s*", re.M)

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


def split_options(body: str) -> tuple[str, list[dict[str, str]]]:
    matches = list(OPT_RE.finditer(body))
    if len(matches) < 2:
        return body.strip(), []
    # Prefer the last contiguous A-D/E block
    start_idx = 0
    for i, m in enumerate(matches):
        if m.group(1) == "A":
            start_idx = i
    matches = matches[start_idx:]
    stem = body[: matches[0].start()].strip()
    options: list[dict[str, str]] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        text = body[m.end() : end].strip()
        text = re.split(r"\n\s*参考答案|\n\s*[A-E]【解析】", text)[0].strip()
        options.append({"key": m.group(1), "text": text})
        if m.group(1) == "E" or (i >= 3 and m.group(1) == "D" and i == len(matches) - 1):
            # keep going for E if present
            pass
    # Deduplicate keys keeping first
    seen = set()
    uniq = []
    for opt in options:
        if opt["key"] in seen:
            continue
        seen.add(opt["key"])
        uniq.append(opt)
    return stem, uniq


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
        expl = re.split(r"(?:^|\n)\s*\d{1,3}[\.、．]\s+", expl, maxsplit=1)[0].strip()
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
        expl = re.split(r"(?:^|\n)\s*\d{1,3}[\.、．]", expl, maxsplit=1)[0].strip()
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
    """Parse compact 'A.1 B.2 C.3 D.4' option blocks common in docx banks."""
    pattern = re.compile(
        r"([A-D])[\.．、\)]\s*([^A-D]*?)(?=(?:\s*[A-D][\.．、\)])|$)"
    )
    # Find the last complete A..D run
    runs = list(re.finditer(r"A[\.．、\)]\s*.*?D[\.．、\)]\s*\S+", chunk, re.S))
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


def clean_docx_stem(stem: str) -> str:
    stem = stem.strip()
    stem = re.sub(r"^【解析】[\s\S]*?(?=\d)", "", stem).strip()
    # Drop title lines
    lines = [ln.strip() for ln in stem.splitlines() if ln.strip()]
    while lines and re.search(r"题库|讲义|详解|目录", lines[0]) and len(lines[0]) < 40:
        lines = lines[1:]
    # If explanation leftovers precede the actual stem, keep the last short numeric/文字题干
    stem = "\n".join(lines).strip()
    # Prefer last paragraph that looks like a question stem
    parts = re.split(r"\n{2,}", stem)
    if len(parts) > 1:
        for part in reversed(parts):
            p = part.strip()
            if len(p) >= 3 and not re.search(r"因此，本题答案|正确答案", p):
                stem = p
                break
    # Collapse whitespace
    stem = re.sub(r"[ \t]+\n", "\n", stem)
    stem = re.sub(r"\n{3,}", "\n\n", stem).strip()
    # Remove leading title still glued
    stem = re.sub(r"^能力测试提分题库[^\n]*\n+", "", stem).strip()
    return stem


def parse_docx_bank(text: str, source: str, source_label: str, module: str) -> list[dict[str, Any]]:
    matches = list(re.finditer(r"答案[：:]\s*([A-E])\s*解析[：:]?\s*", text))
    questions: list[dict[str, Any]] = []
    seq = 0
    for i, m in enumerate(matches):
        prev_end = matches[i - 1].end() if i else 0
        chunk = text[prev_end : m.start()].strip()
        chunk = re.sub(r"^【解析】[^\n]*\n?", "", chunk).strip()

        stem, options = split_inline_abcd(chunk)
        if len(options) < 4:
            stem2, options2 = split_options(chunk)
            if len(options2) >= len(options):
                stem, options = stem2, options2

        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        expl = text[m.end() : end]
        expl = re.split(r"答案[：:]\s*[A-E]", expl, maxsplit=1)[0].strip()
        expl = re.sub(r"^【解析】\s*", "", expl).strip()
        stem = clean_docx_stem(stem)
        if len(options) < 2 or len(stem) < 3:
            continue
        if re.fullmatch(r".{0,30}(题库|讲义|详解).{0,30}", stem):
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
                "fp": fingerprint(stem, m.group(1)+options[0]["text"]),
            }
        )
    return questions


def dedupe(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Prefer beisen > plan > docx when fingerprints collide
    priority = {"beisen": 0, "plan-w1": 1, "plan-w2": 1, "plan-w3": 1, "mock1": 2, "mock2": 2}
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

    meta = {
        "rawCount": raw_count,
        "uniqueCount": len(questions),
        "beisenCount": sum(1 for q in questions if q.get("sourceKey") == "beisen"),
        "sprintPackCount": len(packs),
        "sprintQuestionCount": len({qid for p in packs for qid in p["questionIds"]}),
        "modules": dict(Counter(q["module"] for q in questions)),
        "sources": dict(Counter(q["sourceKey"] for q in questions)),
    }
    (OUT_DIR / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\nDONE")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
