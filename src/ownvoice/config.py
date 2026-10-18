from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OWNVOICE_")
    data_dir: Path = Path(".data")
    device: str = "auto"
    model: str = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
    max_speed: float = Field(default=1.15, ge=1.0, le=1.15, allow_inf_nan=False)

    def prepare(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for name in ("profiles", "jobs"):
            (self.data_dir / name).mkdir(exist_ok=True)
