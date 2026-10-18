from dataclasses import dataclass, field
from pathlib import Path
import hashlib, re
try:
    from tree_sitter_language_pack import get_parser
except ImportError: get_parser = None
LANGS={".py":"python",".ts":"typescript",".tsx":"tsx",".js":"javascript",".jsx":"javascript",".java":"java",".go":"go",".rs":"rust",".rb":"ruby",".c":"c",".cpp":"cpp",".h":"c",".cs":"c_sharp"}
SKIP={".git","node_modules",".venv","venv","dist","build","vendor","coverage"}
@dataclass
class Symbol: name:str; kind:str; line:int; end_line:int
@dataclass
class ParsedFile:
    path:str; language:str; symbols:list[Symbol]=field(default_factory=list); imports:list[str]=field(default_factory=list); endpoints:list[str]=field(default_factory=list); is_test:bool=False
def _walk(node, source: bytes, symbols: list[Symbol]):
    types={"function_definition":"FUNCTION","function_declaration":"FUNCTION","method_definition":"FUNCTION","class_definition":"CLASS","class_declaration":"CLASS","interface_declaration":"CLASS"}
    if node.type in types:
        name=next((source[c.start_byte:c.end_byte].decode(errors="ignore") for c in node.children if c.type in {"identifier","type_identifier","property_identifier"}),None)
        if name: symbols.append(Symbol(name,types[node.type],node.start_point[0]+1,node.end_point[0]+1))
    for child in node.children: _walk(child,source,symbols)
def parse_repository(root: Path, limit=5000) -> list[ParsedFile]:
    result=[]
    for path in root.rglob("*"):
        if len(result)>=limit: break
        if not path.is_file() or any(p in SKIP for p in path.parts) or path.suffix not in LANGS or path.stat().st_size>1_000_000: continue
        rel=path.relative_to(root).as_posix(); source=path.read_bytes(); lang=LANGS[path.suffix]; parsed=ParsedFile(rel,lang,is_test=bool(re.search(r"(^|/)(test_|.*(_test|\.test|\.spec))",rel)))
        text=source.decode(errors="ignore")
        parsed.imports=[a or b for a,b in re.findall(r"(?:from\s+([A-Za-z_][\w.]*)\s+import|import\s+(?:.*?\s+from\s+)?['\"]([^'\"]+)['\"])",text)]
        parsed.endpoints=re.findall(r"@?(?:app|router)\.(?:get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]",text)
        if get_parser:
            try: _walk(get_parser(lang).parse(source).root_node,source,parsed.symbols)
            except Exception: pass
        result.append(parsed)
    return result
def file_id(repo: str,path: str) -> str: return hashlib.sha256(f"{repo}:{path}".encode()).hexdigest()[:24]
