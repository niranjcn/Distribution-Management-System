from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func, or_, and_, update, delete

from app.database_sqlalchemy import async_session_factory
from app.db_models.operator import Operator
from app.db_models.device import Device
from app.models.operator import OperatorCreate, OperatorUpdate, OperatorStatus
from app.utils.helpers import get_pagination, generate_operator_id


async def get_operators(
    page: int = 1,
    page_size: int = 20,
    assigned_to: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None
) -> Dict[str, Any]:
    """Get all operators with pagination and filters"""
    async with async_session_factory() as session:
        conditions = []

        if assigned_to:
            conditions.append(Operator.assigned_to == assigned_to)
        if status:
            conditions.append(Operator.status == status)
        if search:
            like = f"%{search}%"
            conditions.append(
                or_(
                    Operator.name.like(like),
                    Operator.phone.like(like),
                    Operator.email.like(like),
                    Operator.area.like(like),
                )
            )

        where = and_(*conditions) if conditions else True

        count_q = select(func.count()).select_from(Operator).where(where)
        total = (await session.execute(count_q)).scalar()

        offset = (page - 1) * page_size
        q = (
            select(Operator)
            .where(where)
            .order_by(Operator.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = (await session.execute(q)).scalars().all()

        return {
            "data": [r.to_dict() for r in rows],
            "pagination": get_pagination(page, page_size, total),
        }


async def get_operator_by_id(operator_id: str) -> Optional[Dict[str, Any]]:
    """Get operator by ID"""
    async with async_session_factory() as session:
        inst = await session.get(Operator, int(operator_id))
        return inst.to_dict() if inst else None


async def create_operator(operator_data: OperatorCreate, created_by: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new operator"""
    now = datetime.now().replace(tzinfo=None)
    async with async_session_factory() as session:
        op = Operator(
            operator_id=generate_operator_id(),
            name=operator_data.name,
            phone=operator_data.phone,
            email=operator_data.email,
            address=operator_data.address,
            area=operator_data.area,
            city=operator_data.city,
            assigned_to=int(created_by["_id"]),
            assigned_to_name=created_by["name"],
            status=OperatorStatus.ACTIVE.value,
            device_count=0,
            connection_type=operator_data.connection_type.value if operator_data.connection_type else None,
            created_at=now,
            updated_at=now,
        )
        session.add(op)
        await session.flush()
        await session.commit()
        return op.to_dict()


async def update_operator(operator_id: str, operator_data: OperatorUpdate) -> Optional[Dict[str, Any]]:
    """Update operator"""
    update_dict = {k: v for k, v in operator_data.model_dump().items() if v is not None}

    if not update_dict:
        return await get_operator_by_id(operator_id)

    if "status" in update_dict:
        update_dict["status"] = update_dict["status"].value
    if "connection_type" in update_dict:
        update_dict["connection_type"] = update_dict["connection_type"].value

    update_dict["updated_at"] = datetime.now().replace(tzinfo=None)

    async with async_session_factory() as session:
        inst = await session.get(Operator, int(operator_id))
        if not inst:
            return None

        for k, v in update_dict.items():
            setattr(inst, k, v)

        await session.commit()
        return inst.to_dict()


async def delete_operator(operator_id: str) -> bool:
    """Delete operator"""
    async with async_session_factory() as session:
        inst = await session.get(Operator, int(operator_id))
        if not inst:
            return False
        await session.delete(inst)
        await session.commit()
        return True


async def get_operator_devices(operator_id: str) -> List[Dict[str, Any]]:
    """Get devices assigned to an operator"""
    async with async_session_factory() as session:
        q = select(Device).where(Device.current_holder_id == operator_id)
        rows = (await session.execute(q)).scalars().all()
        return [r.to_dict() for r in rows]


async def update_operator_device_count(operator_id: str) -> None:
    """Update operator's device count"""
    now = datetime.now().replace(tzinfo=None)
    async with async_session_factory() as session:
        count_q = (
            select(func.count())
            .select_from(Device)
            .where(Device.current_holder_id == operator_id)
        )
        count = (await session.execute(count_q)).scalar()

        inst = await session.get(Operator, int(operator_id))
        if inst:
            inst.device_count = count
            inst.updated_at = now
            await session.commit()


async def get_operator_stats(assigned_to: Optional[int] = None) -> Dict[str, int]:
    """Get operator statistics"""
    async with async_session_factory() as session:
        q = select(Operator.status, func.count().label("total"))
        if assigned_to:
            q = q.where(Operator.assigned_to == assigned_to)
        q = q.group_by(Operator.status)

        rows = (await session.execute(q)).all()
        by_status = {str(row.status): int(row.total) for row in rows}

        return {
            "total": by_status.get("active", 0) + by_status.get("inactive", 0),
            "active": by_status.get("active", 0),
            "inactive": by_status.get("inactive", 0),
        }
