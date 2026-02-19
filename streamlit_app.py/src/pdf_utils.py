import io
import os
import tempfile

import fitz  # PyMuPDF
from PIL import Image
import streamlit as st


def show_pdf_first_page_as_image(pdf_bytes: bytes, zoom: float = 2.0):
	doc = fitz.open(stream=pdf_bytes, filetype="pdf")
	page = doc[0]

	mat = fitz.Matrix(zoom, zoom)
	pix = page.get_pixmap(matrix=mat)
	img = Image.open(io.BytesIO(pix.tobytes("png")))

	# streamlit 1.54.0: use_container_width 非推奨対応
	st.image(img, width="stretch")


def stamp_pdf_first_page(
	pdf_bytes: bytes,
	name: str,
	program: str = "",
	name_xy: tuple[float, float] = (80, 340),
	program_xy: tuple[float, float] = (80, 235),
	box_wh: tuple[float, float] = (340, 25),
	fontsize: float = 12,
	font_bytes: bytes | None = None,
) -> bytes:
	"""1ページ目にテキストを追記したPDF(bytes)を返す。

	- デフォルトではリポジトリ同梱フォント（fonts/NotoSansJP-VariableFont_wght.ttf）を使います。
	- font_bytes が渡された場合のみ、一時ファイルとして保存して利用します（任意）。
	"""
	doc = fitz.open(stream=pdf_bytes, filetype="pdf")
	page = doc[0]

	box_w, box_h = box_wh
	nx, ny = name_xy
	px, py = program_xy

	name_rect = fitz.Rect(nx, ny, nx + box_w, ny + box_h)
	program_rect = fitz.Rect(px, py, px + box_w, py + box_h)

	color = (0, 0, 0)

	# src/pdf_utils.py から見た相対パスで fonts/ を指す
	this_dir = os.path.dirname(__file__)
	# default_font_path = os.path.join(this_dir, "..", "fonts", "NotoSansJP-VariableFont_wght.ttf")
	default_font_path = os.path.join(this_dir, "..", "fonts", "NotoSansJP-Regular.ttf")

	tmp_font_path = None
	try:
		# font_bytes があればそれを優先（任意運用）
		if font_bytes:
			with tempfile.NamedTemporaryFile(delete=False, suffix=".ttf") as f:
				f.write(font_bytes)
				tmp_font_path = f.name
			font_path = tmp_font_path
		else:
			font_path = default_font_path
			
		if not os.path.exists(font_path):
			raise FileNotFoundError(f"Font file not found: {font_path}")

		common_kwargs = dict(
			fontsize=fontsize,
			color=color,
			align=fitz.TEXT_ALIGN_LEFT,
			fontfile=font_path,
			# base14名。fontfile指定時も一応入れておく
			fontname="helv",
		)
        

		if program:
			page.insert_textbox(program_rect, program, **common_kwargs)

		page.insert_textbox(name_rect, name, **common_kwargs)

		out = doc.write()
		return out

	finally:
		doc.close()
		if tmp_font_path and os.path.exists(tmp_font_path):
			try:
				os.remove(tmp_font_path)
			except Exception:
				pass