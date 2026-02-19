# src/pdf_utils.py

import io
import os
import tempfile

import fitz  # PyMuPDF
from PIL import Image
import streamlit as st


def show_pdf_first_page_as_image(pdf_bytes: bytes, zoom: float = 2.0):
	"""PDF 1ページ目を画像化して表示（ブラウザ埋め込み回避）"""
	doc = fitz.open(stream=pdf_bytes, filetype="pdf")
	try:
		page = doc[0]
		mat = fitz.Matrix(zoom, zoom)
		pix = page.get_pixmap(matrix=mat)
		img = Image.open(io.BytesIO(pix.tobytes("png")))

		# streamlit 1.54.0: use_container_width 非推奨対応
		st.image(img, width="stretch")
	finally:
		doc.close()


def stamp_pdf_first_page(
	pdf_bytes: bytes,
	name: str,
	program: str = "",
	name_xy: tuple[float, float] = (80, 340),
	program_xy: tuple[float, float] = (80, 235),
	box_wh: tuple[float, float] = (340, 25),  # insert_text方式では未使用（互換のため残す）
	fontsize: float = 12,
	font_bytes: bytes | None = None,
) -> bytes:
	"""1ページ目に氏名・プログラムを追記したPDF(bytes)を返す。

	方針:
	- 日本語フォントはリポジトリ同梱 `fonts/NotoSansJP-Regular.ttf` を使用
	- （任意）font_bytes が渡された場合はそれを一時ファイル化して優先
	- 描画は insert_text（1点座標）で行う。insert_textbox より日本語が通りやすい。
	"""

	# --- フォントパス確定 ---
	this_dir = os.path.dirname(__file__)
	default_font_path = os.path.join(this_dir, "..", "fonts", "NotoSansJP-Regular.ttf")

	tmp_font_path = None
	try:
		if font_bytes:
			with tempfile.NamedTemporaryFile(delete=False, suffix=".ttf") as f:
				f.write(font_bytes)
				tmp_font_path = f.name
			font_path = tmp_font_path
		else:
			font_path = default_font_path

		if not os.path.exists(font_path):
			raise FileNotFoundError(f"Font file not found: {font_path}")

		# PyMuPDF フォント生成（ここが効いていれば日本語が出ます）
		font = fitz.Font(fontfile=font_path)

		# --- PDFへ追記 ---
		doc = fitz.open(stream=pdf_bytes, filetype="pdf")
		try:
			page = doc[0]
			color = (0, 0, 0)

			# 参加プログラム
			if program:
				page.insert_text(
					fitz.Point(program_xy[0], program_xy[1]),
					str(program),
					fontsize=fontsize,
					font=font,
					color=color,
				)

			# 氏名
			page.insert_text(
				fitz.Point(name_xy[0], name_xy[1]),
				str(name),
				fontsize=fontsize,
				font=font,
				color=color,
			)

			return doc.write()
		finally:
			doc.close()

	finally:
		if tmp_font_path and os.path.exists(tmp_font_path):
			try:
				os.remove(tmp_font_path)
			except Exception:
				pass