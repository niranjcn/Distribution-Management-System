from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import HTTPException

from app.models.inventory import ExternalBulkDistributionCreate
from app.services import inventory_service


class _FakeMappings:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def first(self):
        return dict(self._rows[0]) if self._rows else None


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return _FakeMappings(self._rows)


class _FakeUpdateResult:
    def __init__(self, rowcount):
        self.rowcount = rowcount


ITEMS = [
    {"id": 1, "name": "Router A", "identifier_type": "MAC ID", "identifier": "AA:BB:CC:00:00:01",
     "device_type": "Router", "price": 100, "quantity": 10, "status": "active"},
    {"id": 2, "name": "STB B", "identifier_type": "IMEI", "identifier": "9999-0001",
     "device_type": "STB", "price": 50, "quantity": 0, "status": "active"},
    {"id": 3, "name": "Modem C", "identifier_type": "IMEI", "identifier": "9999-0002",
     "device_type": "Modem", "price": 30, "quantity": 5, "status": "inactive"},
    {"id": 4, "name": "Router D", "identifier_type": "NU ID", "identifier": "NU-0001",
     "device_type": "Router", "price": 80, "quantity": 2, "status": "active"},
]
ITEMS_BY_ID = {i["id"]: i for i in ITEMS}

USERS = [
    {"id": 10, "name": "SubDist A", "email": "a@test.com", "role": "sub_distributor", "status": "active"},
    {"id": 11, "name": "Operator B", "email": "b@test.com", "role": "operator", "status": "inactive"},
    {"id": 12, "name": "Operator C", "email": "c@test.com", "role": "operator", "status": "active"},
]
USERS_BY_ID = {u["id"]: u for u in USERS}


class _BulkSession:
    """AsyncSession double that responds to the queries issued by the bulk
    distribution services."""

    def __init__(self, items=ITEMS_BY_ID, users=USERS_BY_ID):
        self._items = {k: dict(v) for k, v in items.items()}
        self._users = users
        self.history_rows = []
        self.updates = []
        self.commits = 0

    async def commit(self):
        self.commits += 1

    async def execute(self, statement, params=None):
        sql = str(statement)
        params = params or {}

        if "FROM external_inventory_items" in sql and "identifier_type" in sql:
            pairs = []
            i = 0
            while f"t_{i}" in params and f"i_{i}" in params:
                pairs.append((params[f"t_{i}"], params[f"i_{i}"]))
                i += 1
            return _FakeResult([
                dict(v) for v in self._items.values()
                if (v.get("identifier_type"), v.get("identifier")) in pairs
            ])

        if "FROM external_inventory_items WHERE id IN" in sql:
            ids = set(params.values())
            return _FakeResult([dict(i) for i in self._items.values() if i["id"] in ids])

        if "FROM users WHERE id IN" in sql:
            ids = set(params.values())
            return _FakeResult([dict(u) for u in self._users.values() if u["id"] in ids])

        if "FROM users WHERE LOWER(email) IN" in sql:
            emails = {str(v).lower() for v in params.values()}
            return _FakeResult([dict(u) for u in self._users.values() if u["email"].lower() in emails])

        if "FROM users WHERE id = :user_id" in sql:
            return _FakeResult([dict(self._users[int(params["user_id"])])] if int(params["user_id"]) in self._users else [])

        if "UPDATE external_inventory_items" in sql:
            # Batched CASE decrement: params are did_0/dqty_0/... plus updated_at.
            decrements = {}
            i = 0
            while f"did_{i}" in params:
                decrements[int(params[f"did_{i}"])] = int(params[f"dqty_{i}"])
                i += 1
            for iid, qty in decrements.items():
                item = self._items.get(iid)
                if item:
                    item["quantity"] = int(item["quantity"]) - qty
                    self.updates.append({"item_id": iid, "qty": qty})
            return _FakeUpdateResult(len(decrements))

        if "INSERT INTO external_device_history" in sql:
            rows = params if isinstance(params, list) else [params]
            self.history_rows.extend(rows)
            return _FakeResult([])

        return _FakeResult([])


class _RaceSession(_BulkSession):
    """Simulates another transaction committing a stock change before the
    FOR UPDATE read, so the lock read sees a reduced quantity and validation
    rejects the request."""

    def __init__(self, raced_item_id, reduced_quantity):
        super().__init__()
        self._raced_item_id = raced_item_id
        self._reduced_quantity = reduced_quantity

    async def execute(self, statement, params=None):
        sql = str(statement)
        params = params or {}
        if "FROM external_inventory_items WHERE id IN" in sql:
            ids = set(params.values())
            rows = [dict(i) for i in self._items.values() if i["id"] in ids]
            for r in rows:
                if r["id"] == self._raced_item_id:
                    r["quantity"] = self._reduced_quantity
            return _FakeResult(rows)
        return await super().execute(statement, params)


def _patch_session(session):
    cm = MagicMock()
    cm.__aenter__.return_value = session
    cm.__aexit__.return_value = None
    session_factory = MagicMock(return_value=cm)
    patchers = [
        patch.object(inventory_service, "async_session_factory", session_factory),
        patch.object(inventory_service, "bump_cache_version", new=AsyncMock()),
        patch.object(inventory_service, "generate_external_distribution_id",
                     side_effect=lambda i=iter(range(1, 10000)): f"HIST-{next(i)}"),
        patch.object(inventory_service, "_notify_recipient", new=AsyncMock()),
        patch.object(inventory_service, "_notify_recipient_batch", new=AsyncMock()),
    ]
    for p in patchers:
        p.start()
    return patchers


class TestBulkDistribute:
    async def test_success_batches_items_and_history(self):
        session = _BulkSession()
        patchers = _patch_session(session)
        try:
            payload = ExternalBulkDistributionCreate(items=[
                {"item_id": 1, "to_user_id": 10, "quantity": 2},
                {"item_id": 4, "recipient_email": "C@test.com", "quantity": 1},
            ])
            result = await inventory_service.bulk_distribute(payload=payload, user={"id": 99, "name": "Mgr"})
            notify = inventory_service._notify_recipient_batch
        finally:
            for p in patchers:
                p.stop()

        assert result["created_count"] == 2
        assert result["error_count"] == 0
        assert len(session.updates) == 2
        assert [u["qty"] for u in session.updates] == [2, 1]
        # History inserted via executemany, one batch for both rows.
        assert len(session.history_rows) == 2
        assert all("history_id" in h and "remaining_quantity" in h for h in session.history_rows)
        # One aggregated notification per recipient (recipient 10 and 12).
        assert notify.await_count == 2
        recipients = sorted(int(call.args[0]["id"]) for call in notify.await_args_list)
        assert recipients == [10, 12]

    async def test_bad_items_reported_without_affecting_valid_ones(self):
        session = _BulkSession()
        patchers = _patch_session(session)
        try:
            payload = ExternalBulkDistributionCreate(items=[
                {"item_id": 1, "to_user_id": 10, "quantity": 2},
                {"item_id": 2, "to_user_id": 10, "quantity": 1},   # out of stock (0)
                {"item_id": 3, "to_user_id": 10, "quantity": 1},   # inactive
                {"item_id": 99, "to_user_id": 10, "quantity": 1},  # not found
                {"item_id": 1, "to_user_id": 11, "quantity": 1},   # recipient inactive
                {"item_id": 1, "to_user_id": 999, "quantity": 1},  # recipient missing
            ])
            result = await inventory_service.bulk_distribute(payload=payload, user={"id": 99, "name": "Mgr"})
        finally:
            for p in patchers:
                p.stop()

        assert result["created_count"] == 1
        assert result["error_count"] == 5
        messages = [e["error"] for e in result["errors"]]
        assert any("out of stock" in m for m in messages)
        assert any("not active" in m for m in messages)
        assert any("Item not found" in m for m in messages)
        assert any("Recipient not found" in m for m in messages)
        assert len(session.history_rows) == 1

    async def test_concurrent_stock_loss_is_rejected(self):
        # Another request takes stock before our FOR UPDATE read, so the lock
        # read sees item 1 with only 1 unit left and the request for 2 is
        # rejected during validation.
        session = _RaceSession(raced_item_id=1, reduced_quantity=1)
        patchers = _patch_session(session)
        try:
            payload = ExternalBulkDistributionCreate(items=[
                {"item_id": 1, "to_user_id": 10, "quantity": 2},
            ])
            result = await inventory_service.bulk_distribute(payload=payload, user={"id": 99, "name": "Mgr"})
        finally:
            for p in patchers:
                p.stop()

        assert result["created_count"] == 0
        assert result["error_count"] == 1
        assert "Cannot distribute more than the available quantity" in result["errors"][0]["error"]
        assert session.history_rows == []

    async def test_quantity_over_available_rejected_before_update(self):
        session = _BulkSession()
        patchers = _patch_session(session)
        try:
            payload = ExternalBulkDistributionCreate(items=[
                {"item_id": 4, "to_user_id": 10, "quantity": 999},
            ])
            result = await inventory_service.bulk_distribute(payload=payload, user={"id": 99, "name": "Mgr"})
        finally:
            for p in patchers:
                p.stop()

        assert result["created_count"] == 0
        assert result["error_count"] == 1
        assert "Cannot distribute more than the available quantity" in result["errors"][0]["error"]
        assert session.updates == []

    async def test_repeated_item_aggregated_into_one_decrement(self):
        session = _BulkSession()
        patchers = _patch_session(session)
        try:
            payload = ExternalBulkDistributionCreate(items=[
                {"item_id": 1, "to_user_id": 10, "quantity": 2},
                {"item_id": 1, "to_user_id": 10, "quantity": 3},
            ])
            result = await inventory_service.bulk_distribute(payload=payload, user={"id": 99, "name": "Mgr"})
        finally:
            for p in patchers:
                p.stop()

        assert result["created_count"] == 2
        assert result["error_count"] == 0
        # One batched decrement for the aggregated quantity, not one per entry.
        assert len(session.updates) == 1
        assert session.updates[0] == {"item_id": 1, "qty": 5}
        # History records the running previous/remaining quantities.
        assert [h["previous_quantity"] for h in session.history_rows] == [10, 8]
        assert [h["remaining_quantity"] for h in session.history_rows] == [8, 5]
        assert session._items[1]["quantity"] == 5


class TestBulkDistributeFromFile:
    def _rows(self):
        return [
            {"row": 2, "identifier_type": "MAC ID", "identifier": "AA:BB:CC:00:00:01", "quantity": "2", "notes": None},  # item 1 valid
            {"row": 3, "identifier_type": "NU ID", "identifier": "NU-0001", "quantity": "", "notes": "default qty"},  # item 4 valid
            {"row": 4, "identifier_type": "MAC ID", "identifier": "AA:BB:CC:00:00:01", "quantity": "1", "notes": None},  # duplicate pair
            {"row": 5, "identifier_type": "IMEI", "identifier": "", "quantity": "1", "notes": None},  # missing identifier
            {"row": 6, "identifier_type": "IMEI", "identifier": "9999-0001", "quantity": "1", "notes": None},  # out of stock
            {"row": 7, "identifier_type": "IMEI", "identifier": "9999-0002", "quantity": "3", "notes": None},  # inactive
        ]

    async def test_mixed_rows_report_once_and_distribute_valid(self):
        session = _BulkSession()
        patchers = _patch_session(session)
        try:
            result = await inventory_service.bulk_distribute_from_file(
                identifier_rows=self._rows(),
                to_user_id=10,
                user={"id": 99, "name": "Mgr"},
            )
            notify = inventory_service._notify_recipient_batch
        finally:
            for p in patchers:
                p.stop()

        assert result["created_count"] == 2
        assert result["error_count"] == 4
        messages = [e["error"] for e in result["errors"]]
        # Duplicate identifier pair is reported exactly once (no double reporting).
        assert messages.count("Duplicate identifier (MAC ID AA:BB:CC:00:00:01) in file") == 1
        assert any("Both identifier_type and identifier are required" in m for m in messages)
        assert any("out of stock" in m for m in messages)
        assert any("not active" in m for m in messages)
        assert len(session.history_rows) == 2
        assert len(session.updates) == 2
        # All created records go to one recipient -> a single aggregated notification.
        assert notify.await_count == 1
        assert len(notify.await_args.args[1]) == 2

    async def test_atomic_decrement_records_previous_and_remaining(self):
        session = _BulkSession()
        patchers = _patch_session(session)
        try:
            await inventory_service.bulk_distribute_from_file(
                identifier_rows=[{"row": 2, "identifier_type": "MAC ID", "identifier": "AA:BB:CC:00:00:01", "quantity": "2", "notes": None}],
                to_user_id=10,
                user={"id": 99, "name": "Mgr"},
            )
        finally:
            for p in patchers:
                p.stop()

        assert len(session.updates) == 1
        assert session.updates[0]["qty"] == 2
        assert session.history_rows[0]["previous_quantity"] == 10
        assert session.history_rows[0]["remaining_quantity"] == 8

    async def test_inactive_recipient_rejected(self):
        session = _BulkSession()
        patchers = _patch_session(session)
        try:
            with pytest.raises(HTTPException) as exc_info:
                await inventory_service.bulk_distribute_from_file(
                    identifier_rows=[{"row": 2, "id": "1", "quantity": "1", "notes": None}],
                    to_user_id=11,
                    user={"id": 99, "name": "Mgr"},
                )
        finally:
            for p in patchers:
                p.stop()

        assert exc_info.value.status_code == 400
        assert "not active" in exc_info.value.detail
