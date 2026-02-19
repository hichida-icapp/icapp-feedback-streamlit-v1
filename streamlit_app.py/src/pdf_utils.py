# src/pdf_utils.py

import io
import os
import tempfile

import fitz  # PyMuPDF
from PIL import Image
import streamlit as st


def show_pdf_first_page_as_image(pdf_bytes: bytes, zoom: float = 2.0) -> None:
    """PDF 1ページ目を画像化して表示（ブラウザ埋め込み回避）"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[0]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        st.image(img, width="stretch")
    finally:
        doc.close()


def stamp_pdf_first_page(
    pdf_bytes: bytes,
    name: str,
    program: str = "",
    name_xy: tuple[float, float] = (80, 340),
    program_xy: tuple[float, float] = (80, 235),
    box_wh: tuple[float, float] = (340, 25),  # 互換のため残す（未使用）
    fontsize: float = 12,
    font_bytes: bytes | None = None,
) -> bytes:
    """1ページ目に氏名・プログラムを追記したPDF(bytes)を返す。

    - 日本語フォントはリポジトリ同梱 fonts/NotoSansJP-Regular.ttf を使用
    - （任意）font_bytes が渡された場合は一時ファイル化して優先
    - PyMuPDF 1.27.1 では insert_text に font= は渡せないので fontfile= を使う
    """

    this_dir = os.path.dirname(__file__)
    default_font_path = os.path.join(this_dir, "..", "fonts", "NotoSansJP-Regular.ttf")

    tmp_font_path = None
    if font_bytes:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ttf") as f:
            f.write(font_bytes)
            tmp_font_path = f.name
        font_path = tmp_font_path
    else:
        font_path = default_font_path

    if not os.path.exists(font_path):
        raise FileNotFoundError(f"Font file not found: {font_path}")

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[0]
        color = (0, 0, 0)

        # 参加プログラム（1点座標に描画）
        if program:
            page.insert_text(
                fitz.Point(program_xy[0], program_xy[1]),
                str(program),
                fontsize=fontsize,
                color=color,
                fontfile=font_path,
                fontname="NotoSansJP",
            )

        # 氏名（1点座標に描画）
        page.insert_text(
            fitz.Point(name_xy[0], name_xy[1]),
            str(name),
            fontsize=fontsize,
            color=color,
            fontfile=font_path,
        )

        return doc.write()

    finally:
        doc.close()
        if tmp_font_path and os.path.exists(tmp_font_path):
            try:
                os.remove(tmp_font_path)
            except Exception:
                pass