from inventory.presentation.schemas import InventoryItemResponse
from inventory.wiring import build_fishing_service
from world.application.service import WorldService
from world.infrastructure.map_loader import load_geometry
from world.infrastructure.repository import WorldRepository


def build_world_service(session):
    return WorldService(
        WorldRepository(session),
        load_geometry,
        build_fishing_service(session),
        lambda item: InventoryItemResponse.from_info(item).model_dump(mode="json"),
    )
