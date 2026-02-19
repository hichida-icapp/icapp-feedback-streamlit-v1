import pandas as pd
import streamlit as st

from src.dropbox_client import get_dbx, list_pdfs_in_folder, download_file_bytes
from src.id_utils import extract_id_from_filename
from src.mapping import read_mapping_csv, merge_mapping_with_pdfs, apply_memo_update, to_csv_bytes
from src.pdf_utils import show_pdf_first_page_as_image, stamp_pdf_first_page

st.set_page_config(page_title="Dropbox PDF Viewer", layout="wide")
st.title("Dropbox PDFビューア（氏名で選択 / ID紐付けCSV）")

# --------------------
# CSV読込
# --------------------
st.subheader("ID→氏名 紐付けCSV")
uploaded = st.file_uploader(
	"CSVをアップロード（列: ID, 氏名, 参加プログラム, 備考）",
	type=["csv"],
)

mapping_df = read_mapping_csv(uploaded)
if mapping_df is None:
	st.stop()

st.divider()

# --------------------
# PDF一覧（Dropbox）
# --------------------
folder_path = st.text_input(
	"Dropboxフォルダパス（直下のPDFを一覧表示）",
	value="/PDF",
	placeholder="例: /PDF",
)
if not folder_path:
	st.stop()

dbx = get_dbx(st.secrets)
with st.spinner("PDF一覧を取得中..."):
	pdf_entries = list_pdfs_in_folder(dbx, folder_path)

if not pdf_entries:
	st.warning("PDFが見つかりませんでした（フォルダパスと権限を確認）。")
	st.stop()

# PDF側（Dropbox）からIDを抽出してDataFrame化
pdf_rows = []
for e in pdf_entries:
	fid = extract_id_from_filename(e.name)
	pdf_rows.append({"PDFファイル": e.name, "path_lower": e.path_lower, "ID": fid})

pdf_df = pd.DataFrame(pdf_rows)
merged = merge_mapping_with_pdfs(mapping_df, pdf_df)

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

updated_mapping = apply_memo_update(mapping_df, selected_id=str(selected["ID"]), new_memo=new_memo)

st.download_button(
	"更新後CSVをダウンロード（備考反映）",
	data=to_csv_bytes(updated_mapping),
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
# フォントはリポジトリに同梱（例: fonts/NotoSansJP-VariableFont_wght.ttf）
# Streamlit Cloud でも同じパスで参照できるようにしています

col1, col2 = st.columns(2)
with col1:
	name_x = st.number_input("氏名X（左上）", value=80.0, step=1.0)
	name_y = st.number_input("氏名Y（左上）", value=340.0, step=1.0)
with col2:
	prog_x = st.number_input("参加プログラムX（左上）", value=80.0, step=1.0)
	prog_y = st.number_input("参加プログラムY（左上）", value=235.0, step=1.0)

BOX_W, BOX_H = 340.0, 25.0
stamped_pdf_bytes = stamp_pdf_first_page(
	pdf_bytes,
	name=str(selected["氏名"]),
	program=str(selected["参加プログラム"]).strip() if pd.notna(selected.get("参加プログラム")) else "",
	name_xy=(name_x, name_y),
	program_xy=(prog_x, prog_y),
	box_wh=(BOX_W, BOX_H),
	fontsize=12,
	# font は src/pdf_utils.py 側で同梱フォントを参照
	font_bytes=None,
)

st.download_button(
	"PDFをダウンロード（氏名入り）",
	data=stamped_pdf_bytes,
	file_name=selected["PDFファイル"],
	mime="application/pdf",
)

show_pdf_first_page_as_image(pdf_bytes)