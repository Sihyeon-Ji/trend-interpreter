from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    model_provider: Literal["mock", "gemini", "vllm"] = "mock"
    gcp_project_id: str = "stunning-crane-508614-c1"
    google_cloud_location: str = "global"
    gemini_model: str = "gemini-3.5-flash"
    model_timeout_seconds: float = Field(default=30, gt=0, le=120)
    model_max_attempts: int = Field(default=2, ge=1, le=3)
    input_price_per_million: float = Field(default=0, ge=0)
    output_price_per_million: float = Field(default=0, ge=0)
    demo_api_key: str = ""
    vllm_base_url: str = "http://127.0.0.1:8001/v1"
    vllm_model: str = "google/gemma-4-E2B-it"
    vllm_api_key: str = "local-development-only"
    web_dist: str = "apps/web/dist"
    database_lab_enabled: bool = False
    workflow_lab_enabled: bool = False
    database_host: str = "db"
    database_name: str = "builder_cup"
    database_password_file: str = "/run/db-app/password"
    database_admin_password_file: str = "/run/db-admin/password"
