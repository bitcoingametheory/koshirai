"""A clean tip cannot hide private or disallowed content in public history or the index."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from check_release import check_git_content


class ReleaseHistoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture' + '@' + 'example.invalid')
        self.git('config', 'commit.gpgsign', 'false')
        self.git('config', 'core.hooksPath', str(self.root / 'unused-hooks'))
        self.write('README.md', 'Synthetic public guide.\n')
        self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.PIPE)

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'Synthetic fixture')

    def check(self):
        failures = set()
        count = check_git_content(self.git, failures)
        return count, failures

    def test_multiple_sanitized_commits_pass(self):
        self.write('README.md', 'Revised public guide.\n')
        self.commit()
        self.assertEqual(self.check(), (2, set()))

    def test_deleted_private_content_fails(self):
        self.write('docs/notes.md', 'person' + '@' + 'example.invalid\n')
        self.commit()
        self.git('rm', 'docs/notes.md')
        self.commit()
        self.assertIn('privacy pattern: docs/notes.md', self.check()[1])

    def test_deleted_forbidden_artifact_fails(self):
        self.write('sample.pdf', 'Synthetic bytes.\n')
        self.commit()
        self.git('rm', 'sample.pdf')
        self.commit()
        self.assertIn('unapproved committed path: sample.pdf', self.check()[1])

    def test_staged_content_is_checked_even_if_working_file_is_clean(self):
        self.write('README.md', 'person' + '@' + 'example.invalid\n')
        self.git('add', 'README.md')
        self.write('README.md', 'Synthetic public guide.\n')
        self.assertIn('privacy pattern: README.md', self.check()[1])

    def test_historical_symlink_fails(self):
        (self.root / 'docs').mkdir()
        (self.root / 'docs/link.md').symlink_to('../README.md')
        self.commit()
        self.git('rm', 'docs/link.md')
        self.commit()
        self.assertIn('unapproved committed path: docs/link.md', self.check()[1])
