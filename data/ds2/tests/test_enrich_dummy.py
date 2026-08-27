import copy
import json
import sys
import unittest
from pathlib import Path


DS2_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DS2_DIR))

from enrich_dummy import enrich_dummy
from schemas.models import validate_ds2_output


class TestEnrichDummy(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        sample_path = (
            DS2_DIR
            / "examples"
            / "ds1_issue_output_v1.example.json"
        )

        with sample_path.open("r", encoding="utf-8") as file:
            cls.issues = json.load(file)

    def test_valid_input_returns_ds2_output(self):
        issue = self.issues[0]

        result = enrich_dummy(issue)

        self.assertEqual(
            result["issue_cluster_id"],
            issue["issue_cluster_id"],
        )
        self.assertEqual(
            len(result["articles"]),
            len(issue["articles"]),
        )

    def test_missing_issue_cluster_id_raises_error(self):
        issue = copy.deepcopy(self.issues[0])
        issue.pop("issue_cluster_id")

        with self.assertRaises(ValueError):
            enrich_dummy(issue)

    def test_invalid_stance_confidence_raises_error(self):
        result = enrich_dummy(self.issues[0])

        result["articles"][0]["stance_confidence"] = 1.5

        with self.assertRaises(ValueError):
            validate_ds2_output(result)


if __name__ == "__main__":
    unittest.main()