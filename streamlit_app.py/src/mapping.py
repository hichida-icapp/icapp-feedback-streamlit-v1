import pandas as pd
import streamlit as st


REQUIRED_COLS = ["ID", "氏名", "参加プログラム", "備考"]


def read_mapping_csv(uploaded_file):
    if uploaded_file is None:
        st.info("まずCSVをアップロードしてください。")
        return None

    try:
        df = pd.read_csv(uploaded_file)
        df = df.rename(columns=lambda c: str(c).strip())

        missing = [c for c in REQUIRED_COLS if c not in df.columns]
        if missing:
            st.error(f"CSVの列が不足しています: {missing}")
            return None

        df["ID"] = df["ID"].astype(str).str.strip()
        df["氏名"] = df["氏名"].astype(str).str.strip()
        df["参加プログラム"] = df["参加プログラム"].astype(str).fillna("").str.strip()
        df["備考"] = df["備考"].astype(str).fillna("")

        st.caption(f"読み込み行数: {len(df)}")
        return df

    except Exception as e:
        st.error(f"CSVの読み込みに失敗しました: {e}")
        return None


def merge_mapping_with_pdfs(mapping_df: pd.DataFrame, pdf_df: pd.DataFrame) -> pd.DataFrame:
    return mapping_df.merge(pdf_df, on="ID", how="left")


def apply_memo_update(mapping_df: pd.DataFrame, selected_id: str, new_memo: str) -> pd.DataFrame:
    updated = mapping_df.copy()
    updated.loc[updated["ID"] == str(selected_id).strip(), "備考"] = new_memo
    return updated


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")