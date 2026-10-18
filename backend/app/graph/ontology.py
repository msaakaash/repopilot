"""Closed property-graph ontology used by the repository index."""
from collections import Counter

# Version this deliberately: consumers can reliably interpret historical maps.
LABELS={"Repository","Module","File","Class","Function","APIEndpoint","Test","Dependency","Issue"}
RELATIONSHIPS={"CONTAINS","IMPORTS","CALLS","DEFINES","EXPOSES","TESTS","DEPENDS_ON","AFFECTS"}
CONSTRAINTS=[f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE" for label in LABELS]


def build_mapping(repository_id: str, files: list) -> dict:
    """Return a UI-safe, closed-world summary of what was mapped to Neo4j."""
    labels = Counter({"Repository": 1})
    relationships = Counter()
    languages = Counter()
    modules: list[dict] = []
    dependencies: set[str] = set()
    graph_nodes = [{"id": "repository", "label": "Repository", "name": "Repository"}]
    graph_edges: list[dict] = []
    graph_node_ids = {"repository"}
    graph_edge_ids: set[tuple[str, str, str]] = set()
    for file in files:
        # This compact projection is returned to the browser in addition to
        # being indexed in Neo4j. It is deliberately bounded for large repos,
        # while the complete mapping remains in Neo4j.
        if len(modules) < 100:
            module_id = f"module:{file.path}"
            graph_nodes.append({"id": module_id, "label": "Module", "name": file.path})
            graph_node_ids.add(module_id)
            graph_edges.append({"source": "repository", "target": module_id, "type": "CONTAINS"})
            file_id = f"file:{file.path}"
            graph_nodes.append({"id": file_id, "label": "File", "name": file.path})
            graph_edges.append({"source": module_id, "target": file_id, "type": "CONTAINS"})
            for symbol in file.symbols[:12]:
                symbol_id = f"{module_id}:{symbol.kind}:{symbol.name}"
                if symbol_id not in graph_node_ids:
                    graph_nodes.append({"id": symbol_id, "label": symbol.kind.title(), "name": symbol.name})
                    graph_node_ids.add(symbol_id)
                    graph_edges.append({"source": module_id, "target": symbol_id, "type": "DEFINES"})
            for endpoint in file.endpoints[:8]:
                endpoint_id = f"{module_id}:endpoint:{endpoint}"
                if endpoint_id not in graph_node_ids:
                    graph_nodes.append({"id": endpoint_id, "label": "APIEndpoint", "name": endpoint})
                    graph_node_ids.add(endpoint_id)
                    graph_edges.append({"source": module_id, "target": endpoint_id, "type": "EXPOSES"})
            for dependency in sorted(set(file.imports))[:12]:
                dependency_id = f"dependency:{dependency}"
                if dependency_id not in graph_node_ids:
                    graph_nodes.append({"id": dependency_id, "label": "Dependency", "name": dependency})
                    graph_node_ids.add(dependency_id)
                for relationship in ("IMPORTS", "DEPENDS_ON"):
                    edge_id = (module_id, dependency_id, relationship)
                    if edge_id not in graph_edge_ids:
                        graph_edges.append({"source": module_id, "target": dependency_id, "type": relationship})
                        graph_edge_ids.add(edge_id)
            if file.is_test:
                test_id = f"test:{file.path}"
                graph_nodes.append({"id": test_id, "label": "Test", "name": file.path})
                graph_edges.append({"source": module_id, "target": test_id, "type": "TESTS"})
        labels["Module"] += 1
        labels["File"] += 1
        # These are the two explicit edges written by CodeGraph.index:
        # Repository -> Module and Module -> File.
        relationships["CONTAINS"] += 2
        languages[file.language] += 1
        symbol_counts = Counter(symbol.kind.title() for symbol in file.symbols)
        for label, count in symbol_counts.items():
            labels[label] += count
            relationships["DEFINES"] += count
        labels["APIEndpoint"] += len(file.endpoints)
        relationships["EXPOSES"] += len(file.endpoints)
        # Dependency nodes are shared across modules; relationship counts are
        # therefore de-duplicated per importing module, just as MERGE does.
        imports = set(file.imports)
        dependencies.update(imports)
        relationships["DEPENDS_ON"] += len(imports)
        relationships["IMPORTS"] += len(imports)
        if file.is_test:
            labels["Test"] += 1
            relationships["TESTS"] += 1
        modules.append({
            "path": file.path,
            "language": file.language,
            "is_test": file.is_test,
            "symbols": len(file.symbols),
            "endpoints": len(file.endpoints),
            "imports": len(file.imports),
        })
    labels["Dependency"] = len(dependencies)
    result = {
        "version": "1.2",
        "repository_id": repository_id,
        "labels": dict(labels),
        "relationships": dict(relationships),
        "languages": dict(languages),
        "modules": modules[:100],
        "graph_view": {"nodes": graph_nodes, "edges": graph_edges},
        "schema": {
            "Repository": "one investigation root",
            "Module": "one parsed source module",
            "File": "file represented by a module",
            "Class/Function": "declared parsed symbols",
            "APIEndpoint": "statically discovered route",
            "Dependency": "unique imported dependency name",
            "Test": "module identified as a test",
            "CONTAINS": "Repository→Module and Module→File",
            "DEFINES": "Module→Class or Function",
            "EXPOSES": "Module→APIEndpoint",
            "IMPORTS/DEPENDS_ON": "Module→Dependency",
            "TESTS": "test Module→Test",
        },
    }
    validate_mapping(result)
    return result


def validate_mapping(mapping: dict) -> None:
    """Reject accidental ontology drift before a mapping is persisted or shown."""
    unknown_labels = set(mapping.get("labels", {})) - LABELS
    unknown_relationships = set(mapping.get("relationships", {})) - RELATIONSHIPS
    if unknown_labels or unknown_relationships:
        raise ValueError(f"Invalid ontology mapping: labels={unknown_labels}, relationships={unknown_relationships}")
    if mapping.get("repository_id") is None or mapping.get("labels", {}).get("Repository") != 1:
        raise ValueError("Invalid ontology mapping: exactly one Repository node is required")
    if mapping.get("relationships", {}).get("CONTAINS", 0) != mapping.get("labels", {}).get("Module", 0) * 2:
        raise ValueError("Invalid ontology mapping: CONTAINS edges must represent both repository and file containment")
