import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('explorer_manage', ROOT/'services/evidence_assessment/manage.py')
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


class LifecycleTests(unittest.TestCase):
    def test_offline_discards_inherited_credentials_and_compose_controls(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY':'do-not-forward', 'TAVILY_API_KEY':'do-not-forward',
                'COMPOSE_FILE':'unexpected.yaml', 'EPOCHGUARD_005I_ALLOW_GEMINI':'1', 'OTHER_TOKEN':'do-not-forward'}, clear=True):
            self.assertEqual(manage.environment(), {'COMPOSE_DISABLE_ENV_FILE':'1'})

    def test_both_live_permissions_required_before_any_file(self):
        for values in ({}, {manage.FLAGS[0]:'1'}, {manage.FLAGS[1]:'1'}):
            with patch.dict(os.environ, values, clear=True), patch.object(Path,'resolve',side_effect=AssertionError('file touched')):
                with self.assertRaises(manage.Failure): manage.environment(True)

    def test_repository_credentials_and_repeated_files_refused(self):
        values = {k:'1' for k in manage.FLAGS}
        values.update({k:str(ROOT/'README.md') for k in manage.FILES})
        with patch.dict(os.environ, values, clear=True):
            with self.assertRaises(manage.Failure): manage.environment(True)

    def test_distinct_external_private_files_forward_paths_only(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory)/str(i) for i in range(3)]
            for path in paths:
                path.write_text('private-placeholder')
                path.chmod(0o600)
            values = dict(zip(manage.FILES, map(str, paths)))
            values.update({k:'1' for k in manage.FLAGS})
            with patch.dict(os.environ, values, clear=True):
                env = manage.environment(True)
            self.assertTrue(all('private-placeholder' not in v for v in env.values()))
            self.assertTrue(all(env[k]=='1' for k in manage.FLAGS))

    def test_existing_resources_are_not_taken_over(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(manage,'ROOT',Path(directory)), \
                patch('sys.argv',['manage.py','test']), patch.object(manage,'resources',return_value={'containers':['existing']}), \
                patch.object(manage,'run') as run, patch.object(manage,'cleanup') as cleanup:
            with self.assertRaises(SystemExit): manage.main()
            run.assert_not_called()
            cleanup.assert_not_called()
            self.assertFalse((Path(directory)/'artifacts/005i/lifecycle.lock').exists())

    def test_failed_start_is_cleaned_without_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(manage,'ROOT',Path(directory)), \
                patch('sys.argv',['manage.py','up']), patch.object(manage,'resources',return_value={'containers':[]}), \
                patch.object(manage,'run',side_effect=manage.Failure('fixed')), patch.object(manage,'cleanup') as cleanup:
            with self.assertRaises(SystemExit): manage.main()
            cleanup.assert_called_once()


if __name__ == '__main__': unittest.main()
