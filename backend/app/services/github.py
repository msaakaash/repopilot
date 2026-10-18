"""Read-only GitHub repository evidence used by the investigation pipeline."""
from urllib.parse import urlparse
import asyncio
import re

import httpx

from app.config import settings
from app.services.repository import RepositoryError, validate_github_url


def repository_name(url: str) -> str:
    validate_github_url(url)
    return urlparse(url).path.strip("/")


async def fetch_repository_details(url: str, branch: str) -> dict:
    """Fetch repository and branch details before cloning.

    This uses GitHub's API with the configured GitHub token when available.
    It is read-only and works for public repositories without a token.  The
    returned evidence is stored with the task so history is reproducible.
    """
    name=repository_name(url)
    headers={"Accept":"application/vnd.github+json", "X-GitHub-Api-Version":"2022-11-28"}
    if settings.github_token:
        headers["Authorization"]=f"Bearer {settings.github_token}"
    timeout=httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(base_url="https://api.github.com", headers=headers, timeout=timeout) as client:
        repository=await client.get(f"/repos/{name}")
        if repository.status_code == 404:
            raise RepositoryError("GitHub repository was not found or the configured token cannot access it")
        if repository.status_code in {401, 403}:
            raise RepositoryError("GitHub API authentication or rate limit prevented repository inspection")
        repository.raise_for_status()
        branch_response=await client.get(f"/repos/{name}/branches/{branch}")
        if branch_response.status_code == 404:
            default_branch=repository.json().get("default_branch", "unknown")
            raise RepositoryError(f"Branch {branch!r} was not found on GitHub. Default branch: {default_branch}")
        branch_response.raise_for_status()
        branches_response, languages_response = await asyncio.gather(
            client.get(f"/repos/{name}/branches", params={"per_page": 100}),
            client.get(f"/repos/{name}/languages"),
        )
        branches_response.raise_for_status()
        languages_response.raise_for_status()
        last = re.search(r"[?&]page=(\d+)[^>]*>; rel=\"last\"", branches_response.headers.get("Link", ""))
        if last:
            last_page = int(last.group(1))
            tail = await client.get(f"/repos/{name}/branches", params={"per_page": 100, "page": last_page})
            tail.raise_for_status()
            branch_count = (last_page - 1) * 100 + len(tail.json())
        else:
            branch_count = len(branches_response.json())

    info=repository.json(); branch_info=branch_response.json()
    branch_names = [item["name"] for item in branches_response.json()]
    # GitHub paginates this endpoint.  The Link header gives the exact total
    # for repositories with more than one page without fetching every branch.
    return {
        "provider":"github",
        "full_name":info["full_name"],
        "html_url":info["html_url"],
        "default_branch":info.get("default_branch"),
        "selected_branch":branch,
        "commit_sha":branch_info.get("commit", {}).get("sha"),
        "private":info.get("private", False),
        "pushed_at":info.get("pushed_at"),
        "languages": languages_response.json(),
        "branches": branch_names,
        "branch_count": branch_count,
    }


async def fetch_branches(url: str) -> dict:
    """Read branch names before a task is created; never mutates GitHub."""
    name = repository_name(url)
    headers={"Accept":"application/vnd.github+json", "X-GitHub-Api-Version":"2022-11-28"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    async with httpx.AsyncClient(base_url="https://api.github.com", headers=headers, timeout=httpx.Timeout(20.0, connect=10.0)) as client:
        repository = await client.get(f"/repos/{name}")
        if repository.status_code == 404:
            raise RepositoryError("GitHub repository was not found or the configured token cannot access it")
        if repository.status_code in {401, 403}:
            raise RepositoryError("GitHub API authentication or rate limit prevented branch discovery")
        repository.raise_for_status()
        branches = await client.get(f"/repos/{name}/branches", params={"per_page": 100})
        branches.raise_for_status()
    default = repository.json().get("default_branch", "main")
    names = [item["name"] for item in branches.json()]
    return {"branches": names, "default_branch": "main" if "main" in names else default}
