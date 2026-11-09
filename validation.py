"""Aturan input dipakai bersama oleh form web dan API."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

STATUSES = {"pending": "Belum dikerjakan", "in_progress": "Progres", "done": "Selesai"}
PRIORITIES = {"low": "Rendah", "medium": "Sedang", "high": "Tinggi"}
VIEWS = {"active": "Tugas aktif", "completed": "Selesai", "archived": "Arsip"}
DUE_FILTERS = {"all": "Semua tenggat", "overdue": "Terlambat", "today": "Hari ini", "upcoming": "Mendatang"}
JAKARTA = ZoneInfo("Asia/Jakarta")


def today():
    return datetime.now(JAKARTA).date()


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def text_value(data, key, label, limit, errors, required=False):
    value = data.get(key)
    if value is None and not required:
        return None
    if not isinstance(value, str):
        errors[key] = f"{label} wajib berupa teks."
        return None
    value = value.strip()
    if required and not value:
        errors[key] = f"{label} wajib diisi."
    elif len(value) > limit:
        errors[key] = f"{label} maksimal {limit} karakter."
    return value or None


def validate_task(data, partial=False):
    cleaned, errors = {}, {}
    allowed = {"title", "description", "due_date", "priority", "officer_id"}
    if partial:
        allowed.add("status")
    unknown = set(data) - allowed
    if unknown:
        errors["payload"] = "Field tidak dikenal: " + ", ".join(sorted(unknown))
    if partial and not data:
        errors["payload"] = "Kirim setidaknya satu field untuk diperbarui."
    for key, label, limit, required in (
        ("title", "Judul", 120, True), ("description", "Deskripsi", 1000, False)
    ):
        if not partial or key in data:
            cleaned[key] = text_value(data, key, label, limit, errors, required)
    if not partial or "due_date" in data:
        value = data.get("due_date")
        try:
            if not isinstance(value, str) or len(value) != 10:
                raise ValueError
            cleaned["due_date"] = date.fromisoformat(value)
            if cleaned["due_date"].isoformat() != value:
                raise ValueError
        except ValueError:
            errors["due_date"] = "Tenggat wajib berupa tanggal valid (YYYY-MM-DD)."
    for key, options, default, label in (
        ("priority", PRIORITIES, "medium", "Prioritas"),
        ("status", STATUSES, "pending", "Status"),
    ):
        if key == "status" and not partial:
            cleaned[key] = default
        elif not partial or key in data:
            value = data.get(key, default)
            if not isinstance(value, str) or value not in options:
                errors[key] = f"{label} tidak valid."
            else:
                cleaned[key] = value
    if not partial or "officer_id" in data:
        value = data.get("officer_id")
        if value is None:
            cleaned["officer_id"] = None
        elif isinstance(value, int) and not isinstance(value, bool) and value > 0:
            cleaned["officer_id"] = value
        else:
            errors["officer_id"] = "Petugas harus berupa ID bilangan bulat positif atau null."
    return cleaned, errors


def validate_officer(data):
    errors = {}
    cleaned = {
        "name": text_value(data, "name", "Nama", 100, errors, True),
        "position": text_value(data, "position", "Jabatan", 100, errors),
    }
    return cleaned, errors


def parse_filters(args):
    filters = {
        "view": args.get("view", "active"),
        "status": args.get("status", ""),
        "due": args.get("due", "all"),
        "officer_id": args.get("officer_id", ""),
        "q": args.get("q", "").strip(),
    }
    if filters["view"] not in VIEWS or filters["due"] not in DUE_FILTERS:
        raise ValueError("Filter halaman atau tenggat tidak valid.")
    status = filters["status"]
    if status and status not in STATUSES:
        raise ValueError("Filter status tidak valid.")
    if filters["view"] == "active" and status == "done":
        raise ValueError("Gunakan halaman Selesai untuk tugas yang selesai.")
    if filters["view"] == "completed" and status not in ("", "done"):
        raise ValueError("Halaman Selesai hanya memuat status selesai.")
    if filters["due"] == "overdue" and filters["view"] != "active":
        raise ValueError("Filter Terlambat tersedia pada Tugas Aktif.")
    officer = filters["officer_id"]
    if officer not in ("", "none") and (not officer.isascii() or not officer.isdigit() or int(officer) < 1):
        raise ValueError("Filter petugas tidak valid.")
    if len(filters["q"]) > 120:
        raise ValueError("Pencarian maksimal 120 karakter.")
    return filters
