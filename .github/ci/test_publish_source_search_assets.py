"""Publication safeguards, with no GitHub writes or credential dependency."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('source_search_publisher',
    Path(__file__).with_name('publish-source-search-assets.py'))
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.source = Path(self.directory.name) / 'VERIFICATION.json'
        self.source.write_bytes(b'{"reviewed":true}\n')
        self.name = 'SOURCE-SEARCH-VERIFICATION.json'
        self.selected = {self.name: self.source}
        self.asset = {'name': self.name, 'id': 10, **publisher.fingerprint(self.source)}

    def test_matching_asset_is_idempotent(self):
        self.assertEqual(publisher.plan({'assets': [self.asset]}, self.selected), [])

    def test_differing_existing_asset_stops_before_upload(self):
        before = {'assets': [{**self.asset, 'digest': 'sha256:' + '0' * 64}]}
        with patch.object(publisher.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'refusing to replace'):
                publisher.publish(before, self.selected)
            run.assert_not_called()

    def test_upload_uses_exact_public_filename_and_never_clobbers(self):
        after = {'assets': [self.asset], 'body': publisher.MARKER}
        uploaded = []
        def upload(command, **kwargs):
            self.assertEqual(command[:4], ['gh', 'release', 'upload', 'v2.0.0'])
            path = Path(command[4])
            self.assertEqual(path.name, self.name)
            self.assertEqual(path.read_bytes(), self.source.read_bytes())
            self.assertNotIn('--clobber', command)
            self.assertEqual(command[5:], ['--repo', 'chonamdoo/agents-memory-releases'])
            uploaded.append(path.name)
        with patch.object(publisher, 'release', return_value=after), \
                patch.object(publisher.subprocess, 'run', side_effect=upload):
            publisher.publish({'assets': []}, self.selected)
        self.assertEqual(uploaded, [self.name])

    def test_previous_asset_identity_must_be_preserved(self):
        with self.assertRaisesRegex(ValueError, 'previous release asset changed'):
            publisher.preserved({'assets': [self.asset]},
                                {'assets': [{**self.asset, 'id': 11}]})

    def test_stable_release_is_never_modified(self):
        value = {'id': publisher.RELEASE_ID, 'tag_name': 'v2.0.0',
                 'prerelease': False, 'draft': False}
        with patch.object(publisher, 'gh', return_value=json.dumps(value)):
            with self.assertRaisesRegex(ValueError, 'never change its channel'):
                publisher.release()


if __name__ == '__main__':
    unittest.main()
