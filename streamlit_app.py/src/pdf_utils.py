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
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]

    box_w, box_h = box_wh
    nx, ny = name_xy
    px, py = program_xy

    name_rect = fitz.Rect(nx, ny, nx + box_w, ny + box_h)
    program_rect = fitz.Rect(px, py, px + box_w, py + box_h)

    color = (0, 0, 0)

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

        # デバッグ出力は font_path 確定後に
        import streamlit as st
        st.write("font_path:", font_path)
        st.write("exists:", os.path.exists(font_path))
        st.write("size:", os.path.getsize(font_path) if os.path.exists(font_path) else None)

        if not os.path.exists(font_path):
            raise FileNotFoundError(f"Font file not found: {font_path}")

        common_kwargs = dict(
            fontsize=fontsize,
            color=color,
            align=fitz.TEXT_ALIGN_LEFT,
            fontfile=font_path,
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