"""클라이언트와 같은 Tiled 파일에서 서버 충돌/물 정보를 만든다."""

import json
from functools import lru_cache
from pathlib import Path

from PIL import Image

from world.domain.rules import MAP_NAMES, MapGeometry, WorldError

ASSETS = Path(__file__).resolve().parents[2] / "static"


@lru_cache(maxsize=3)
def load_geometry(name: str) -> MapGeometry:
    if name not in MAP_NAMES:
        raise WorldError("INVALID_MAP", "지원하지 않는 맵입니다.", 422)

    path = ASSETS / "maps" / f"{name}.tmj"
    data = json.loads(path.read_text(encoding="utf-8"))
    width, height = data["width"] * 16, data["height"] * 16
    blocked = bytearray(width * height)
    water = set()
    tilesets = []

    for tileset in data["tilesets"]:
        base = path.parent
        if "source" in tileset:
            source = (base / tileset["source"]).resolve()
            source.relative_to(ASSETS.resolve())
            tileset = {
                **json.loads(source.read_text(encoding="utf-8")),
                "firstgid": tileset["firstgid"],
            }
            base = source.parent
        image_path = (base / tileset["image"]).resolve()
        image_path.relative_to(ASSETS.resolve())
        with Image.open(image_path) as image:
            pixels = image.convert("RGBA").copy()
        properties = {
            tile["id"]: {p["name"]: p["value"] for p in tile.get("properties", [])}
            for tile in tileset.get("tiles", [])
        }
        tilesets.append((tileset, pixels, properties))
    tilesets.sort(key=lambda entry: entry[0]["firstgid"], reverse=True)

    def stamp(gid, left, top):
        if not gid:
            return
        if gid & 0xE0000000:
            raise ValueError(
                "Transformed tiles are not supported by the collision contract"
            )
        definition, image, properties = next(
            entry for entry in tilesets if gid >= entry[0]["firstgid"]
        )
        tile_id = gid - definition["firstgid"]
        props = properties.get(tile_id, {})
        if not (props.get("solid") or props.get("water")):
            return
        margin, spacing = definition.get("margin", 0), definition.get("spacing", 0)
        columns = (image.width - 2 * margin + spacing) // (16 + spacing)
        source_x = margin + tile_id % columns * (16 + spacing)
        source_y = margin + tile_id // columns * (16 + spacing)
        for y in range(16):
            for x in range(16):
                mx, my = int(left + x), int(top + y)
                if 0 <= mx < width and 0 <= my < height:
                    if props.get("water"):
                        water.add((mx // 16, my // 16))
                    if (
                        props.get("water")
                        or image.getpixel((source_x + x, source_y + y))[3] >= 128
                    ):
                        blocked[my * width + mx] = 1

    spawn = None

    def walk(layers):
        nonlocal spawn
        for layer in layers:
            if layer.get("visible") is False:
                continue
            if layer["type"] == "group":
                walk(layer["layers"])
            elif layer["type"] == "tilelayer":
                for index, gid in enumerate(layer["data"]):
                    stamp(gid, index % data["width"] * 16, index // data["width"] * 16)
            elif layer["type"] == "objectgroup":
                for obj in layer["objects"]:
                    if obj.get("visible") is False:
                        continue
                    if obj.get("name") == "spawn":
                        spawn = (obj["x"] - 8, obj["y"] - 13)
                    if obj.get("gid"):
                        stamp(obj["gid"], obj["x"], obj["y"] - obj["height"])

    walk(data["layers"])
    geometry = MapGeometry(width, height, blocked, water, spawn or (0, 0))
    if not spawn or not geometry.can_stand(*spawn):
        raise ValueError(f"Invalid spawn in {name}")
    return geometry
