import re
from typing import Dict, List, Optional, Tuple


#: Column names allowed to be interpolated into the search SQL. Anything outside
#: this set is rejected, so attacker-controlled values can never reach the query.
_ALLOWED_FIELDS = ("digital_id", "broadband_id")

#: Matches a bare column name or a ``table.column`` reference built only from
#: SQL identifiers (letters, digits, underscores). No spaces, quotes or
#: parentheses can pass, so nothing else can be smuggled into the query.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


def build_identity_search_clause(
    user_id_columns: List[str],
    like: str,
    fields: Optional[List[str]] = None,
) -> Tuple[str, Dict[str, str]]:
    """Build an SQL OR clause matching any digital_identities row for the given user-id columns.

    Used to extend transaction/search filters so that sub-distributors, clusters and
    operators can also be matched by their digital_id / broadband_id (any identity row,
    including additional digital IDs).

    ``user_id_columns`` and ``fields`` are interpolated directly into SQL, so both are
    strictly validated here (whitelist + identifier pattern) to guarantee no untrusted
    input can ever be injected into the query string.
    """
    fields = fields or ["digital_id", "broadband_id"]

    unknown_fields = [f for f in fields if f not in _ALLOWED_FIELDS]
    if unknown_fields:
        raise ValueError(f"Unsupported identity search field(s): {unknown_fields}")

    invalid_columns = [c for c in user_id_columns if not _IDENTIFIER_RE.match(c)]
    if invalid_columns:
        raise ValueError(f"Invalid user-id column reference(s): {invalid_columns}")

    fragments = []
    params: Dict[str, str] = {}

    for idx, col in enumerate(user_id_columns):
        for field in fields:
            pname = f"idm_{idx}_{field}"
            fragments.append(
                f"EXISTS (SELECT 1 FROM digital_identities di{idx}_{field} "
                f"WHERE di{idx}_{field}.user_id = {col} AND di{idx}_{field}.{field} LIKE :{pname})"
            )
            params[pname] = like

    return "(" + " OR ".join(fragments) + ")", params
