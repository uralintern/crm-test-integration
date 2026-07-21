from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    APP_HOST: str = 'localhost'
    APP_PORT: int = 8000
    
    DB_USER: str = 'user'
    DB_PASSWORD: str = '1111'
    DB_NAME: str = 'internships'
    DB_HOST: str = 'localhost'
    DB_PORT: str = '5432'

    @property
    def db_url(self) -> str:
        return f'postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}'

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore'
    )


config = Config()
