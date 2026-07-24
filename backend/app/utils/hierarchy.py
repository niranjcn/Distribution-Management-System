from typing import Set


async def get_descendant_user_ids(db, root_user_id: str) -> Set[str]:
    """Return all descendant user IDs by walking parent_id using a single recursive CTE."""
    if not root_user_id or not str(root_user_id).isdigit():
        return set()

    cursor = await db.execute(
        """WITH RECURSIVE descendants AS (
            SELECT id FROM users WHERE parent_id = ?
            UNION ALL
            SELECT u.id FROM users u
            INNER JOIN descendants d ON u.parent_id = d.id
        )
        SELECT id FROM descendants""",
        (int(root_user_id),),
    )
    rows = await cursor.fetchall()
    return {str(row["id"]) for row in rows if row["id"]}
