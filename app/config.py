from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "mysql+pymysql://root:changeme@localhost:3306/laptops"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False

    auth_username: str = "admin"
    auth_password: str = ""
    session_secret: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
