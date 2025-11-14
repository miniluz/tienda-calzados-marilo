import os
from typing import NamedTuple

from dotenv import load_dotenv

load_dotenv()


class EnvConfig(NamedTuple):
    DJANGO_DEBUG: bool
    DJANGO_SECRET_KEY: str
    ALLOWED_HOSTS: list[str]
    ADMIN_PASSWORD: str
    USE_SQLITE: bool
    POSTGRES_HOST: str
    POSTGRES_PORT: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    TAX_RATE: float
    DELIVERY_COST: float
    CHECKOUT_FORM_WINDOW_MINUTES: int
    PAYMENT_WINDOW_MINUTES: int
    CLEANUP_CRON_MINUTES: int

    def get_order_reservation_minutes(self) -> int:
        """
        Calculate total order reservation time.
        Formula: CHECKOUT_FORM_WINDOW_MINUTES + PAYMENT_WINDOW_MINUTES + 5 (buffer)
        Default: 10 + 5 + 5 = 20 minutes
        """
        return self.CHECKOUT_FORM_WINDOW_MINUTES + self.PAYMENT_WINDOW_MINUTES + 5


envConfig: EnvConfig | None = None


def getFromEnv(name: str, optional=False) -> str:
    var = os.getenv(name)

    if not optional and var is None:
        raise ValueError(f"The environment variable `${name}` is empty.")

    return var if var is not None else ""


def getBoolFromEnv(name: str) -> bool:
    return getFromEnv(name, True).strip() != ""


def getListFromEnv(name: str) -> list[str]:
    return getFromEnv(name, True).split(",")


def getFloatFromEnv(name: str, default: float | None = None) -> float:
    value = getFromEnv(name, default is not None)
    if not value and default is not None:
        return default
    try:
        return float(value)
    except ValueError:
        if default is not None:
            return default
        raise ValueError(f"The environment variable `${name}` must be a valid float.")


def getIntFromEnv(name: str, default: int | None = None) -> int:
    value = getFromEnv(name, default is not None)
    if not value and default is not None:
        return default
    try:
        return int(value)
    except ValueError:
        if default is not None:
            return default
        raise ValueError(f"The environment variable `${name}` must be a valid integer.")


def getEnvConfig() -> EnvConfig:
    global envConfig

    if envConfig is not None:
        return envConfig

    use_sqlite = getBoolFromEnv("USE_SQLITE")

    envConfig = EnvConfig(
        DJANGO_DEBUG=getBoolFromEnv("DJANGO_DEBUG"),
        DJANGO_SECRET_KEY=getFromEnv("DJANGO_SECRET_KEY"),
        ALLOWED_HOSTS=getListFromEnv("ALLOWED_HOSTS"),
        ADMIN_PASSWORD=getFromEnv("ADMIN_PASSWORD"),
        USE_SQLITE=getBoolFromEnv("USE_SQLITE"),
        POSTGRES_HOST=getFromEnv("POSTGRES_HOST", use_sqlite),
        POSTGRES_PORT=getFromEnv("POSTGRES_PORT", use_sqlite),
        POSTGRES_USER=getFromEnv("POSTGRES_USER", use_sqlite),
        POSTGRES_PASSWORD=getFromEnv("POSTGRES_PASSWORD", use_sqlite),
        POSTGRES_DB=getFromEnv("POSTGRES_DB", use_sqlite),
        TAX_RATE=getFloatFromEnv("TAX_RATE", 21.0),
        DELIVERY_COST=getFloatFromEnv("DELIVERY_COST", 5.0),
        CHECKOUT_FORM_WINDOW_MINUTES=getIntFromEnv("CHECKOUT_FORM_WINDOW_MINUTES", 10),
        PAYMENT_WINDOW_MINUTES=getIntFromEnv("PAYMENT_WINDOW_MINUTES", 5),
        CLEANUP_CRON_MINUTES=getIntFromEnv("CLEANUP_CRON_MINUTES", 5),
    )

    return envConfig
