"""Standardizes street names, so the same street is grouped together."""

# The data spells street types inconsistently, e.g. "PARK AV" and "PARK AVENUE".
STREET_TYPE_ABBREVIATIONS = {
    "AVENUE": "AV",
    "AVE": "AV",
    "STREET": "ST",
    "BOULEVARD": "BLVD",
    "BL": "BLVD",
    "ROAD": "RD",
    "PARKWAY": "PKWY",
    "PLACE": "PL",
    "DRIVE": "DR",
}


def normalize_street(street: str | None) -> str:
    words = (street or "").upper().split()
    if words:
        words[-1] = STREET_TYPE_ABBREVIATIONS.get(words[-1], words[-1])
    return " ".join(words)
