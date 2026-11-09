"""기존 스프라이트 키와 업로드 이미지의 저장/조회 규칙."""
import io
import os
from pathlib import Path
import re
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

PROJECT_DIR = Path(__file__).resolve().parents[2]
SPRITE_DIR = PROJECT_DIR / 'src' / 'static' / 'sprites'
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_IMAGE_SIDE = 2048
UPLOAD_KEY = re.compile(r'upload_[0-9a-f]{32}')


def image_directory() -> Path:
    configured = Path(os.environ.get('ITEM_IMAGE_DIR', '.local/item-images'))
    return configured if configured.is_absolute() else PROJECT_DIR / configured


def image_url(icon: str) -> str | None:
    if re.fullmatch(r'[a-z0-9_]{1,50}', icon):
        return f'/static/sprites/item_{icon}.png'
    return None


def list_images() -> list[dict[str, str]]:
    result = [{'icon': path.stem.removeprefix('item_'), 'url': image_url(path.stem.removeprefix('item_')), 'source': 'bundled'}
              for path in sorted(SPRITE_DIR.glob('item_*.png'))]
    directory = image_directory()
    if directory.exists():
        result.extend({'icon': path.stem, 'url': image_url(path.stem), 'source': 'uploaded'}
                      for path in sorted(directory.glob('upload_*.png')) if UPLOAD_KEY.fullmatch(path.stem))
    return result


def save_image(data: bytes) -> dict[str, str | int]:
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise ValueError('이미지는 2MB 이하의 파일을 선택해 주세요.')
    try:
        with Image.open(io.BytesIO(data), formats=['PNG', 'JPEG', 'WEBP']) as original:
            if max(original.size) > MAX_IMAGE_SIDE or min(original.size) < 1:
                raise ValueError('이미지 가로와 세로는 각각 2048px 이하여야 합니다.')
            if getattr(original, 'n_frames', 1) != 1:
                raise ValueError('움직이는 이미지 대신 정지 이미지를 선택해 주세요.')
            original.load()
            # 새 이미지에 픽셀만 복사해 원본 메타데이터를 저장하지 않는다.
            clean = Image.new('RGBA', original.size)
            clean.paste(original.convert('RGBA'))
            output = io.BytesIO()
            clean.save(output, format='PNG')
            width, height = clean.size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('읽을 수 있는 PNG, JPG 또는 WebP 이미지를 선택해 주세요.') from exc
    icon = 'upload_' + uuid4().hex
    directory = image_directory()
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / f'{icon}.png').open('xb') as target:
        target.write(output.getvalue())
    return {'icon': icon, 'url': image_url(icon), 'width': width, 'height': height}
