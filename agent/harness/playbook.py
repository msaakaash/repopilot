"""Load and validate the repository investigation playbook."""
from dataclasses import dataclass
from pathlib import Path
import re

AGENT_ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK_PATH = AGENT_ROOT / "playbooks" / "investigation.md"
REQUIRED_TOOLS = {"github_evidence", "code_evidence", "repository_memory", "github_mcp"}
REQUIRED_OUTPUT = {"summary", "answer", "steps", "affected_files", "tests", "risks", "evidence_sources"}
REQUIRED_SKILLS = {"repopilot-investigation"}

@dataclass(frozen=True)
class Phase:
    name: str
    prompt: str
    tools: tuple[str, ...]
    skills: tuple[str, ...]

@dataclass(frozen=True)
class Playbook:
    name: str
    version: int
    phases: tuple[Phase, ...]

    def phase(self, name: str) -> Phase:
        return next(phase for phase in self.phases if phase.name == name)

def load_playbook(path: Path = PLAYBOOK_PATH) -> Playbook:
    """Parse the Markdown playbook and reject incomplete agent contracts."""
    try:
        source = path.read_text(encoding="utf-8")
        metadata = re.search(r"\A---\s*\nname:\s*(\S+)\s*\nversion:\s*(\d+)\s*\n---", source)
        schema = re.search(r"## Output schema\s*\n(.*?)(?=\n## |\Z)", source, re.DOTALL)
        phase_blocks = re.findall(r"## Phase:\s*([^\n]+)\s*\n(.*?)(?=\n## Phase:|\Z)", source, re.DOTALL)
        if not metadata or not schema:
            raise ValueError("missing metadata or output schema")
        output = set(re.findall(r"-\s+`([a-z_]+)`:\s+[^\n]+", schema.group(1)))
        phases = []
        for name, body in phase_blocks:
            tools_match = re.search(r"### Tools\s*\n(.*?)(?=\n### |\Z)", body, re.DOTALL)
            skills_match = re.search(r"### Skills\s*\n(.*?)(?=\n### |\Z)", body, re.DOTALL)
            prompt_match = re.search(r"### Prompt\s*\n(.*?)(?=\n### |\Z)", body, re.DOTALL)
            if not tools_match or not skills_match or not prompt_match:
                raise ValueError(f"phase {name} is incomplete")
            tools = tuple(re.findall(r"-\s+`([^`]+)`", tools_match.group(1)))
            skills = tuple(re.findall(r"-\s+`([^`]+)`", skills_match.group(1)))
            phases.append(Phase(name.strip(), prompt_match.group(1).strip(), tools, skills))
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid agent playbook: {path}") from exc
    if metadata.group(1) != "repository-investigation":
        raise ValueError("Playbook must have a name and integer version")
    if {phase.name for phase in phases} != {"investigate", "respond"}:
        raise ValueError("Playbook must define investigate and respond phases")
    investigate = next(phase for phase in phases if phase.name == "investigate")
    if not REQUIRED_TOOLS.issubset(set(investigate.tools)):
        raise ValueError("Investigation phase is missing a required tool")
    if not REQUIRED_SKILLS.issubset(set(investigate.skills)):
        raise ValueError("Investigation phase is missing a required skill")
    if output != REQUIRED_OUTPUT:
        raise ValueError("Playbook output schema does not match the plan contract")
    return Playbook(metadata.group(1), int(metadata.group(2)), tuple(phases))
