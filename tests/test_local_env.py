"""Local credentials load without replacing explicit process configuration."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from local_env import load_local_env


class LocalEnvironment(unittest.TestCase):
    def test_loads_quoted_values_and_preserves_explicit_environment(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            file = Path(folder) / '.env'
            file.write_text('# comment\nTOKEN="file value"\nEXPLICIT=file\nINVALID-KEY=value\n')
            os.environ['EXPLICIT'] = 'process'
            load_local_env(file)
            self.assertEqual(os.environ['TOKEN'], 'file value')
            self.assertEqual(os.environ['EXPLICIT'], 'process')
            self.assertNotIn('INVALID-KEY', os.environ)

    def test_missing_file_is_allowed_on_a_fresh_clone(self):
        with tempfile.TemporaryDirectory() as folder:
            load_local_env(Path(folder) / 'missing.env')
