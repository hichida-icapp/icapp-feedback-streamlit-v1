import re


def extract_id_from_filename(filename: str) -> str | None:
	"""ファイル名の先頭8文字をIDとして返す（8文字未満ならNone）"""
	if not filename:
		return None

	head = filename[:8]
	if not re.fullmatch(r"[0-9A-Za-z_-]{8}", head):
		return None

	return head