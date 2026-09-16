#!/usr/bin/env python3
"""Unit tests for the frontend CI change mapping."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("ci_detect.py")
SPEC = importlib.util.spec_from_file_location("ci_detect", MODULE_PATH)
assert SPEC and SPEC.loader
ci_detect = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ci_detect)


class DetectMappingTest(unittest.TestCase):
    def test_docs_only(self) -> None:
        self.assertEqual(ci_detect.classify(["README.md"]), ([], []))

    def test_source_change(self) -> None:
        self.assertEqual(ci_detect.classify(["src/frontend/frontend.py"]), (["frontend"], []))

    def test_docker_input(self) -> None:
        self.assertEqual(
            ci_detect.classify(["src/frontend/uv.lock"]),
            (["frontend"], ["frontend"]),
        )

    def test_common_workflow(self) -> None:
        self.assertEqual(
            ci_detect.classify([".github/workflows/frontend-ecr.yml"]),
            (["frontend"], ["frontend"]),
        )

    def test_delete_uses_deleted_path(self) -> None:
        paths = ci_detect.paths_from_name_status("D\tsrc/frontend/frontend.py\n")
        self.assertEqual(ci_detect.classify(paths), (["frontend"], []))

    def test_rename_checks_old_and_new_paths(self) -> None:
        paths = ci_detect.paths_from_name_status("R100\tsrc/frontend/a.py\tsrc/frontend/b.py\n")
        self.assertEqual(ci_detect.classify(paths), (["frontend"], []))

    def test_unknown_path_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "unclassified paths"):
            ci_detect.classify(["src/loadgenerator/locustfile.py"])


if __name__ == "__main__":
    unittest.main()
