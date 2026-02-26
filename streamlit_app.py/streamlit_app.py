import hashlib
import io
import re
import zipfile
from datetime import datetime

import pandas as pd
import streamlit as st

from src.dropbox_client import download_file_bytes, get_dbx, list_pdfs_in_folder
from src.id_utils import extract_id_from_filename
from src.mapping import (
    apply_memo_update,
    merge_mapping_with_pdfs,
    read_mapping_csv,
    to_csv_bytes,
)
from src.pdf_utils import show_pdf_first_page_as_image, stamp_pdf_first_page


st.set_page_config(page_title="Dropbox PDF Viewer", layout="wide")
st.title("iCaPP Feed Back Sheet PDFビューア（氏名で選択 / ID紐付けCSV）")

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
    "【原則，変更しない】Dropboxフォルダパス（直下のPDFを一覧表示）",
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
        st.dataframe(
            missing_pdf[["ID", "氏名", "参加プログラム", "備考"]],
            use_container_width=True,
        )

# 氏名で選択（同姓同名対策でIDも併記）
merged["表示名"] = merged.apply(
    lambda r: f"{r['氏名']}（{r['ID']}）"
    if pd.notna(r.get("ID"))
    else str(r.get("氏名")),
    axis=1,
)

options = merged.sort_values(["氏名", "ID"]).reset_index(drop=True)
selected_label = st.selectbox("氏名（ID）を選択", options["表示名"].tolist())
selected = options[options["表示名"] == selected_label].iloc[0]

st.caption(
    f"ID: {selected['ID']} / 氏名: {selected['氏名']} / 参加プログラム: {selected['参加プログラム']}"
)

# --------------------
# 備考（メモ）編集 → 確定ボタン → CSV再出力
# --------------------
st.subheader("備考メモ")
memo_key = f"memo_{selected['ID']}"
if memo_key not in st.session_state:
    st.session_state[memo_key] = "" if pd.isna(selected["備考"]) else str(selected["備考"])

st.text_area(
    "備考（メモ）を編集",
    key=memo_key,
    height=120,
)

col_apply, col_hint = st.columns([1, 3])

with col_apply:
    apply_clicked = st.button("変更を確定（備考へ反映）")

with col_hint:
    st.caption("編集後、このボタンを押すと更新後CSVのダウンロードが表示されます。")

if apply_clicked:
    updated_mapping = apply_memo_update(
        mapping_df,
        selected_id=str(selected["ID"]),
        new_memo=st.session_state[memo_key],
    )
    st.success("備考を反映しました。")
    st.download_button(
        "更新後CSVをダウンロード（備考反映）",
        data=to_csv_bytes(updated_mapping),
        file_name="mapping_updated.csv",
        mime="text/csv",
    )
else:
    st.info("変更を保存してCSVに反映するには『変更を確定（備考へ反映）』を押してください。")

# --------------------
# PDF取得・表示
# --------------------
if pd.isna(selected["path_lower"]):
    st.error(
        "このIDに対応するPDFがDropbox上で見つかりませんでした。ファイル名の先頭8文字（ID）を確認してください。"
    )
    st.stop()

with st.spinner("PDFを取得中..."):
    pdf_bytes = download_file_bytes(dbx, selected["path_lower"])

# --------------------
# 座標調整UI + ロゴ（PNG）
# --------------------
# デフォルト（expander を開かなくても必ず定義される）
name_x, name_y = 140.0, 320.0
prog_x, prog_y = 105.0, 190.0
logo_x, logo_y = 105.0, 150.0
logo_w, logo_h = 180.0, 60.0

with st.expander("プログラム：ロゴのアップロード；PDFへ氏名・ロゴ（座標調整）", expanded=False):
    st.caption("備考：座標は調整済み．必要時のみ開いて調整してください。")

    # ロゴアップロード（セッション内保持）
    st.subheader("参加プログラム：ロゴ（PNG）")
    uploaded_logo = st.file_uploader(
        "ロゴ画像（PNG）をアップロード（このセッション内で保持）：サイズ 幅180px　高さ60px のPNG形式の画像ファイルを用意してください．",
        type=["png"],
        key="program_logo_uploader",
    )

    if "program_logo_bytes" not in st.session_state:
        st.session_state.program_logo_bytes = None
        st.session_state.program_logo_hash = None

    if uploaded_logo is not None:
        new_bytes = uploaded_logo.getvalue()
        new_hash = hashlib.sha256(new_bytes).hexdigest()
        if st.session_state.program_logo_hash != new_hash:
            st.session_state.program_logo_bytes = new_bytes
            st.session_state.program_logo_hash = new_hash
            st.success("ロゴを更新しました（このセッションで保持されます）。")

    if st.session_state.program_logo_bytes:
        st.image(st.session_state.program_logo_bytes, caption="現在のロゴ", width=220)
    else:
        st.info("ロゴ未設定（必要ならPNGをアップロードしてください）。")

    # 文字座標
    col1, col2 = st.columns(2)

    with col1:
        name_x = st.number_input("氏名X（左上）", value=name_x, step=1.0)
        name_y = st.number_input("氏名Y（左上）", value=name_y, step=1.0)

    with col2:
        prog_x = st.number_input("参加プログラムX（左上）", value=prog_x, step=1.0)
        prog_y = st.number_input("参加プログラムY（左上）", value=prog_y, step=1.0)

    # ロゴ枠
    st.subheader("ロゴ枠（左上 + 幅高さ）")
    col3, col4 = st.columns(2)

    with col3:
        logo_x = st.number_input("ロゴX（左上）", value=logo_x, step=1.0)
        logo_y = st.number_input("ロゴY（左上）", value=logo_y, step=1.0)

    with col4:
        logo_w = st.number_input("ロゴ幅W", value=logo_w, step=1.0, min_value=1.0)
        logo_h = st.number_input("ロゴ高さH", value=logo_h, step=1.0, min_value=1.0)

BOX_W, BOX_H = 340.0, 25.0

stamped_pdf_bytes = stamp_pdf_first_page(
    pdf_bytes,
    name=str(selected["氏名"]),
    program=str(selected["参加プログラム"]).strip()
    if pd.notna(selected.get("参加プログラム"))
    else "",
    name_xy=(name_x, name_y),
    program_xy=(prog_x, prog_y),
    box_wh=(BOX_W, BOX_H),
    fontsize=11,
    logo_bytes=st.session_state.get("program_logo_bytes"),
    logo_rect_xywh=(logo_x, logo_y, logo_w, logo_h),
    debug_draw_logo_rect=False,
    font_bytes=None,
)

st.download_button(
    "PDFをダウンロード（氏名入り）",
    data=stamped_pdf_bytes,
    file_name=selected["PDFファイル"],
    mime="application/pdf",
)

# --------------------
# 一括生成（ZIP）
# - CSVに登録されている全IDについて、PDFがあるものだけ処理（PDFが無いIDはスキップ）
# - ZIP内のPDFファイル名: ID_氏名.pdf
# - ZIPファイル名: iCaPP_FeedBackSheet_yyyymmdd.zip
# --------------------
st.divider()
st.subheader("一括出力（ZIP）")

batch_clicked = st.button("全員分PDFを一括生成（ZIP）")


def safe_filename(s: str) -> str:
    s = "" if s is None else str(s)
    # Windowsでも壊れにくい最低限の置換
    return re.sub(r"[\\/:*?\"<>|]+", "_", s).strip()


if batch_clicked:
    targets = options[pd.notna(options["path_lower"])].copy()
    skipped = options[pd.isna(options["path_lower"])][["ID", "氏名", "参加プログラム"]].copy()

    if len(targets) == 0:
        st.warning("Dropbox上でPDFが見つかるIDがありませんでした。")
        st.stop()

    progress = st.progress(0)
    zip_buf = io.BytesIO()

    with st.spinner("全員分のPDFを生成中..."):
        with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            total = len(targets)

            for i, (_, r) in enumerate(targets.iterrows(), start=1):
                one_pdf_bytes = download_file_bytes(dbx, r["path_lower"])

                one_stamped = stamp_pdf_first_page(
                    one_pdf_bytes,
                    name=str(r["氏名"]),
                    program=str(r["参加プログラム"]).strip()
                    if pd.notna(r.get("参加プログラム"))
                    else "",
                    name_xy=(name_x, name_y),
                    program_xy=(prog_x, prog_y),
                    box_wh=(BOX_W, BOX_H),
                    fontsize=11,
                    logo_bytes=st.session_state.get("program_logo_bytes"),
                    logo_rect_xywh=(logo_x, logo_y, logo_w, logo_h),
                    debug_draw_logo_rect=False,
                    font_bytes=None,
                )

                sid = str(r["ID"]).strip()
                sname = str(r["氏名"]).strip()
                zip_pdf_name = safe_filename(f"{sid}_{sname}.pdf")

                zf.writestr(zip_pdf_name, one_stamped)
                progress.progress(i / total)

    zip_buf.seek(0)

    st.success(f"ZIP生成完了：{len(targets)} 件（スキップ: {len(skipped)} 件）")

    if len(skipped) > 0:
        with st.expander("PDFが無くスキップしたID（確認用）"):
            st.dataframe(skipped, use_container_width=True)

    today_yyyymmdd = datetime.now().strftime("%Y%m%d")

    st.download_button(
        "ZIPをダウンロード（全員分）",
        data=zip_buf.getvalue(),
        file_name=f"iCaPP_FeedBackSheet_{today_yyyymmdd}.zip",
        mime="application/zip",
    )

show_pdf_first_page_as_image(pdf_bytes)