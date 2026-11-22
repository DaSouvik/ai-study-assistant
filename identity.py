from collections.abc import Mapping


def google_owner_id(claims: Mapping[str, object]) -> str:
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("The Google identity does not include a valid subject.")
    return f"google:{subject}"
