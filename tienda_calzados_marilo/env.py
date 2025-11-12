import os
from typing import NamedTuple

from dotenv import load_dotenv

load_dotenv()


class EnvConfig(NamedTuple):
    DJANGO_DEBUG: bool
    DJANGO_SECRET_KEY: str
    ADMIN_PASSWORD: str
    USE_SQLITE: bool
    POSTGRES_HOST: str
    POSTGRES_PORT: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str


envConfig: EnvConfig | None = None


def getFromEnv(name: str, optional=False) -> str:
    var = os.getenv(name)

    if not optional and var is None:
        raise ValueError(f"The environment variable `${name}` is empty.")

    return var if var is not None else ""


def getBoolFromEnv(name: str) -> bool:
    return getFromEnv(name, True).strip() != ""


def getEnvConfig() -> EnvConfig:
    global envConfig

    if envConfig is not None:
        return envConfig

    use_sqlite = getBoolFromEnv("USE_SQLITE")

    envConfig = EnvConfig(
        DJANGO_DEBUG=getBoolFromEnv("DJANGO_DEBUG"),
        DJANGO_SECRET_KEY=getFromEnv("DJANGO_SECRET_KEY"),
        ADMIN_PASSWORD=getFromEnv("ADMIN_PASSWORD"),
        USE_SQLITE=getBoolFromEnv("USE_SQLITE"),
        POSTGRES_HOST=getFromEnv("POSTGRES_HOST", use_sqlite),
        POSTGRES_PORT=getFromEnv("POSTGRES_PORT", use_sqlite),
        POSTGRES_USER=getFromEnv("POSTGRES_USER", use_sqlite),
        POSTGRES_PASSWORD=getFromEnv("POSTGRES_PASSWORD", use_sqlite),
        POSTGRES_DB=getFromEnv("POSTGRES_DB", use_sqlite),
    )

    return envConfig
