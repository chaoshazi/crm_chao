'''运行时配置：全部来自环境变量或 .env，统一前缀 CRM_。'''

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

STORAGE_CHOICES = ('sqlite', 'postgres')


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in (value or '').split(',') if part.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_prefix='CRM_', extra='ignore')

    # ---- 应用 ----
    env: str = 'dev'
    log_level: str = 'INFO'
    tenant_id: str = 'default'

    # ---- 存储 ----
    storage: str = 'sqlite'
    sqlite_path: str = 'data/crm.sqlite3'
    database_url: str = 'postgresql+psycopg://crm:crm@localhost:5433/crm'
    auto_migrate: bool = True

    # ---- 安全 ----
    secret_key: str = 'dev-only-change-me'
    token_ttl_hours: int = 12
    service_token: str = 'dev-service-token'
    service_actor_id: str = 'ai-agent'

    # ---- 初始化数据 ----
    seed_demo: bool = True
    bootstrap_admin_email: str = 'admin@example.com'
    bootstrap_admin_password: str = 'admin12345'
    bootstrap_admin_name: str = '系统管理员'

    # ---- 前端 ----
    serve_web: bool = True
    web_dist_dir: str = 'web/dist'
    cors_origins: str = 'http://localhost:5174,http://127.0.0.1:5174'

    # ---- 分页 ----
    default_page_size: int = 50
    max_page_size: int = 200

    @field_validator('storage')
    @classmethod
    def _validate_storage(cls, value: str) -> str:
        resolved = (value or '').strip().lower()
        if resolved not in STORAGE_CHOICES:
            raise ValueError(f'storage 必须是 {STORAGE_CHOICES} 之一，收到 {value}')
        return resolved

    @property
    def database_uri(self) -> str:
        '''sqlite 走本地文件（零依赖），postgres 用配置里的连接串。'''
        if self.storage == 'sqlite':
            return f'sqlite+pysqlite:///{self.sqlite_file}'
        return self.database_url

    @property
    def sqlite_file(self) -> str:
        return str(self.sqlite_path).replace('\\', '/')

    @property
    def cors_origin_list(self) -> list[str]:
        return sorted(_split_csv(self.cors_origins))


@lru_cache
def get_settings() -> Settings:
    return Settings()