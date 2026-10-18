import re
from sqlalchemy import select
from app.db.database import SessionLocal
from app.db.models import Task
from app.graph.repository import CodeGraph
from app.graph.ontology import build_mapping
from app.services.repository import create_worktree
from app.services.github import fetch_repository_details
from app.services.memory import recent_repository_memory
from app.services.parser import parse_repository
from agent.harness.planner import Plan, plan_task, propose_change
from app.services.executor import run_in_docker
import subprocess
async def process(task_id:str):
    async with SessionLocal() as db:
        task=await db.get(Task,task_id)
        memory=await recent_repository_memory(db, task.repository_url, task_id)
        task.status="inspecting"; await db.commit()
    try:
        github=await fetch_repository_details(task.repository_url, task.branch)
        worktree=create_worktree(task.repository_url,task_id,task.branch)
        files=parse_repository(worktree); graph=CodeGraph()
        ontology_mapping = build_mapping(task_id, files)
        terms=[x for x in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}",task.request)][:20]
        graph_error = None
        try:
            await graph.initialize(); await graph.index(task_id,files)
            context=await graph.search(task_id,terms)
        except Exception as exc:
            # Neo4j enriches the investigation, but an unavailable graph
            # service must not turn an otherwise valid repository question
            # into a failed task.
            graph_error = str(exc)[:500]
            context=local_graph_context(files, terms)
        finally:
            await graph.close()
        async with SessionLocal() as db:
            row=await db.get(Task,task_id); row.status="planning"; row.result={"files_indexed":len(files),"graph_context":context,"github":github,"agent_memory":memory,"ontology_mapping":ontology_mapping,"basic_analysis":basic_analysis(files, github),"graph_index_status":"local fallback" if graph_error else "indexed in Neo4j"}; await db.commit()
        # No description means the user asked for a repository inspection, not a
        # speculative change. This deliberately works without an LLM credential.
        plan=inspection_plan(files) if not task.request.strip() else await plan_task(task.request,context,github,memory)
        async with SessionLocal() as db:
            row=await db.get(Task,task_id); row.plan=plan.model_dump(); row.status="awaiting_approval"; await db.commit()
    except Exception as exc:
        async with SessionLocal() as db:
            row=await db.get(Task,task_id); row.status="failed"; row.error=str(exc)[:4000]; await db.commit()


def basic_analysis(files, github: dict) -> dict:
    languages: dict[str, int] = {}
    tests = 0
    endpoints = 0
    symbols = 0
    for file in files:
        languages[file.language] = languages.get(file.language, 0) + 1
        tests += int(file.is_test)
        endpoints += len(file.endpoints)
        symbols += len(file.symbols)
    return {"commit": github.get("commit_sha"), "files": len(files), "languages": languages, "test_modules": tests, "api_endpoints": endpoints, "symbols": symbols}


def local_graph_context(files, terms: list[str]) -> dict:
    """Bounded graph-shaped evidence used if Neo4j is temporarily offline."""
    lowered = [term.lower() for term in terms]
    def matches(file):
        haystack = " ".join([file.path, *(symbol.name for symbol in file.symbols)]).lower()
        return not lowered or any(term in haystack for term in lowered)
    selected = [file for file in files if matches(file)] or files
    return {"files": [{"id": file.path, "path": file.path, "test": file.is_test, "symbols": [symbol.name for symbol in file.symbols]} for file in selected[:50]]}


def inspection_plan(files):
    tests = [file.path for file in files if file.is_test][:12]
    return Plan(summary="Repository baseline inspection and ontology mapping", answer="Baseline complete. Add a custom question to have the agent investigate it with verified GitHub MCP and repository-graph evidence.", steps=["Indexed supported source files and their declared symbols.", "Mapped modules, symbols, APIs, and dependencies into the closed Neo4j ontology.", "Review the repository map and add a focused question before approving a code change."], affected_files=[file.path for file in files[:25]], tests=tests, risks=["This is structural analysis; runtime behavior and unparsed languages require a focused follow-up investigation."], evidence_sources=["Repository index", "Neo4j ontology mapping"])

async def execute_approved(task_id: str):
    async with SessionLocal() as db:
        task=await db.get(Task,task_id)
        if not task: return
        context=(task.result or {}).get("graph_context", {})
    try:
        worktree=create_worktree(task.repository_url,task_id,task.branch)
        change=await propose_change(task.request,task.plan or {},context)
        patch=worktree/".repopilot.patch"; patch.write_text(change.unified_diff,encoding="utf-8")
        applied=subprocess.run(["git","apply","--check",str(patch)],cwd=worktree,capture_output=True,text=True)
        if applied.returncode: raise RuntimeError("Generated patch rejected: "+applied.stderr[-1000:])
        subprocess.run(["git","apply",str(patch)],cwd=worktree,check=True,capture_output=True,text=True); patch.unlink(missing_ok=True)
        run=run_in_docker(worktree,change.test_command)
        async with SessionLocal() as db:
            row=await db.get(Task,task_id); row.status="completed" if run.returncode==0 else "failed"; row.result={**(row.result or {}),"change":change.model_dump(),"test":run.__dict__}; row.error=None if run.returncode==0 else run.output; await db.commit()
    except Exception as exc:
        async with SessionLocal() as db:
            row=await db.get(Task,task_id); row.status="failed"; row.error=str(exc)[:4000]; await db.commit()
