import subprocess
import pytest
from app.services import repository
from app.services.repository import validate_github_url, RepositoryError
def test_accepts_github_https(): assert validate_github_url("https://github.com/acme/repo") == "https://github.com/acme/repo"
@pytest.mark.parametrize("url",["http://github.com/a/b","https://gitlab.com/a/b","https://github.com/a/b/issues"])
def test_rejects_non_repository_urls(url):
    with pytest.raises(RepositoryError): validate_github_url(url)

def test_worktree_uses_branch_ref_from_bare_clone(tmp_path, monkeypatch):
    bare = tmp_path / "cache.git"
    bare.mkdir()
    workspace = tmp_path / "workspaces"
    calls = []

    monkeypatch.setattr(repository, "clone_to_bare", lambda _: bare)
    monkeypatch.setattr(repository.settings, "workspace_root", workspace)

    def run(args, **_):
        calls.append(args)
        if "check-ref-format" in args:
            return subprocess.CompletedProcess(args, 0, "main\n", "")
        if "rev-parse" in args:
            assert "refs/heads/main^{commit}" in args
            return subprocess.CompletedProcess(args, 0, "abc123\n", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(repository.subprocess, "run", run)
    target = repository.create_worktree("https://github.com/acme/repo", "task-1", "main")

    assert target == workspace.resolve() / "tasks" / "task-1"
    assert any(call[-1] == "abc123" for call in calls if "worktree" in call)
