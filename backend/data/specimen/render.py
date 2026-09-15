"""
render.py - Minimal page-layout helper over reportlab, with a mandatory
SPECIMEN watermark and provenance banner on every page.
"""

from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit

W, H = A4
LM, RM = 20 * mm, 20 * mm
CW = W - LM - RM

BANNER = ("SPECIMEN - SYNTHETIC TEST DATA - NOT A VALID DOCUMENT - "
          "SIH 2026 / PS SIH26100")
FOOTER = ("Generated specimen for Smart India Hackathon 2026 prototype "
          "demonstration (PS SIH26100). Fictitious entity. Not issued by any "
          "authority and of no legal effect.")


class Doc:
    def __init__(self, path):
        self.path = path
        self.c = rl_canvas.Canvas(path, pagesize=A4)
        self.c.setTitle("SPECIMEN - synthetic test document")
        self.c.setAuthor("SIH26100 specimen generator")
        self.c.setSubject("Synthetic test fixture - not a genuine document")
        self.y = 0
        self._page_start()

    # ---- page furniture -------------------------------------------------
    def _page_start(self):
        c = self.c
        # diagonal watermark
        c.saveState()
        c.setFillColorRGB(0.87, 0.87, 0.89)
        c.setFont("Helvetica-Bold", 52)
        c.translate(W / 2, H * 0.58)
        c.rotate(38)
        c.drawCentredString(0, 60, "SPECIMEN")
        c.setFont("Helvetica-Bold", 22)
        c.drawCentredString(0, 10, "SYNTHETIC TEST DATA")
        c.drawCentredString(0, -20, "NOT A VALID DOCUMENT")
        c.restoreState()

        # top banner strip
        c.saveState()
        c.setFillColorRGB(0.82, 0.10, 0.10)
        c.rect(0, H - 13 * mm, W, 13 * mm, stroke=0, fill=1)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawCentredString(W / 2, H - 8.6 * mm, BANNER)
        c.restoreState()

        # bottom footer
        c.saveState()
        c.setFont("Helvetica-Oblique", 6.5)
        c.setFillColorRGB(0.42, 0.42, 0.42)
        for i, ln in enumerate(simpleSplit(FOOTER, "Helvetica-Oblique", 6.5, CW)):
            c.drawString(LM, 12 * mm - i * 8, ln)
        c.restoreState()

        self.y = H - 24 * mm

    def _space(self, need):
        if self.y - need < 22 * mm:
            self.c.showPage()
            self._page_start()

    # ---- content blocks -------------------------------------------------
    def authority(self, lines, rule=True):
        """Issuing-authority header block, centred."""
        self._space(30 * mm)
        sizes = [12, 9.5, 8.5, 8]
        for i, ln in enumerate(lines):
            sz = sizes[min(i, len(sizes) - 1)]
            font = "Helvetica-Bold" if i == 0 else "Helvetica"
            self.c.setFont(font, sz)
            self.c.setFillColorRGB(0, 0, 0)
            self.c.drawCentredString(W / 2, self.y, ln)
            self.y -= sz + 3.5
        if rule:
            self.y -= 3
            self.c.setLineWidth(1.1)
            self.c.line(LM, self.y, W - RM, self.y)
            self.y -= 9

    def title(self, text, size=12.5):
        self._space(16 * mm)
        self.c.setFont("Helvetica-Bold", size)
        self.c.setFillColorRGB(0, 0, 0)
        self.c.drawCentredString(W / 2, self.y, text)
        self.y -= size + 9

    def heading(self, text, size=9.5):
        self._space(14 * mm)
        self.y -= 3
        self.c.setFont("Helvetica-Bold", size)
        self.c.setFillColorRGB(0, 0, 0)
        self.c.drawString(LM, self.y, text)
        self.y -= size + 5

    def fields(self, rows, label_w=62 * mm, size=9, gap=5.0, bold_values=()):
        """rows: list of (label, value). Renders 'Label : Value' lines."""
        for label, value in rows:
            self._space(12 * mm)
            self.c.setFont("Helvetica", size)
            self.c.setFillColorRGB(0.2, 0.2, 0.2)
            self.c.drawString(LM, self.y, label)
            self.c.drawString(LM + label_w - 4 * mm, self.y, ":")
            vfont = "Helvetica-Bold" if label in bold_values else "Helvetica"
            self.c.setFont(vfont, size)
            self.c.setFillColorRGB(0, 0, 0)
            vx = LM + label_w
            wrapped = simpleSplit(str(value), vfont, size, CW - label_w)
            for j, ln in enumerate(wrapped):
                if j:
                    self.y -= size + 2
                    self._space(12 * mm)
                self.c.drawString(vx, self.y, ln)
            self.y -= size + gap

    def para(self, text, size=9, gap=5, align="left", indent=0):
        self._space(14 * mm)
        self.c.setFont("Helvetica", size)
        self.c.setFillColorRGB(0, 0, 0)
        for ln in simpleSplit(text, "Helvetica", size, CW - indent):
            self._space(11 * mm)
            self.c.drawString(LM + indent, self.y, ln)
            self.y -= size + 2.6
        self.y -= gap

    def bullets(self, items, size=9, gap=4):
        for it in items:
            self._space(12 * mm)
            self.c.setFont("Helvetica", size)
            self.c.setFillColorRGB(0, 0, 0)
            self.c.drawString(LM + 4 * mm, self.y, "-")
            for j, ln in enumerate(simpleSplit(it, "Helvetica", size, CW - 12 * mm)):
                if j:
                    self.y -= size + 2.4
                    self._space(11 * mm)
                self.c.drawString(LM + 9 * mm, self.y, ln)
            self.y -= size + gap

    def table(self, headers, rows, widths, size=8.5):
        self._space((len(rows) + 3) * 6 * mm)
        x0 = LM
        # header
        self.c.setFillColorRGB(0.90, 0.90, 0.92)
        self.c.rect(x0, self.y - 3, sum(widths), 13, stroke=0, fill=1)
        self.c.setFont("Helvetica-Bold", size)
        self.c.setFillColorRGB(0, 0, 0)
        x = x0
        for h, w in zip(headers, widths):
            self.c.drawString(x + 2.2 * mm, self.y + 1.5, h)
            x += w
        self.y -= 14
        self.c.setFont("Helvetica", size)
        for r in rows:
            self._space(14 * mm)
            x = x0
            maxlines = 1
            for v, w in zip(r, widths):
                lines = simpleSplit(str(v), "Helvetica", size, w - 4.4 * mm)
                maxlines = max(maxlines, len(lines))
                for j, ln in enumerate(lines):
                    self.c.drawString(x + 2.2 * mm, self.y - j * (size + 2), ln)
                x += w
            self.y -= maxlines * (size + 2) + 3
            self.c.setStrokeColorRGB(0.78, 0.78, 0.80)
            self.c.setLineWidth(0.4)
            self.c.line(x0, self.y + 3, x0 + sum(widths), self.y + 3)
        self.y -= 6

    def signature(self, name, designation, company, place, date, seal_text=None):
        self._space(42 * mm)
        self.y -= 10 * mm
        rx = W - RM
        self.c.setFont("Helvetica", 8.5)
        self.c.setFillColorRGB(0, 0, 0)
        self.c.drawString(LM, self.y, f"Place : {place}")
        self.c.drawString(LM, self.y - 12, f"Date  : {date}")

        if seal_text:
            self.c.saveState()
            self.c.setStrokeColorRGB(0.35, 0.35, 0.55)
            self.c.setFillColorRGB(0.35, 0.35, 0.55)
            self.c.setLineWidth(0.9)
            cx, cy = LM + 30 * mm, self.y - 20 * mm
            self.c.circle(cx, cy, 13 * mm, stroke=1, fill=0)
            self.c.setFont("Helvetica-Bold", 5.6)
            for i, ln in enumerate(simpleSplit(seal_text, "Helvetica-Bold", 5.6, 22 * mm)[:4]):
                self.c.drawCentredString(cx, cy + 5 - i * 7, ln)
            self.c.restoreState()

        self.c.setFont("Helvetica-Oblique", 9)
        self.c.drawRightString(rx, self.y - 4 * mm, "(signed)")
        self.c.setLineWidth(0.7)
        self.c.setStrokeColorRGB(0, 0, 0)
        self.c.line(rx - 62 * mm, self.y - 7 * mm, rx, self.y - 7 * mm)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawRightString(rx, self.y - 12 * mm, name)
        self.c.setFont("Helvetica", 8.5)
        self.c.drawRightString(rx, self.y - 17 * mm, designation)
        for i, ln in enumerate(simpleSplit("For " + company, "Helvetica", 8.5, 70 * mm)):
            self.c.drawRightString(rx, self.y - 22 * mm - i * 10, ln)
        self.y -= 34 * mm

    def note(self, text, size=7.4):
        self._space(12 * mm)
        self.c.setFont("Helvetica-Oblique", size)
        self.c.setFillColorRGB(0.40, 0.40, 0.40)
        for ln in simpleSplit(text, "Helvetica-Oblique", size, CW):
            self._space(10 * mm)
            self.c.drawString(LM, self.y, ln)
            self.y -= size + 2.2
        self.y -= 4

    def idcard(self, rows, photo_label="PHOTO"):
        """Boxed ID-card style block (Aadhaar / PAN)."""
        self._space(60 * mm)
        box_h = 48 * mm
        top = self.y
        self.c.setStrokeColorRGB(0.30, 0.30, 0.34)
        self.c.setLineWidth(1.0)
        self.c.rect(LM, top - box_h, CW, box_h, stroke=1, fill=0)
        # photo placeholder
        px, pw, ph = LM + 5 * mm, 25 * mm, 31 * mm
        py = top - 8 * mm - ph
        self.c.setStrokeColorRGB(0.55, 0.55, 0.58)
        self.c.setLineWidth(0.7)
        self.c.rect(px, py, pw, ph, stroke=1, fill=0)
        self.c.setFont("Helvetica", 7)
        self.c.setFillColorRGB(0.5, 0.5, 0.5)
        self.c.drawCentredString(px + pw / 2, py + ph / 2 + 4, photo_label)
        self.c.drawCentredString(px + pw / 2, py + ph / 2 - 6, "(specimen)")
        # fields
        fx = px + pw + 7 * mm
        fy = top - 9 * mm
        for label, value, bold in rows:
            self.c.setFont("Helvetica", 8)
            self.c.setFillColorRGB(0.28, 0.28, 0.28)
            self.c.drawString(fx, fy, label)
            self.c.setFont("Helvetica-Bold" if bold else "Helvetica", 10 if bold else 9)
            self.c.setFillColorRGB(0, 0, 0)
            self.c.drawString(fx + 34 * mm, fy, str(value))
            fy -= 12
        self.y = top - box_h - 8 * mm

    def save(self):
        self.c.save()
