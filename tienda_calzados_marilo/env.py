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
    # Email configuration
    USE_CONSOLE_MAIL: bool
    WEBSITE_URL: str
    EMAIL_HOST: str
    EMAIL_PORT: int
    EMAIL_HOST_USER: str
    EMAIL_HOST_PASSWORD: str
    EMAIL_USE_TLS: bool
    EMAIL_USE_SSL: bool

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
    use_console_mail = getBoolFromEnv("USE_CONSOLE_MAIL")

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
        # Email configuration
        USE_CONSOLE_MAIL=use_console_mail,
        WEBSITE_URL=getFromEnv("WEBSITE_URL", optional=True) or "http://localhost:8000",
        EMAIL_HOST=getFromEnv("EMAIL_HOST", use_console_mail),
        EMAIL_PORT=getIntFromEnv("EMAIL_PORT", 25) if not use_console_mail else 25,
        EMAIL_HOST_USER=getFromEnv("EMAIL_HOST_USER", use_console_mail),
        EMAIL_HOST_PASSWORD=getFromEnv("EMAIL_HOST_PASSWORD", use_console_mail),
        EMAIL_USE_TLS=getBoolFromEnv("EMAIL_USE_TLS"),
        EMAIL_USE_SSL=getBoolFromEnv("EMAIL_USE_SSL"),
    )

    return envConfig
