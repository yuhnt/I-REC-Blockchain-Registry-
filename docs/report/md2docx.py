"""Chuyển Final Report.md sang .docx theo mẫu format.docx (trang bìa, mục lục, style Heading, Times New Roman).

Dùng: python md2docx.py <format.docx> <report.md> <thư mục ảnh> <out.docx>
Giữ nguyên trang bìa và trường mục lục của mẫu (block 0–42), thay phần thân bằng nội dung chuyển từ markdown.
"""
from __future__ import annotations

import re
import struct
import sys
import zipfile
from xml.sax.saxutils import escape

FMT, MD, IMG_DIR, OUT = sys.argv[1:5]

FONT = 'w:ascii="Times New Roman" w:eastAsia="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"'
BODY_SZ, TABLE_SZ, CODE_SZ = 24, 20, 19
TEXT_W = 11906 - 2 * 1134  # bề rộng vùng chữ (dxa)
BORDER = "8EAADB"
HEAD_FILL = "D9E2F3"

# ---------------------------------------------------------------- inline


def runs(text: str, sz: int = BODY_SZ, base: str = "") -> str:
    """**đậm**, *nghiêng* / _nghiêng_, `mã`, [chữ](link) → các w:r."""
    out = []
    pat = re.compile(r"(\*\*(.+?)\*\*|`([^`]+)`|(?<![\w*])\*(?!\s)([^*]+?)(?<!\s)\*(?![\w*])|(?<![\w])_(?!\s)([^_]+?)(?<!\s)_(?![\w])"
                     r"|\[([^\]]+)\]\(([^)]+)\))")
    pos = 0
    for m in pat.finditer(text):
        if m.start() > pos:
            out.append(_run(text[pos:m.start()], sz, base))
        if m.group(2) is not None:
            out.append(runs(m.group(2), sz, base + "<w:b/><w:bCs/>"))
        elif m.group(3) is not None:
            out.append(_run(m.group(3), sz - 2, base, code=True))
        elif m.group(4) is not None:
            out.append(runs(m.group(4), sz, base + "<w:i/><w:iCs/>"))
        elif m.group(5) is not None:
            out.append(runs(m.group(5), sz, base + "<w:i/><w:iCs/>"))
        else:
            out.append(runs(m.group(6), sz, base))
        pos = m.end()
    if pos < len(text):
        out.append(_run(text[pos:], sz, base))
    return "".join(out)


def _run(t: str, sz: int, extra: str = "", code: bool = False) -> str:
    if not t:
        return ""
    font = ('w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas" w:eastAsia="Times New Roman"' if code else FONT)
    return (f'<w:r><w:rPr><w:rFonts {font}/>{extra}<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/></w:rPr>'
            f'<w:t xml:space="preserve">{escape(t)}</w:t></w:r>')


def _jc(text: str) -> str:
    """Căn đều hai bên, trừ đoạn có mã dài (căn đều sẽ kéo giãn khoảng trắng)."""
    return '<w:jc w:val="left"/>' if "`" in text else '<w:jc w:val="both"/>'


def para(text: str, *, sz: int = BODY_SZ, ppr: str = "", base: str = "") -> str:
    return f'<w:p><w:pPr>{ppr}{_jc(text)}</w:pPr>{runs(text, sz, base)}</w:p>'


# ---------------------------------------------------------------- khối

BOOKMARK = [100]


def heading(level: int, text: str) -> str:
    BOOKMARK[0] += 1
    style = {1: "Heading1", 2: "Heading2", 3: "Heading3"}.get(level, "Heading4")
    spacing = {1: '<w:spacing w:before="320" w:after="120"/>', 2: '<w:spacing w:before="240" w:after="80"/>',
               3: '<w:spacing w:before="160" w:after="60"/>'}.get(level, "")
    rpr = f"<w:rFonts {FONT}/>"
    body = re.sub(r"\*\*(.+?)\*\*", r"\1", text).replace("`", "")
    return (f'<w:p><w:pPr><w:pStyle w:val="{style}"/>{spacing}<w:rPr>{rpr}</w:rPr></w:pPr>'
            f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{escape(body)}</w:t></w:r></w:p>')


def bullet(text: str, level: int) -> str:
    return (f'<w:p><w:pPr><w:numPr><w:ilvl w:val="{level}"/><w:numId w:val="1"/></w:numPr>'
            f'<w:spacing w:after="40"/>{_jc(text)}</w:pPr>{runs(text)}</w:p>')


def ordered(num: str, text: str, level: int) -> str:
    left = 360 + 360 * (level + 1)
    return (f'<w:p><w:pPr><w:tabs><w:tab w:val="left" w:pos="{left}"/></w:tabs><w:spacing w:after="40"/>'
            f'<w:ind w:left="{left}" w:hanging="360"/>{_jc(text)}</w:pPr>'
            f'{_run(num + ".", BODY_SZ)}<w:r><w:tab/></w:r>{runs(text)}</w:p>')


def _cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", s)]


def _plain_len(t: str) -> int:
    return len(re.sub(r"\*\*|`|\*", "", t))


def table(lines: list[str]) -> str:
    rows = [_cells(x) for x in lines if not re.match(r"^\s*\|?\s*:?-{2,}", x)]
    n = max(len(r) for r in rows)
    rows = [r + [""] * (n - len(r)) for r in rows]
    weight = []
    for j in range(n):
        lens = [_plain_len(r[j]) for r in rows]
        longest = max(lens)
        avg = sum(lens) / len(lens)
        weight.append(max(5.0, min(longest, 18) * 0.6 + min(avg, 120) * 0.8))
    tot = sum(weight)
    widths = [TEXT_W * w / tot for w in weight]
    # Cột không được hẹp hơn từ dài nhất của nó (tránh bẻ "Mã" thành "M ã")
    mins = []
    for j in range(n):
        tokens = [t for r in rows for t in re.sub(r"\*\*|`|\*", "", r[j]).split()]
        longest_tok = max((len(t) for t in tokens), default=2)
        mins.append(min(150 * longest_tok + 260, TEXT_W * 0.35))
    for _ in range(5):
        short = [j for j in range(n) if widths[j] < mins[j]]
        if not short:
            break
        need = sum(mins[j] - widths[j] for j in short)
        rich = [j for j in range(n) if j not in short and widths[j] > mins[j]]
        pool = sum(widths[j] - mins[j] for j in rich)
        for j in short:
            widths[j] = mins[j]
        for j in rich:
            widths[j] -= need * (widths[j] - mins[j]) / pool
    widths = [int(w) for w in widths]
    widths[-1] = TEXT_W - sum(widths[:-1])
    b = f'w:val="single" w:sz="4" w:space="0" w:color="{BORDER}"'
    out = [f'<w:tbl><w:tblPr><w:tblW w:w="{TEXT_W}" w:type="dxa"/><w:tblBorders><w:top {b}/><w:left {b}/>'
           f'<w:bottom {b}/><w:right {b}/><w:insideH {b}/><w:insideV {b}/></w:tblBorders>'
           f'<w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="40" w:type="dxa"/><w:left w:w="80" w:type="dxa"/>'
           f'<w:bottom w:w="40" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>']
    out += [f'<w:gridCol w:w="{w}"/>' for w in widths]
    out.append("</w:tblGrid>")
    for i, r in enumerate(rows):
        head = i == 0
        out.append("<w:tr>" + ("<w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>" if head else "<w:trPr><w:cantSplit/></w:trPr>"))
        for w, c in zip(widths, r):
            shd = f'<w:shd w:val="clear" w:color="auto" w:fill="{HEAD_FILL}"/>' if head else ""
            c = c.replace("\\|", "|")
            base = "<w:b/><w:bCs/>" if head else ""
            out.append(f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>{shd}</w:tcPr>'
                       f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
                       f'{runs(c, TABLE_SZ, base)}</w:p></w:tc>')
        out.append("</w:tr>")
    out.append("</w:tbl>")
    out.append('<w:p><w:pPr><w:spacing w:after="60"/></w:pPr></w:p>')
    return "".join(out)


def code_block(lines: list[str]) -> str:
    out = []
    for x in lines:
        out.append(f'<w:p><w:pPr><w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/>'
                   f'<w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:ind w:left="284"/></w:pPr>'
                   f'{_run(x, CODE_SZ, code=True)}</w:p>')
    return "".join(out) + '<w:p><w:pPr><w:spacing w:after="60"/></w:pPr></w:p>'


IMAGES: list[tuple[str, str, int, int]] = []  # (rId, file, cx, cy)


def png_size(path: str) -> tuple[int, int]:
    with open(path, "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


def image(caption: str, fname: str) -> str:
    w, h = png_size(f"{IMG_DIR}/{fname}")
    max_w, max_h = TEXT_W / 1440 * 914400, 7.6 * 914400
    scale = min(max_w / w, max_h / h)
    cx, cy = int(w * scale), int(h * scale)
    rid = f"rIdImg{len(IMAGES) + 1}"
    IMAGES.append((rid, fname, cx, cy))
    k = len(IMAGES)
    drawing = (f'<w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
               f'<wp:docPr id="{900 + k}" name="Hinh {k}"/><wp:cNvGraphicFramePr><a:graphicFrameLocks '
               f'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
               f'<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData '
               f'uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic '
               f'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="{900 + k}" '
               f'name="{fname}"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="{rid}"/><a:stretch>'
               f'<a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" '
               f'cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
               f'</a:graphicData></a:graphic></wp:inline></w:drawing>')
    return (f'<w:p><w:pPr><w:keepNext/><w:spacing w:before="120" w:after="60"/><w:jc w:val="center"/></w:pPr>'
            f'<w:r>{drawing}</w:r></w:p>'
            f'<w:p><w:pPr><w:spacing w:after="160"/><w:jc w:val="center"/></w:pPr>'
            f'{runs(caption, 22, "<w:i/><w:iCs/>")}</w:p>')


# ---------------------------------------------------------------- markdown → khối


def convert(md: str) -> str:
    lines = md.split("\n")
    # Bỏ dòng tiêu đề "# Final Report": thay bằng Title của mẫu
    assert lines[0].startswith("# Final Report")
    out = [f'<w:p><w:pPr><w:pStyle w:val="Title"/><w:spacing w:after="120"/><w:jc w:val="center"/>'
           f'<w:rPr><w:rFonts {FONT}/></w:rPr></w:pPr><w:r><w:rPr><w:rFonts {FONT}/><w:sz w:val="56"/>'
           f'<w:szCs w:val="56"/></w:rPr><w:t>Final Report – Nhóm 4</w:t></w:r></w:p>']
    i = 1
    para_buf: list[str] = []

    def flush():
        if para_buf:
            out.append(para(" ".join(s.strip() for s in para_buf)))
            para_buf.clear()

    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            flush(); i += 1; continue
        if s.startswith("```"):
            flush()
            j = i + 1
            while not lines[j].strip().startswith("```"):
                j += 1
            out.append(code_block(lines[i + 1:j])); i = j + 1; continue
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m and not line.startswith((" ", "\t")):
            flush(); out.append(heading(len(m.group(1)), m.group(2).strip())); i += 1; continue
        m = re.match(r"^!\[([^\]|]+)(?:\|\d+)?\]\(([^)]+)\)$", s)
        if m:
            flush(); out.append(image(m.group(1), m.group(2))); i += 1; continue
        if s.startswith("|"):
            flush()
            j = i
            while j < len(lines) and lines[j].strip().startswith("|"):
                j += 1
            out.append(table(lines[i:j])); i = j; continue
        indent = len(line) - len(line.lstrip(" \t"))
        level = 0 if indent == 0 else 1
        m = re.match(r"^[-*]\s+(.*)$", s)
        if m:
            flush(); out.append(bullet(m.group(1).strip(), level)); i += 1; continue
        m = re.match(r"^(\d+)\.\s+(.*)$", s)
        if m:
            flush(); out.append(ordered(m.group(1), m.group(2).strip(), level)); i += 1; continue
        if re.match(r"^\[\d+\]\s", s):  # mỗi mục tài liệu tham khảo là một đoạn, căn trái
            flush()
            out.append(f'<w:p><w:pPr><w:spacing w:after="60"/><w:ind w:left="567" w:hanging="567"/></w:pPr>'
                       f'{runs(s)}</w:p>')
            i += 1
            continue
        para_buf.append(s)
        i += 1
    flush()
    return "".join(out)


# ---------------------------------------------------------------- lắp file


def main() -> None:
    zin = zipfile.ZipFile(FMT)
    doc = zin.read("word/document.xml").decode("utf-8")
    start = doc.index("<w:body>") + len("<w:body>")
    end = doc.index("</w:body>")
    body = doc[start:end]
    # Mục lục nằm trong <w:sdt>, nên cắt theo vị trí: giữ mọi thứ tới hết khối thứ 43 (ngắt trang sau mục lục).
    found = list(re.finditer(r"<w:p[ >].*?</w:p>|<w:tbl>.*?</w:tbl>|<w:sectPr.*?</w:sectPr>", body, re.S))
    assert 'w:type="page"' in found[42].group(0) and 'fldCharType="end"' in found[41].group(0)
    assert found[-1].group(0).startswith("<w:sectPr")
    head, sect = body[:found[42].end()], found[-1].group(0)
    assert head.count("<w:sdt>") == head.count("</w:sdt>") == 1
    for old, new in (("<w:t>Mini Proposal</w:t>", "<w:t>BÁO CÁO CUỐI KỲ</w:t>"),
                     ("Hệ Thống Chứng Chỉ Carbon Hoặc Năng Lượng Tái Tạo Chống Double Counting ",
                      "Hệ thống chứng chỉ năng lượng tái tạo chống double counting dựa trên sổ cái dùng chung, "
                      "multi-oracle và phát hiện bất thường"),
                     ("<w:t>Contents</w:t>", "<w:t>Mục lục</w:t>")):
        assert head.count(old) == 1, old
        head = head.replace(old, new)

    md = open(MD, encoding="utf-8").read()
    new_body = head + convert(md) + sect
    doc = doc[:start] + new_body + doc[end:]

    rels = zin.read("word/_rels/document.xml.rels").decode("utf-8")
    extra = "".join(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                    f'relationships/image" Target="media/{f}"/>' for rid, f, _, _ in IMAGES)
    rels = rels.replace("</Relationships>", extra + "</Relationships>")
    ct = zin.read("[Content_Types].xml").decode("utf-8")
    if 'Extension="png"' not in ct:
        ct = ct.replace("<Default Extension=\"rels\"", '<Default Extension="png" ContentType="image/png"/>'
                        '<Default Extension="rels"', 1)
    settings = zin.read("word/settings.xml").decode("utf-8")  # mục lục được Word cập nhật ở bước sau (update_word.ps1)

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename.endswith("/"):
                continue
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                data = doc.encode("utf-8")
            elif item.filename == "word/_rels/document.xml.rels":
                data = rels.encode("utf-8")
            elif item.filename == "[Content_Types].xml":
                data = ct.encode("utf-8")
            elif item.filename == "word/settings.xml":
                data = settings.encode("utf-8")
            elif item.filename == "word/footer1.xml":
                assert b"<w:t>Mini Proposal</w:t>" in data
                data = data.replace(b"<w:t>Mini Proposal</w:t>", b"<w:t>Final Report</w:t>")
            zout.writestr(item, data)
        for _, f, _, _ in IMAGES:
            zout.write(f"{IMG_DIR}/{f}", f"word/media/{f}")
    print("ok", OUT, len(IMAGES), "ảnh")


if __name__ == "__main__":
    main()
