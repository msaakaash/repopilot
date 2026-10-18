# Agent tools

The investigation playbook uses these runtime tools:

- `github_evidence`: selected repository, branch, and commit.
- `code_evidence`: parsed repository and graph results.
- `repository_memory`: earlier investigations for the repository.
- `github_mcp`: GitHub evidence for custom questions.

The harness verifies that the three local tools and a GitHub MCP tool were called before returning a custom-question plan.
