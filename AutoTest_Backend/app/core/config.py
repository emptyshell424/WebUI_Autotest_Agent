from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    DEEPSEEK_API_KEY: str
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    MODEL_NAME: str = "deepseek-chat"

    class Config:

        env_file = ".env"

settings = Settings()
