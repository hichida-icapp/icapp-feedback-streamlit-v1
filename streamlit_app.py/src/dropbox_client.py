import dropbox


def get_dbx(secrets) -> dropbox.Dropbox:
    app_key = secrets["DROPBOX_APP_KEY"]
    app_secret = secrets["DROPBOX_APP_SECRET"]
    refresh_token = secrets["DROPBOX_REFRESH_TOKEN"]

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


def download_file_bytes(dbx: dropbox.Dropbox, path_lower: str) -> bytes:
    _, resp = dbx.files_download(path_lower)
    return resp.content