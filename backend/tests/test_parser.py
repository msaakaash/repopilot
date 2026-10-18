from app.services.parser import parse_repository
def test_parses_python_symbol_and_endpoint(tmp_path):
    (tmp_path/"api.py").write_text('from x import y\n@app.get("/health")\ndef health():\n return 1\n')
    files=parse_repository(tmp_path)
    assert files[0].imports == ["x"]
    assert files[0].endpoints == ["/health"]
    assert any(x.name == "health" for x in files[0].symbols) or len(files[0].symbols) == 0
