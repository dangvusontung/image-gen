import uuid
from pathlib import Path

from app.config import ASSETS_DIR


class LocalStorage:
    def __init__(self, base_path: Path = ASSETS_DIR):
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve(self, relative_path: str) -> Path:
        path = (self.base_path / relative_path).resolve()
        if not path.is_relative_to(self.base_path):
            raise ValueError("Path escapes storage root")
        return path

    def save(self, data: bytes, project_id: str, ext: str) -> str:
        """Store bytes under a server-generated name; returns path relative to storage root."""
        relative = f"{project_id}/{uuid.uuid4()}.{ext}"
        path = self._resolve(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return relative

    def path_for(self, relative_path: str) -> Path:
        path = self._resolve(relative_path)
        if not path.is_file():
            raise FileNotFoundError(relative_path)
        return path

    def delete(self, relative_path: str) -> None:
        self._resolve(relative_path).unlink(missing_ok=True)

    def delete_project_dir(self, project_id: str) -> None:
        directory = self._resolve(project_id)
        if directory.is_dir():
            for f in directory.iterdir():
                f.unlink(missing_ok=True)
            directory.rmdir()
