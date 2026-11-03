"""Synthetic temporary gate fixtures; never copy these receipts to the public candidate."""
import copy
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import release_readiness as dual

ROOT = Path(__file__).resolve().parents[1]


class DualGateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / 'candidate'
        shutil.copytree(ROOT / 'release-candidates/v1.0.0', self.root)
        self.c = dual.actual.read_json(self.root / 'candidate.json')
        self.v = dual.actual.read_json(self.root / 'virtual-candidate.json')
        self.v['evidence'] = dict.fromkeys(dual.VIRTUAL)
        self.save()

    def save(self):
        (self.root / 'virtual-candidate.json').write_text(json.dumps(self.v))

    def metric(self, key, profile):
        base = {'target_profile': profile, 'profile_config_sha256': dual.actual.profile_digest(self.c, profile)}
        if key == 'core_regression':
            return {'passed': 225, 'phases_passed': 675, 'failed': 0, 'skipped': 0, 'xfailed': 0, 'xpassed': 0,
                    'complete': True, 'source_digest_before': self.c['source_digest'],
                    'source_digest_after': self.c['source_digest'], 'original_receipt_sha256': 'a'*64}
        if key == 'provider_contract':
            return base | {'cases': 50, 'passed': 50, 'failed': 0, 'case_manifest_sha256': 'a'*64,
                           'model_output_double': True, 'semantic_quality_tested': False,
                           'checks': dict.fromkeys(['keep_discard_review', 'invalid_fail_closed', 'no_fallback', 'source_preserved'], True)}
        if key == 'service_lifecycle':
            return base | {'checks': dict.fromkeys(dual.actual.RUNTIME_CHECKS, True), 'real_service': True,
                           'model_output_double': True, 'all_generated_parts_deleted': True,
                           'validation_method': 'common_service_plus_mode_double',
                           'common_runtime_result_sha256': dual.actual.read_json(self.root / self.c['evidence']['runtime_contract']['path'])['execution_result_sha256'],
                           'profile_service_result_sha256': 'd'*64,
                           'common_runtime_binding': self.c['evidence']['runtime_contract'],
                           'profile_service_binding': self.v['evidence']['security']}
        if key == 'security':
            return base | {'cases': 20, 'violations': 0, 'checks': dict.fromkeys(dual.SAFETY, True),
                           'real_service': True, 'model_output_double': True}
        if key == 'virtual_install':
            return base | {'checks': dict.fromkeys(dual.INSTALL, True), 'version': '1.0.0'}
        return {'checks': dict.fromkeys(dual.actual.DIST_CHECKS, True), 'artifact_version': '1.0.0',
                'artifact_source_commit': self.c['source_commit'], 'prerelease': False, 'draft': False,
                'platform': self.c['platform'], 'private_source_published': False,
                'private_core_excluded': True, 'artifact_inspection_sha256': 'e'*64,
                'assets': [{'name': 'synthetic.tar.gz', 'sha256': 'a'*64, 'bytes': 1}]}

    def receipt(self, key):
        value = {k: self.c[k] for k in dual.actual.IDENTITY}
        value.update(track='virtual', execution_kind=dual.KINDS[key], execution_platform='Linux-x86_64',
                     model_quality_claim=False, execution_result_sha256='d'*64)
        if key in dual.SHARED:
            value['metrics'] = self.metric(key, 'personal')
        else:
            value['profiles'] = {p: self.metric(key, p) for p in dual.actual.PROFILES}
        return value

    def attach(self, key, value=None):
        path = self.root / ('synthetic-' + key + '.json')
        path.write_text(json.dumps(self.receipt(key) if value is None else value))
        self.v['evidence'][key] = {'path': path.name, 'sha256': dual.actual.digest(path.read_bytes())}
        self.save()

    def full(self):
        for key in ['core_regression', 'provider_contract', 'security', 'service_lifecycle', 'virtual_install', 'distribution']:
            self.attach(key)

    def test_virtual100_releases_without_changing_actual_acceptance(self):
        before = dual.actual.evaluate(self.root)
        self.full()
        value = dual.evaluate(self.root)
        self.assertEqual(value['virtual']['score'], 100)
        self.assertTrue(value['release_ready'])
        self.assertFalse(value['actual']['ready'])
        self.assertEqual(value['actual']['profile_scores'], before['profile_scores'])

    def test_final_distribution_is_required(self):
        self.full(); self.v['evidence']['distribution'] = None; self.save()
        value = dual.evaluate(self.root)
        self.assertEqual(value['virtual']['score'], 90)
        self.assertFalse(value['release_ready'])

    def test_private_test_wheel_cannot_be_claimed_as_a_public_artifact(self):
        self.full(); r = self.receipt('distribution'); r['metrics']['private_core_excluded'] = False
        self.attach('distribution', r)
        self.assertFalse(dual.evaluate(self.root)['release_ready'])

    def test_each_profile_must_pass(self):
        self.full(); r = self.receipt('provider_contract'); r['profiles']['company'] = None
        self.attach('provider_contract', r)
        value = dual.evaluate(self.root)
        self.assertEqual(value['virtual']['profile_scores'], {'personal': 100, 'company': 80})
        self.assertEqual(value['virtual']['score'], 80)
        self.assertFalse(value['release_ready'])

    def test_actual_evidence_is_not_automatically_virtual(self):
        self.full(); r = self.receipt('security'); r['track'] = 'actual'; self.attach('security', r)
        self.assertFalse(dual.evaluate(self.root)['release_ready'])

    def test_virtual_shared_evidence_is_rejected_by_actual_audit(self):
        self.full()
        for key in ['core_regression', 'distribution']:
            self.c['evidence'][key] = self.v['evidence'][key]
        (self.root / 'candidate.json').write_text(json.dumps(self.c))
        result = dual.actual.evaluate(self.root)
        for key in ['core_regression', 'distribution']:
            row = next(x for x in result['rows'] if x['id'] == key)
            self.assertEqual(row['earned'], 0)
            self.assertEqual(row['personal'], '증거 오류')

    def test_model_quality_claim_cannot_appear_in_virtual_evidence(self):
        self.full(); r = self.receipt('provider_contract'); r['model_quality_claim'] = True
        self.attach('provider_contract', r); self.assertFalse(dual.evaluate(self.root)['release_ready'])

    def test_runtime_and_profile_config_changes_invalidate_virtual_evidence(self):
        self.full()
        original = copy.deepcopy(self.c)
        for group, key, value in [('runtime', 'retain_chunk_size', 1234), ('company', 'host', 'claude'),
                                   ('company', 'admission_model', 'different-model')]:
            self.c = copy.deepcopy(original)
            if group == 'runtime': self.c['runtime_profile'][key] = value
            else: self.c['profiles'][group][key] = value
            (self.root / 'candidate.json').write_text(json.dumps(self.c))
            result = dual.evaluate(self.root)
            self.assertFalse(result['release_ready'])
            row = next(x for x in result['virtual']['rows'] if x['id'] == 'provider_contract')
            self.assertNotEqual(row['company'], '통과')

    def test_composed_service_rejects_unrelated_hashes_and_receipt_paths(self):
        self.full()
        for field, value in [('common_runtime_result_sha256', '0'*64), ('profile_service_result_sha256', 'f'*64),
                             ('common_runtime_binding', self.v['evidence']['security']),
                             ('profile_service_binding', self.c['evidence']['runtime_contract'])]:
            with self.subTest(field=field):
                r = self.receipt('service_lifecycle'); r['profiles']['company'][field] = value
                self.attach('service_lifecycle', r)
                result = dual.evaluate(self.root)
                self.assertFalse(result['release_ready'])
                row = next(x for x in result['virtual']['rows'] if x['id'] == 'service_lifecycle')
                self.assertNotEqual(row['company'], '통과')

    def test_composed_common_receipt_requires_exact_profile_matrix(self):
        self.full()
        path = self.root / self.c['evidence']['runtime_contract']['path']
        original = dual.actual.read_json(path)
        for matrix in [None, [], {'personal': original['profiles']['personal']},
                       original['profiles'] | {'unexpected': {}}]:
            receipt = copy.deepcopy(original); receipt['profiles'] = matrix
            path.write_text(json.dumps(receipt))
            self.c['evidence']['runtime_contract']['sha256'] = dual.actual.digest(path.read_bytes())
            (self.root / 'candidate.json').write_text(json.dumps(self.c))
            self.attach('service_lifecycle')
            result = dual.evaluate(self.root)
            row = next(x for x in result['virtual']['rows'] if x['id'] == 'service_lifecycle')
            self.assertNotEqual(row['personal'], '통과')
            self.assertFalse(result['release_ready'])

    def test_mock_semantics_are_not_scored_as_model_quality(self):
        self.full(); r = self.receipt('provider_contract'); r['profiles']['company']['semantic_quality_tested'] = True
        self.attach('provider_contract', r); self.assertFalse(dual.evaluate(self.root)['release_ready'])

    def test_source_identity_and_config_track_remain_pinned(self):
        self.full()
        for key in dual.actual.IDENTITY:
            with self.subTest(key=key):
                r = self.receipt('security'); r[key] = 'wrong'; self.attach('security', r)
                self.assertFalse(dual.evaluate(self.root)['release_ready'])

    def test_missing_failed_bool_or_incomplete_counts_cannot_pass(self):
        self.full()
        for field, value in [('cases', True), ('passed', 49), ('failed', 1), ('model_output_double', 1)]:
            with self.subTest(field=field):
                r = self.receipt('provider_contract'); r['profiles']['company'][field] = value
                self.attach('provider_contract', r); self.assertFalse(dual.evaluate(self.root)['release_ready'])

    def test_profile_swap_nonobject_and_extra_matrix_are_rejected(self):
        self.full()
        for value in [False, [], 'pass', {'target_profile': 'personal'}]:
            r = self.receipt('security'); r['profiles']['company'] = value; self.attach('security', r)
            self.assertFalse(dual.evaluate(self.root)['release_ready'])

    def test_hash_path_and_symlink_rejections(self):
        self.full()
        binding = copy.deepcopy(self.v['evidence']['security'])
        for path in ['../outside.json', '/tmp/outside.json']:
            self.v['evidence']['security'] = {'path': path, 'sha256': 'a'*64}; self.save()
            self.assertFalse(dual.evaluate(self.root)['release_ready'])
        self.v['evidence']['security'] = binding; self.v['evidence']['security']['sha256'] = 'b'*64; self.save()
        self.assertFalse(dual.evaluate(self.root)['release_ready'])
        self.attach('security'); path = self.root / self.v['evidence']['security']['path']
        target = self.root / 'other.json'; path.rename(target); path.symlink_to(target)
        self.assertFalse(dual.evaluate(self.root)['release_ready'])

    def test_policy_requires_explicit_stable_virtual100_then_actual(self):
        p = self.root / 'release-policy.json'; original = json.loads(p.read_text())
        for key, value in [('required_virtual_score', 90), ('schema_version', True), ('prerelease', 0), ('actual_verification', 'never')]:
            policy = original | {key: value}; p.write_text(json.dumps(policy))
            with self.subTest(key=key), self.assertRaises(ValueError): dual.evaluate(self.root)

    def test_cli_uses_virtual_for_release_and_actual_for_followup(self):
        self.full()
        for track, exit_code in [('virtual', 0), ('actual', 3)]:
            output = io.StringIO()
            with redirect_stdout(output): result = dual.main(['check', '--track', track, '--candidate', str(self.root)])
            data = json.loads(output.getvalue())
            self.assertEqual(result, exit_code); self.assertTrue(data['release_ready']); self.assertFalse(data['actual_complete'])

    def test_real_validator_is_not_weakened(self):
        self.full()
        with patch.object(dual.actual, 'evaluate', wraps=dual.actual.evaluate) as evaluate:
            result = dual.evaluate(self.root)
            evaluate.assert_called_once_with(self.root)
        self.assertEqual(result['actual']['score'], 15)

    def test_generated_combined_table_matches(self):
        root = ROOT / 'release-candidates/v1.0.0'
        self.assertEqual((root / 'RELEASE-READINESS.ko.md').read_text(), dual.render(dual.evaluate(root)))


if __name__ == '__main__':
    unittest.main()
