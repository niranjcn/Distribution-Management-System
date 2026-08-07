from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict
import pytest


_SUBMODULES_WITH_DEVICE = ["stats", "analytics", "view_as"]
_SUBMODULES_WITH_DISTRIBUTION = ["stats", "analytics"]
_SUBMODULES_WITH_DEFECT = ["stats", "analytics"]
_SUBMODULES_WITH_RETURN = ["stats", "analytics"]
_SUBMODULES_WITH_USER = ["stats", "analytics"]
_SUBMODULES_WITH_LOG_API = ["activities"]


def _patch_submodules_value(modules: list, attr: str, value):
    patchers = []
    for mod in modules:
        p = patch(f"app.services.dashboard_service.{mod}.{attr}", value)
        p.start()
        patchers.append(p)
    return patchers


@pytest.fixture
def mock_services():
    """Patches all service dependencies in the dashboard_service submodules that use them."""
    _SERVICE_SPECS = [
        ("device_service", _SUBMODULES_WITH_DEVICE),
        ("distribution_service", _SUBMODULES_WITH_DISTRIBUTION),
        ("defect_service", _SUBMODULES_WITH_DEFECT),
        ("return_service", _SUBMODULES_WITH_RETURN),
        ("user_service", _SUBMODULES_WITH_USER),
    ]

    all_patchers = []
    mock_map = {}

    for svc_name, submodules in _SERVICE_SPECS:
        mock_obj = MagicMock(spec=True)
        mock_map[svc_name] = mock_obj
        for mod in submodules:
            p = patch(f"app.services.dashboard_service.{mod}.{svc_name}", new=mock_obj)
            p.start()
            all_patchers.append(p)

    log_api_mock = AsyncMock()
    for mod in _SUBMODULES_WITH_LOG_API:
        p = patch(f"app.services.dashboard_service.{mod}.log_api_activity", new=log_api_mock)
        p.start()
        all_patchers.append(p)
    mock_map["log_api_activity"] = log_api_mock

    yield mock_map
    for p in all_patchers:
        p.stop()


@pytest.fixture
def super_admin_user() -> Dict[str, Any]:
    return {"_id": "1", "id": "1", "role": "super_admin", "name": "Admin", "email": "admin@test.com"}


@pytest.fixture
def manager_user() -> Dict[str, Any]:
    return {"_id": "2", "id": "2", "role": "manager", "name": "Manager", "email": "manager@test.com"}


@pytest.fixture
def pdic_staff_user() -> Dict[str, Any]:
    return {"_id": "3", "id": "3", "role": "pdic_staff", "name": "Staff", "email": "staff@test.com"}


@pytest.fixture
def sub_distributor_user() -> Dict[str, Any]:
    return {"_id": "10", "id": "10", "role": "sub_distributor", "name": "SubDist", "email": "subdist@test.com", "parent_id": "1"}


@pytest.fixture
def sub_distribution_manager_user() -> Dict[str, Any]:
    return {"_id": "20", "id": "20", "role": "sub_distribution_manager", "name": "SDM", "email": "sdm@test.com", "parent_id": "10"}


@pytest.fixture
def cluster_user() -> Dict[str, Any]:
    return {"_id": "30", "id": "30", "role": "cluster", "name": "Cluster", "email": "cluster@test.com", "parent_id": "20"}


@pytest.fixture
def operator_user() -> Dict[str, Any]:
    return {"_id": "40", "id": "40", "role": "operator", "name": "Operator", "email": "op@test.com", "parent_id": "30", "status": "active"}
