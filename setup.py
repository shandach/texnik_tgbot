from setuptools import find_packages, setup

setup(
    name="texnik-tgbot",
    version="0.3.0",
    description="Telegram bot backend flows for equipment requests",
    python_requires=">=3.10",
    packages=find_packages(include=["app", "app.*"]),
    install_requires=[],
    extras_require={
        "prod": [
            "fastapi>=0.115.0",
            "uvicorn>=0.30.0",
            "sqlalchemy>=2.0.0",
            "psycopg[binary]>=3.1.0",
        ]
    },
)
