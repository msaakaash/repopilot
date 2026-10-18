import subprocess
from dataclasses import dataclass
from pathlib import Path
from app.config import settings
@dataclass
class ExecutionResult: returncode:int; output:str; command:list[str]
ALLOWED={"pytest","npm","pnpm","yarn","ruff","mypy","python","go","cargo"}
def run_in_docker(worktree:Path, command:list[str]) -> ExecutionResult:
    if not command or command[0] not in ALLOWED: raise ValueError("Command is not allowlisted")
    docker=["docker","run","--rm","--network","none","--cpus","1","--memory","1g","--pids-limit","256","--cap-drop","ALL","--security-opt","no-new-privileges","--read-only","--tmpfs","/tmp:rw,noexec,nosuid,size=128m","-v",f"{worktree.resolve()}:/workspace:rw","-w","/workspace","python:3.12-slim",*command]
    try:
        p=subprocess.run(docker,capture_output=True,text=True,timeout=settings.execution_timeout_seconds)
        return ExecutionResult(p.returncode,(p.stdout+p.stderr)[-20000:],docker)
    except FileNotFoundError: return ExecutionResult(127,"Docker is unavailable; repository code was not executed.",docker)
    except subprocess.TimeoutExpired: return ExecutionResult(124,"Execution timed out and Docker was terminated.",docker)
