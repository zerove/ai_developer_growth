from tools.scripts.rules_engine.parsers.python_parser import PythonParser


class MockNode:
    def __init__(self, type: str, start: tuple, end: tuple):
        self.type = type
        self.start_point = start
        self.end_point = end
        self.children = []


def test_python_parser_instantiation():
    parser = PythonParser()
    assert parser is not None
