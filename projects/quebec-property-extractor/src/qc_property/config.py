from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


class ProjectSettings(BaseModel):
    municipality_name: str
    source_year: int


class SourceSettings(BaseModel):
    dataset: str
    municipality_index_url: str
    timeout_seconds: int = 60
    max_retries: int = 3


class ParserSettings(BaseModel):
    mapping_file: Path
    validate_xsd: bool = False
    detect_unknown_tags: bool = True


class OutputSettings(BaseModel):
    directory: Path
    excel: bool = True
    csv: bool = True
    manifest: bool = True


class LoggingSettings(BaseModel):
    level: str = "INFO"
    file: Optional[Path] = None


class AppSettings(BaseModel):
    project: ProjectSettings
    source: SourceSettings
    parser: ParserSettings
    output: OutputSettings
    logging: LoggingSettings = LoggingSettings()

    @field_validator("parser", mode="before")
    @classmethod
    def resolve_mapping_path(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if "mapping_file" in v:
            v["mapping_file"] = Path(v["mapping_file"])
        return v

    @field_validator("output", mode="before")
    @classmethod
    def resolve_output_path(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if "directory" in v:
            v["directory"] = Path(v["directory"])
        return v


class EnvSettings(BaseSettings):
    log_level: Optional[str] = None
    source_year: Optional[int] = None
    municipality_name: Optional[str] = None
    output_dir: Optional[Path] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def load_settings(config_path: Path = Path("config/settings.yaml")) -> AppSettings:
    """Load application settings from YAML, applying env overrides."""
    with open(config_path) as f:
        data = yaml.safe_load(f)

    env = EnvSettings()
    if env.source_year:
        data["project"]["source_year"] = env.source_year
    if env.municipality_name:
        data["project"]["municipality_name"] = env.municipality_name
    if env.output_dir:
        data["output"]["directory"] = env.output_dir
    if env.log_level:
        data.setdefault("logging", {})["level"] = env.log_level

    return AppSettings(**data)