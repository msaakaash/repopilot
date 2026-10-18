from neo4j import AsyncGraphDatabase
from app.config import settings
from app.services.parser import ParsedFile, file_id
from app.graph.ontology import CONSTRAINTS
class CodeGraph:
    def __init__(self): self.driver=AsyncGraphDatabase.driver(settings.neo4j_uri,auth=(settings.neo4j_username,settings.neo4j_password))
    async def close(self): await self.driver.close()
    async def initialize(self):
        async with self.driver.session() as s:
            for query in CONSTRAINTS: await s.run(query)
    async def index(self, repo_id:str, files:list[ParsedFile]):
        async with self.driver.session() as s:
            await s.run("MERGE (r:Repository {id:$id}) SET r.ontology_version='1.2'",id=repo_id)
            for f in files:
                fid=file_id(repo_id,f.path)
                await s.run("MATCH (r:Repository {id:$repo}) MERGE (m:Module {id:$id}) SET m.path=$path,m.language=$lang,m.is_test=$test MERGE (f:File {id:$file_id}) SET f.path=$path MERGE (r)-[:CONTAINS]->(m) MERGE (m)-[:CONTAINS]->(f)",repo=repo_id,id=fid,file_id=f'{fid}:file',path=f.path,lang=f.language,test=f.is_test)
                for symbol in f.symbols:
                    label="Class" if symbol.kind=="CLASS" else "Function"
                    await s.run(f"MATCH (m:Module {{id:$id}}) MERGE (n:{label} {{id:$sid}}) SET n.name=$name,n.line=$line,n.end_line=$end MERGE (m)-[:DEFINES]->(n)",id=fid,sid=f"{fid}:{symbol.kind}:{symbol.name}",name=symbol.name,line=symbol.line,end=symbol.end_line)
                for endpoint in f.endpoints: await s.run("MATCH (m:Module {id:$id}) MERGE (a:APIEndpoint {id:$aid}) SET a.path=$path MERGE (m)-[:EXPOSES]->(a)",id=fid,aid=f"{fid}:api:{endpoint}",path=endpoint)
                for imp in f.imports: await s.run("MATCH (m:Module {id:$id}) MERGE (d:Dependency {id:$did}) SET d.name=$name MERGE (m)-[:DEPENDS_ON]->(d) MERGE (m)-[:IMPORTS]->(d)",id=fid,did=f"{repo_id}:dep:{imp}",name=imp)
                if f.is_test:
                    await s.run("MATCH (m:Module {id:$id}) MERGE (t:Test {id:$tid}) SET t.path=$path MERGE (m)-[:TESTS]->(t)",id=fid,tid=f"{fid}:test",path=f.path)
    async def search(self, repo_id:str, terms:list[str]) -> dict:
        # Filtering by relationship type is valid across supported Neo4j 5
        # versions. The former relationship-type alternation caused syntax
        # failures on some Aura deployments.
        query="""
        MATCH (:Repository {id:$repo})-[:CONTAINS]->(m:Module)
        OPTIONAL MATCH (m)-[rel]->(s)
        WHERE type(rel) IN $relationship_types
          AND any(t IN $terms WHERE toLower(m.path) CONTAINS t OR toLower(coalesce(s.name, '')) CONTAINS t)
        WITH m, [name IN collect(DISTINCT s.name) WHERE name IS NOT NULL] AS symbols
        RETURN m.id AS id, m.path AS path, m.is_test AS test, symbols
        LIMIT 50
        """
        async with self.driver.session() as s:
            result=await s.run(query, repo=repo_id, terms=[x.lower() for x in terms], relationship_types=["DEFINES", "EXPOSES"])
            files=[x.data() async for x in result]
            # Broad requests such as "inspect for bugs" usually do not name a
            # symbol or filename. Give the planner a bounded repository map
            # instead of silently planning with no code evidence.
            if not files:
                fallback=await s.run("""
                    MATCH (:Repository {id:$repo})-[:CONTAINS]->(m:Module)
                    OPTIONAL MATCH (m)-[:DEFINES]->(symbol)
                    WITH m, [name IN collect(DISTINCT symbol.name) WHERE name IS NOT NULL] AS symbols
                    RETURN m.id AS id, m.path AS path, m.is_test AS test, symbols
                    ORDER BY m.is_test, m.path
                    LIMIT 50
                """, repo=repo_id)
                files=[x.data() async for x in fallback]
            return {"files":files}
