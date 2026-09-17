from pathlib import Path
import unittest

from tools.ci_fleet.agent_cmd import ALLOWED_WF


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_WORKFLOW = ROOT / ".github" / "workflows" / "package-catalog-cloud.yml"


class AgentCommandContractTest(unittest.TestCase):
    def test_guarded_package_catalog_workflow_is_dispatchable(self):
        self.assertIn("package-catalog-cloud.yml", ALLOWED_WF)

    def test_publish_count_tracks_live_certificate_snapshot(self):
        text = PACKAGE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("SNAPSHOT_CERTIFIED=$(jq -r '.indexes | length'", text)
        self.assertIn("CANDIDATE_CERTIFIED=$(jq -r '.certifiedGate.timingCertified'", text)
        self.assertIn('test "$CANDIDATE_CERTIFIED" = "$SNAPSHOT_CERTIFIED"', text)
        self.assertNotIn("timingCertified' \"$WORK/catalog.certified.json\")\" = 159", text)


if __name__ == "__main__":
    unittest.main()
