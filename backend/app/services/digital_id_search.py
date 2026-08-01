from typing import Dict, List, Optional, Tuple


def build_identity_search_clause(
    user_id_columns: List[str],
    like: str,
    fields: Optional[List[str]] = None,
) -> Tuple[str, Dict[str, str]]:
    """Build an SQL OR clause matching any digital_identities row for the given user-id columns.

    Used to extend transaction/search filters so that sub-distributors, clusters and
    operators can also be matched by their digital_id / broadband_id (any identity row,
    including additional digital IDs).
    """
    fields = fields or ["digital_id", "broadband_id"]
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
