import os
from typing import NamedTuple

from dotenv import load_dotenv

load_dotenv()


class EnvConfig(NamedTuple):
    DJANGO_DEBUG: bool
    DJANGO_SECRET_KEY: str
    POSTGRES_HOST: str
    POSTGRES_PORT: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str


envConfig: EnvConfig | None = None


def getFromEnv(name: str) -> str:
    var = os.getenv(name)

    if var == None:
        raise ValueError(f"The environment variable `${name}` is empty.")

    return var


def getBoolFromEnv(name: str) -> bool:
    return getFromEnv(name).strip() != ""


def getEnvConfig() -> EnvConfig:
    global envConfig

    if envConfig != None:
        return envConfig

    envConfig = EnvConfig(
        DJANGO_DEBUG=getBoolFromEnv("DJANGO_DEBUG"),
        DJANGO_SECRET_KEY=getFromEnv("DJANGO_SECRET_KEY"),
        POSTGRES_HOST=getFromEnv("POSTGRES_HOST"),
        POSTGRES_PORT=getFromEnv("POSTGRES_PORT"),
        POSTGRES_USER=getFromEnv("POSTGRES_USER"),
        POSTGRES_PASSWORD=getFromEnv("POSTGRES_PASSWORD"),
        POSTGRES_DB=getFromEnv("POSTGRES_DB"),
    )

    return envConfig
