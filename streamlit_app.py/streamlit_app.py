import io
import re
import streamlit as st
import dropbox

# 1ページPDFを画像として表示（ChromeのPDF埋め込みブロック回避）
import fitz  # PyMuPDF
from PIL import Image

import pandas as pd

st.set_page_config(page_title="Dropbox PDF Viewer", layout="wide")
st.title("Dropbox PDFビューア（氏名で選択 / ID紐付けCSV）")


# --------------------
# Dropbox
# --------------------
def get_dbx():
    app_key = st.secrets["DROPBOX_APP_KEY"]
    app_secret = st.secrets["DROPBOX_APP_SECRET"]
    refresh_token = st.secrets["DROPBOX_REFRESH_TOKEN"]

    return dropbox.Dropbox(
        oauth2_refresh_token=refresh_token,
        app_key=app_key,
        app_secret=app_secret,
    )


def list_pdfs_in_folder(dbx: dropbox.Dropbox, folder_path: str):
    """直下のPDFだけ（再帰しない）"""
    res = dbx.files_list_folder(folder_path, recursive=False)

    entries = []
    for e in res.entries:
        if isinstance(e, dropbox.files.FileMetadata) and e.name.lower().endswith(".pdf"):
            entries.append(e)

    entries.sort(key=lambda x: x.name)
    return entries


def download_file_bytes(dbx: dropbox.Dropbox, path_lower: str):
    md, resp = dbx.files_download(path_lower)
    return resp.content


# --------------------
# PDF表示（1ページ画像）
# --------------------
def show_pdf_first_page_as_image(pdf_bytes: bytes, zoom: float = 2.0):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]

    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img = Image.open(io.BytesIO(pix.tobytes("png")))

    st.image(img, use_container_width=True)


# --------------------
# ID抽出
# --------------------
def extract_id_from_filename(filename: str) -> str | None:
    """ファイル名の先頭8文字をIDとして返す（8文字未満ならNone）"""
    if not filename:
        return None

    head = filename[:8]

    # 8桁数字だけ等に制限したい場合はここを調整
    if not re.fullmatch(r"[0-9A-Za-z_-]{8}", head):
        return None

    return head


# --------------------
# PDFに氏名等を追記（ダウンロード用）
# --------------------
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

    - name_xy / program_xy は「左上座標」(x, y) のみを入力
    - box_wh はテキストボックスの幅・高さ
    NOTE: 座標はPDFテンプレートに依存。
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]

    box_w, box_h = box_wh

    # PyMuPDF座標: 左上が(0,0)、単位はpoint
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


# --------------------
# CSV読込
# --------------------
st.subheader("ID→氏名 紐付けCSV")

uploaded = st.file_uploader(
    "CSVをアップロード（列: ID, 氏名, 参加プログラム, 備考）",
    type=["csv"],
)

mapping_df = None
if uploaded is not None:
    try:
        mapping_df = pd.read_csv(uploaded)
        mapping_df = mapping_df.rename(columns=lambda c: str(c).strip())

        required_cols = ["ID", "氏名", "参加プログラム", "備考"]
        missing = [c for c in required_cols if c not in mapping_df.columns]
        if missing:
            st.error(f"CSVの列が不足しています: {missing}")
            st.stop()

        mapping_df["ID"] = mapping_df["ID"].astype(str).str.strip()
        mapping_df["氏名"] = mapping_df["氏名"].astype(str).str.strip()
        mapping_df["参加プログラム"] = mapping_df["参加プログラム"].astype(str).fillna("").str.strip()
        mapping_df["備考"] = mapping_df["備考"].astype(str).fillna("")

        st.caption(f"読み込み行数: {len(mapping_df)}")

    except Exception as e:
        st.error(f"CSVの読み込みに失敗しました: {e}")
        st.stop()
else:
    st.info("まずCSVをアップロードしてください。")


st.divider()

# --------------------
# PDF一覧（Dropbox）
# --------------------
folder_path = st.text_input(
    "Dropboxフォルダパス（直下のPDFを一覧表示）",
    value="/PDF",
    placeholder="例: /PDF",
)

if not folder_path or mapping_df is None:
    st.stop()


dbx = get_dbx()

with st.spinner("PDF一覧を取得中..."):
    pdf_entries = list_pdfs_in_folder(dbx, folder_path)

if not pdf_entries:
    st.warning("PDFが見つかりませんでした（フォルダパスと権限を確認）。")
    st.stop()

# PDF側（Dropbox）から ID を抽出して一覧を作る
pdf_rows = []
for e in pdf_entries:
    fid = extract_id_from_filename(e.name)
    pdf_rows.append({"PDFファイル": e.name, "path_lower": e.path_lower, "ID": fid})

pdf_df = pd.DataFrame(pdf_rows)

# 紐付け（CSV）と結合
merged = mapping_df.merge(pdf_df, on="ID", how="left")

# PDFが見つからない人も分かるようにする
missing_pdf = merged[merged["PDFファイル"].isna()]
if len(missing_pdf) > 0:
    with st.expander("PDFが見つからないID（確認用）"):
        st.dataframe(missing_pdf[["ID", "氏名", "参加プログラム", "備考"]], use_container_width=True)

# 氏名で選択（同姓同名対策でIDも併記）
merged["表示名"] = merged.apply(
    lambda r: f"{r['氏名']}（{r['ID']}）" if pd.notna(r.get("ID")) else str(r.get("氏名")),
    axis=1,
)

options = merged.sort_values(["氏名", "ID"]).reset_index(drop=True)
selected_label = st.selectbox("氏名（ID）を選択", options["表示名"].tolist())
selected = options[options["表示名"] == selected_label].iloc[0]

st.caption(f"ID: {selected['ID']} / 氏名: {selected['氏名']} / 参加プログラム: {selected['参加プログラム']}")

# --------------------
# 備考（メモ）編集 → CSV再出力
# --------------------
st.subheader("備考メモ")
new_memo = st.text_area(
    "備考（メモ）を編集",
    value="" if pd.isna(selected["備考"]) else str(selected["備考"]),
    height=120,
)

# 反映したCSVを生成してダウンロードできるようにする
updated = mapping_df.copy()
# IDが一致する行を更新（同一IDが複数行ある場合は全て更新）
updated.loc[updated["ID"] == str(selected["ID"]).strip(), "備考"] = new_memo

csv_bytes = updated.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "更新後CSVをダウンロード（備考反映）",
    data=csv_bytes,
    file_name="mapping_updated.csv",
    mime="text/csv",
)

# --------------------
# PDF取得・表示
# --------------------
if pd.isna(selected["path_lower"]):
    st.error("このIDに対応するPDFがDropbox上で見つかりませんでした。ファイル名の先頭8文字（ID）を確認してください。")
    st.stop()

with st.spinner("PDFを取得中..."):
    pdf_bytes = download_file_bytes(dbx, selected["path_lower"])

# --------------------
# 座標調整UI（左上座標のみ）
# --------------------
st.subheader("PDFへ氏名を入れてダウンロード（座標調整）")
# 日本語フォント（TTF/OTF）をアップロード（未指定なら英数字向けフォールバック）
font_up = st.file_uploader("日本語フォントをアップロード（.ttf / .otf）", type=["ttf", "otf"])
font_bytes = font_up.read() if font_up is not None else None
col1, col2 = st.columns(2)
with col1:
    name_x = st.number_input("氏名X（左上）", value=80.0, step=1.0)
    name_y = st.number_input("氏名Y（左上）", value=340.0, step=1.0)
with col2:
    prog_x = st.number_input("参加プログラムX（左上）", value=80.0, step=1.0)
    prog_y = st.number_input("参加プログラムY（左上）", value=235.0, step=1.0)

# ボックスサイズは固定（必要なら後でUI化）
BOX_W, BOX_H = 340.0, 25.0

# ダウンロード用に氏名入りPDFを生成（表示は元PDFのまま）
stamped_pdf_bytes = stamp_pdf_first_page(
    pdf_bytes,
    name=str(selected["氏名"]),
    program=str(selected["参加プログラム"]).strip() if pd.notna(selected.get("参加プログラム")) else "",
    name_xy=(name_x, name_y),
    program_xy=(prog_x, prog_y),
    box_wh=(BOX_W, BOX_H),
    font_bytes=font_bytes,
)

st.download_button(
    "PDFをダウンロード（氏名入り）",
    data=stamped_pdf_bytes,
    file_name=selected["PDFファイル"],
    mime="application/pdf",
)

# プレビューは元PDFのまま（高速化・安全側）
show_pdf_first_page_as_image(pdf_bytes)