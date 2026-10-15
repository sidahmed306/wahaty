"""Facture PDF bilingue (français à gauche, arabe à droite), générée avec ReportLab.

L'arabe est « mis en forme » (lettres liées, arabic-reshaper) puis remis dans l'ordre
d'affichage de droite à gauche (python-bidi), avec la police libre Noto Naskh Arabic.
Le PDF est produit à la demande à partir de la copie figée dans la facture : il est donc
toujours identique, et rien n'est stocké sur le disque (le disque de Render est effacé
à chaque redémarrage).
"""

import re
from io import BytesIO
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONT_DIR = Path(__file__).parent / "fonts"
AR, AR_BOLD = "NotoNaskhArabic", "NotoNaskhArabic-Bold"
LATIN, LATIN_BOLD = "Helvetica", "Helvetica-Bold"
ARABIC_RE = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")

WIDTH, HEIGHT = A4
MARGIN = 40
RIGHT = WIDTH - MARGIN
ROW = 18
BOTTOM_LIMIT = 170  # place gardée pour les totaux et le pied de page
GREEN = colors.HexColor("#2f6b3b")
LIGHT = colors.HexColor("#eef4ee")


def register_fonts():
    registered = pdfmetrics.getRegisteredFontNames()
    if AR not in registered:
        pdfmetrics.registerFont(TTFont(AR, FONT_DIR / "NotoNaskhArabic-Regular.ttf"))
        pdfmetrics.registerFont(TTFont(AR_BOLD, FONT_DIR / "NotoNaskhArabic-Bold.ttf"))


def has_arabic(text):
    return bool(ARABIC_RE.search(text or ""))


def shape(text):
    """Texte prêt à dessiner : l'arabe est lié et mis de droite à gauche."""
    text = str(text or "")
    return get_display(arabic_reshaper.reshape(text)) if has_arabic(text) else text


def runs(text, bold=False):
    """Découpe un texte (déjà en ordre d'affichage) en morceaux d'une même police :
    la police arabe ne contient pas les lettres latines, et inversement."""
    arabic_font, latin_font = (AR_BOLD, LATIN_BOLD) if bold else (AR, LATIN)
    pieces = []
    for char in text:
        font = arabic_font if ARABIC_RE.match(char) else latin_font
        if char == " " and pieces:
            font = pieces[-1][0]  # un espace garde la police du morceau en cours
        if pieces and pieces[-1][0] == font:
            pieces[-1][1] += char
        else:
            pieces.append([font, char])
    return pieces


class InvoiceDrawer:
    def __init__(self, invoice):
        self.invoice = invoice
        self.buffer = BytesIO()
        self.c = canvas.Canvas(self.buffer, pagesize=A4)
        self.c.setTitle(f"Facture {invoice.number}")
        self.c.setAuthor(invoice.seller_snapshot.get("name", ""))
        self.page = 1

    # --- petits outils ------------------------------------------------------------

    def text(self, x, y, value, size=10, bold=False, align="left", color=colors.black):
        """Écrit un texte français, arabe ou mélangé, aligné à gauche, à droite ou centré."""
        pieces = runs(shape(value), bold)
        width = sum(pdfmetrics.stringWidth(t, f, size) for f, t in pieces)
        x = {"left": x, "right": x - width, "center": x - width / 2}[align]
        self.c.setFillColor(color)
        for font, piece in pieces:
            self.c.setFont(font, size)
            self.c.drawString(x, y, piece)
            x += pdfmetrics.stringWidth(piece, font, size)

    def bilingual(self, y, fr, ar, size=10, bold=False, color=colors.black):
        """Libellé français à gauche, arabe à droite, sur la même ligne."""
        self.text(MARGIN, y, fr, size, bold, color=color)
        self.text(RIGHT, y, ar, size, bold, align="right", color=color)

    # --- parties de la facture ----------------------------------------------------

    def header(self):
        inv = self.invoice
        seller = inv.seller_snapshot
        self.c.setFillColor(GREEN)
        self.c.rect(0, HEIGHT - 8, WIDTH, 8, stroke=0, fill=1)
        self.bilingual(HEIGHT - 50, "FACTURE", "فاتورة", size=22, bold=True, color=GREEN)
        self.text(WIDTH / 2, HEIGHT - 50, seller.get("name", ""), 13, bold=True, align="center")
        y = HEIGHT - 68
        for line in (seller.get("phone"), seller.get("address")):
            if line:
                self.text(WIDTH / 2, y, line, 9, align="center", color=colors.grey)
                y -= 12

        y = HEIGHT - 110
        order = inv.order
        for fr, ar, value in (
            ("N° de facture", "رقم الفاتورة", inv.number),
            ("Date", "التاريخ", inv.issue_date.strftime("%d/%m/%Y")),
            ("Commande", "الطلب", order.number),
        ):
            self.bilingual(y, fr, ar, 10)
            self.text(WIDTH / 2, y, value, 10, bold=True, align="center")
            y -= 15

        customer = inv.customer_snapshot
        y -= 10
        self.c.setFillColor(LIGHT)
        self.c.roundRect(MARGIN, y - 52, RIGHT - MARGIN, 66, 6, stroke=0, fill=1)
        self.bilingual(y, "Client", "الزبون", 10, bold=True, color=GREEN)
        self.text(WIDTH / 2, y, customer.get("name", ""), 11, bold=True, align="center")
        details = [customer.get("phone"), customer.get("address"), customer.get("city")]
        for line in filter(None, details):
            y -= 14
            self.text(WIDTH / 2, y, line, 9, align="center")
        return HEIGHT - 260

    COLUMNS = (
        # (libellé fr, libellé ar, x, alignement, clé)
        ("Produit", "المنتج", MARGIN + 4, "left", "product"),
        ("Quantité", "الكمية", 330, "right", "quantity"),
        ("Unité", "الوحدة", 345, "left", "unit"),
        ("Prix unitaire", "سعر الوحدة", 470, "right", "unit_price"),
        ("Total", "المجموع", RIGHT - 4, "right", "line_total"),
    )

    def table_header(self, y):
        self.c.setFillColor(GREEN)
        self.c.rect(MARGIN, y - 22, RIGHT - MARGIN, 34, stroke=0, fill=1)
        for fr, ar, x, align, _ in self.COLUMNS:
            self.text(x, y, fr, 8.5, bold=True, align=align, color=colors.white)
            self.text(x, y - 14, ar, 8.5, bold=True, align=align, color=colors.white)
        return y - 40

    def new_page(self):
        self.footer()
        self.c.showPage()
        self.page += 1
        self.text(MARGIN, HEIGHT - 40, self.invoice.number, 10, bold=True)
        return self.table_header(HEIGHT - 70)

    def lines(self, y):
        y = self.table_header(y)
        for index, line in enumerate(self.invoice.lines_snapshot):
            if y < BOTTOM_LIMIT:
                y = self.new_page()
            if index % 2:
                self.c.setFillColor(LIGHT)
                self.c.rect(MARGIN, y - 5, RIGHT - MARGIN, ROW, stroke=0, fill=1)
            for _, _, x, align, key in self.COLUMNS:
                self.text(x, y, line[key], 9.5, align=align)
            y -= ROW
        return y

    def totals(self, y):
        inv = self.invoice
        y -= 10
        self.c.setStrokeColor(GREEN)
        self.c.line(250, y + 8, RIGHT, y + 8)
        rows = [
            ("Sous-total", "المجموع الفرعي", inv.subtotal, False),
            ("Livraison", "التوصيل", inv.delivery_fee, False),
            ("Remise", "الخصم", -inv.discount if inv.discount else inv.discount, False),
            ("Total à payer (MRU)", "المبلغ الإجمالي (أوقية)", inv.total_amount, True),
        ]
        for fr, ar, value, bold in rows:
            size = 11 if bold else 9.5
            self.text(250, y, fr, size, bold)
            self.text(475, y, ar, size, bold, align="right")
            self.text(RIGHT - 4, y, f"{value:,.2f}".replace(",", " "), size, bold, align="right")
            y -= 17 if bold else 15
        return y

    def cancelled_stamp(self):
        stamp = colors.Color(0.8, 0.1, 0.1, alpha=0.18)  # rouge transparent : chiffres lisibles
        self.c.saveState()
        self.c.translate(WIDTH / 2, HEIGHT / 2)
        self.c.rotate(30)
        self.text(0, 20, "ANNULÉE", 70, bold=True, align="center", color=stamp)
        self.text(0, -60, "ملغاة", 70, bold=True, align="center", color=stamp)
        self.c.restoreState()

    def footer(self):
        if self.invoice.status == self.invoice.Status.CANCELLED:
            self.cancelled_stamp()
        self.c.setStrokeColor(colors.lightgrey)
        self.c.line(MARGIN, 60, RIGHT, 60)
        self.bilingual(45, "Montants en ouguiya (MRU)", "المبالغ بالأوقية", 8, color=colors.grey)
        self.text(WIDTH / 2, 45, f"Page {self.page}", 8, align="center", color=colors.grey)
        self.text(WIDTH / 2, 32, "Wahaty · واحتي", 8, align="center", color=colors.grey)

    def render(self):
        register_fonts()
        # Le tableau s'arrête toujours au-dessus de BOTTOM_LIMIT : il reste la place des totaux.
        self.totals(self.lines(self.header()))
        self.footer()
        self.c.save()
        return self.buffer.getvalue()


def invoice_pdf(invoice):
    return InvoiceDrawer(invoice).render()
