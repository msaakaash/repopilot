import re, subprocess
from pathlib import Path
from urllib.parse import urlparse
from app.config import settings

class RepositoryError(RuntimeError): pass

def validate_github_url(url: str) -> str:
    parsed=urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}:
        raise RepositoryError("Only https://github.com/owner/repository URLs are accepted")
    if not re.fullmatch(r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?", parsed.path): raise RepositoryError("Invalid GitHub repository path")
    return url.removesuffix("/")

def safe_name(url: str) -> str: return re.sub(r"[^A-Za-z0-9_.-]", "_", url.rsplit("/", 2)[-2] + "_" + url.rsplit("/", 1)[-1])

def clone_to_bare(url: str) -> Path:
    validate_github_url(url); root=settings.workspace_root.resolve(); root.mkdir(parents=True, exist_ok=True)
    bare=root / f"{safe_name(url)}.git"
    if not bare.exists():
        result=subprocess.run(["git","clone","--bare","--filter=blob:none",url,str(bare)], capture_output=True,text=True,timeout=180)
        if result.returncode: raise RepositoryError(result.stderr[-1000:])
    else:
        # The mirror is shared by tasks, so update it before resolving a branch.
        result=subprocess.run(["git","--git-dir",str(bare),"fetch","--prune","origin"], capture_output=True,text=True,timeout=180)
        if result.returncode: raise RepositoryError(f"Cannot update repository: {result.stderr[-1000:]}")
    return bare

def create_worktree(url: str, task_id: str, branch: str) -> Path:
    bare=clone_to_bare(url); target=settings.workspace_root.resolve()/"tasks"/task_id
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists(): return target

    valid_branch=subprocess.run(["git","check-ref-format","--branch",branch],capture_output=True,text=True,timeout=10)
    if valid_branch.returncode:
        raise RepositoryError(f"Invalid branch name: {branch!r}")

    # A --bare clone stores remote branches as refs/heads/<branch>, not as
    # refs/remotes/origin/<branch>. Resolve the commit explicitly so checkout
    # works for both a fresh clone and an older cache layout.
    revision=None
    for ref in (f"refs/heads/{branch}", f"refs/remotes/origin/{branch}"):
        resolved=subprocess.run(
            ["git","--git-dir",str(bare),"rev-parse","--verify","--quiet",f"{ref}^{{commit}}"],
            capture_output=True,text=True,timeout=10,
        )
        if resolved.returncode == 0:
            revision=resolved.stdout.strip()
            break
    if not revision:
        branches=subprocess.run(
            ["git","--git-dir",str(bare),"for-each-ref","--format=%(refname:strip=2)","refs/heads"],
            capture_output=True,text=True,timeout=10,
        )
        available=", ".join(branches.stdout.splitlines()[:20]) or "none"
        raise RepositoryError(f"Branch {branch!r} was not found. Available branches: {available}")

    result=subprocess.run(["git","--git-dir",str(bare),"worktree","add","--detach",str(target),revision],capture_output=True,text=True,timeout=90)
    if result.returncode: raise RepositoryError(f"Cannot create worktree for branch {branch}: {result.stderr[-800:]}")
    return target
