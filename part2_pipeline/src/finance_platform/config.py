"""Read from the environment variables and cache so that every module reads settings from here
rather than querying the environment variables directly.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    domain: str = "finance"
    bucket_prefix: str = ""
    aws_region: str = Field(default="ap-southeast-2", alias="AWS_DEFAULT_REGION")

    # Set to the LocalStack gateway for local. Empty string means using real AWS.
    localstack_endpoint: str = "http://localhost:4566"

    # These are randomly chosen - 200 defect free rows, 5 defective rows will be added.
    seed_row_count: int = 200
    random_seed: int = 42

    @property
    def landing_bucket(self) -> str:
        return f"{self.bucket_prefix}{self.domain}-data-landing"

    @property
    def curated_bucket(self) -> str:
        return f"{self.bucket_prefix}{self.domain}-data-curated"

    def curated_prefix(self) -> str:
        return f"curated/{self.domain}/daily_category_spend"


@lru_cache
def get_settings() -> Settings:
    return Settings()
