# -*- coding: utf-8 -*-
"""عقد ملفات السير: كلّ ملفٍّ في .github/workflows يُقرأ بمحلّلٍ يردّ المفتاح المكرّر.

سببُه (2026-11-03): دخلت كتلتا env في خطوةٍ واحدة من restore.yml مع تقسية #59،
فرفض GitHub الملفَّ كلَّه وفشلت حلقة الاسترجاع قبل أن تبدأ أيُّ وظيفة. ومحلّلُ yaml
الافتراضيُّ في بايثون يقبل التكرار صامتاً (‏يأخذ الأخير)، فلا يكشفه إلا محلّلٌ صارم.
"""
import pathlib
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
WF = ROOT / ".github" / "workflows"


class _Strict(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    seen = {}
    for k, _ in node.value:
        key = loader.construct_object(k, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None, f"مفتاحٌ مكرّر {key!r} (أوّلُه في السطر {seen[key] + 1})", k.start_mark)
        seen[key] = k.start_mark.line
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


_Strict.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


class WorkflowYamlContract(unittest.TestCase):
    def test_no_duplicate_keys(self):
        files = sorted(WF.glob("*.yml")) + sorted(WF.glob("*.yaml"))
        self.assertTrue(files, "لا ملفّاتِ سير")
        bad = []
        for f in files:
            try:
                yaml.load(f.read_text(encoding="utf-8"), Loader=_Strict)
            except yaml.YAMLError as e:
                bad.append(f"{f.name}: {e}")
        self.assertEqual(bad, [], "\n".join(bad))

    def test_strict_loader_rejects_duplicate(self):
        with self.assertRaises(yaml.constructor.ConstructorError):
            yaml.load("a:\n  env: {x: 1}\n  env: {y: 2}\n", Loader=_Strict)


if __name__ == "__main__":
    unittest.main()
