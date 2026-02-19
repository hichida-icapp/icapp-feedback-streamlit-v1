import io
import fitz  # PyMuPDF
from PIL import Image
import streamlit as st


def show_pdf_first_page_as_image(pdf_bytes: bytes, zoom: float = 2.0):
	doc = fitz.open(stream=pdf_bytes, filetype="pdf")
	page = doc[0]
	mat = fitz.Matrix(zoom, zoom)
	pix = page.get_pixmap(matrix=mat)
	img = Image.open(io.BytesIO(pix.tobytes("png")))
	st.image(img, use_container_width=True)


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

	NOTE:
	- いまは fontname="helv" のため、日本語氏名は文字化けする可能性があります。
	- 日本語フォントを使う場合、font_bytes をPyMuPDF側へ登録する処理を追加してください。
	"""
	doc = fitz.open(stream=pdf_bytes, filetype="pdf")
	page = doc[0]

	box_w, box_h = box_wh
	nx, ny = name_xy
	px, py = program_xy

	name_rect = fitz.Rect(nx, ny, nx + box_w, ny + box_h)
	program_rect = fitz.Rect(px, py, px + box_w, py + box_h)

	color = (0, 0, 0)

	if program:
		page.insert_textbox(
			program_rect,
			program,
			fontsize=fontsize,
			fontname="helv",
			color=color,
			align=fitz.TEXT_ALIGN_LEFT,
		)

	page.insert_textbox(
		name_rect,
		name,
		fontsize=fontsize,
		fontname="helv",
		color=color,
		align=fitz.TEXT_ALIGN_LEFT,
	)

	out = doc.write()
	doc.close()
	return out