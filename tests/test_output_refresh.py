import json
from pathlib import Path
import tempfile
import unittest

from scripts.output_refresh import refresh_directory, refresh_json


class OutputRefreshTests(unittest.TestCase):
    def test_refresh_removes_stale_batches_and_preserves_unrelated_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'output'
            output.mkdir()
            (output / 'batch-000000.parquet').write_text('old')
            (output / 'batch-000001.parquet').write_text('stale')
            (output / 'keep.txt').write_text('keep')
            def build(stage):
                stage.mkdir()
                (stage / 'batch-000000.parquet').write_text('new')
                (stage / 'ingestion-manifest.json').write_text(json.dumps({'output': str(stage)}))
                return {'output': str(stage)}
            result = refresh_directory(output, build, ('batch-*.parquet', 'ingestion-manifest.json'))
            self.assertEqual(result['output'], str(output))
            self.assertEqual(json.loads((output / 'ingestion-manifest.json').read_text())['output'], str(output))
            self.assertEqual((output / 'batch-000000.parquet').read_text(), 'new')
            self.assertFalse((output / 'batch-000001.parquet').exists())
            self.assertEqual((output / 'keep.txt').read_text(), 'keep')

    def test_failed_build_preserves_existing_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'output'
            output.mkdir()
            marker = output / 'batch-000000.parquet'
            marker.write_text('old')
            def fail(stage):
                raise RuntimeError('failed')
            with self.assertRaises(RuntimeError):
                refresh_directory(output, fail, ('batch-*.parquet',))
            self.assertEqual(marker.read_text(), 'old')
            result = Path(temporary) / 'result.json'
            result.write_text('old')
            with self.assertRaises(RuntimeError):
                refresh_json(result, fail)
            self.assertEqual(result.read_text(), 'old')
