from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    # Resolve configuration relative to this source file, not the process working
    # directory. This keeps the API, workers, and tests on the same persistent
    # database and workspace locations.
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")
    llm_provider: str = "gemini"
    llm_model: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_model: str = ""
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "change_me"
    postgres_url: str = "postgresql+asyncpg://repopilot:change_me@localhost:5432/repopilot"
    github_token: str = ""
    # The GitHub MCP server receives this only as a process environment variable;
    # it is never placed in an agent prompt, task record, or client response.
    github_mcp_command: str = "npx"
    github_mcp_args: str = "-y,@modelcontextprotocol/server-github"
    github_mcp_token_env: str = "GITHUB_PERSONAL_ACCESS_TOKEN"
    workspace_root: Path = PROJECT_ROOT / "data" / "workspaces"
    project_root: Path = PROJECT_ROOT
    max_repair_attempts: int = 2
    execution_timeout_seconds: int = 600
    max_repository_mb: int = 250

settings = Settings()
