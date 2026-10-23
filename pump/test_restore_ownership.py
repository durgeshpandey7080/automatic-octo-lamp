import os
from pathlib import Path
import tempfile
from unittest.mock import patch
from django.test import SimpleTestCase
from restore_apply import preserve_owner


class RestoreOwnershipTests(SimpleTestCase):
    def test_same_owner_needs_no_privileged_chown(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'restoring';path.write_text('synthetic')
            info=path.stat()
            with patch('restore_apply.os.chown',create=True) as chown:
                preserve_owner(path,(info.st_uid,info.st_gid))
                chown.assert_not_called()

    def test_required_ownership_change_failure_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'restoring';path.write_text('synthetic')
            info=path.stat()
            with patch('restore_apply.os.chown',create=True,side_effect=PermissionError('Synthetic permission failure')) as chown:
                with self.assertRaises(PermissionError):preserve_owner(path,(info.st_uid+1,info.st_gid+1))
                chown.assert_called_once_with(path,info.st_uid+1,info.st_gid+1)
