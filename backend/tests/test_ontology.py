from app.graph.ontology import build_mapping
from app.services.parser import ParsedFile, Symbol


def test_mapping_uses_versioned_api_and_file_ontology():
    files = [ParsedFile("tests/test_api.py", "python", [Symbol("health", "FUNCTION", 1, 2)], ["fastapi"], ["/health"], True)]
    mapping = build_mapping("repo-1", files)
    assert mapping["version"] == "1.2"
    assert mapping["labels"]["File"] == 1
    assert mapping["labels"]["APIEndpoint"] == 1
    assert mapping["labels"]["Test"] == 1
    assert mapping["relationships"]["IMPORTS"] == 1
    assert mapping["relationships"]["CONTAINS"] == 2
    assert mapping["schema"]["CONTAINS"] == "Repository→Module and Module→File"


def test_mapping_counts_shared_dependency_once_but_each_import_edge():
    files = [
        ParsedFile("one.py", "python", imports=["shared"]),
        ParsedFile("two.py", "python", imports=["shared"]),
    ]
    mapping = build_mapping("repo-1", files)
    assert mapping["labels"]["Dependency"] == 1
    assert mapping["relationships"]["IMPORTS"] == 2


def test_graph_view_contains_nodes_and_edges_for_mapped_relationships():
    files = [ParsedFile("tests/test_api.py", "python", [Symbol("health", "FUNCTION", 1, 2)], ["fastapi"], ["/health"], True)]
    graph = build_mapping("repo-1", files)["graph_view"]
    node_ids = {node["id"] for node in graph["nodes"]}
    node_labels = {node["label"] for node in graph["nodes"]}
    relationships = {edge["type"] for edge in graph["edges"]}
    assert {"Repository", "Module", "File", "Function", "APIEndpoint", "Dependency", "Test"} <= node_labels
    assert {"CONTAINS", "DEFINES", "EXPOSES", "IMPORTS", "DEPENDS_ON", "TESTS"} <= relationships
    assert all(edge["source"] in node_ids and edge["target"] in node_ids for edge in graph["edges"])
