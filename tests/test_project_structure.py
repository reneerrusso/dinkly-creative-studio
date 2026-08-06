from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.validate_project import JSON_DATA_FILES, REQUIRED_FILES, ROOT, validate_project


class ProjectStructureTests(unittest.TestCase):
    def test_all_required_project_files_exist(self) -> None:
        missing = [relative for relative in REQUIRED_FILES if not (ROOT / relative).is_file()]
        self.assertEqual(missing, [])

    def test_all_data_files_are_valid_json_arrays(self) -> None:
        for relative in JSON_DATA_FILES:
            payload = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            self.assertIsInstance(payload, list, relative)

    def test_reference_image_is_present_and_nonempty(self) -> None:
        image = ROOT / "references" / "dinkly_young.png"
        self.assertTrue(image.is_file())
        self.assertGreater(image.stat().st_size, 100)

    def test_validator_passes_without_recursive_test_run(self) -> None:
        self.assertEqual(validate_project(Path(ROOT), run_tests=False), [])


if __name__ == "__main__":
    unittest.main()
