#!/usr/bin/env python3
# Copyright 2020 David Bort <git@dbort.com>
# Use of this source code is governed by a MIT-style license that can be found
# in the LICENSE file or at https://opensource.org/licenses/MIT

"""Tests for backups.config."""

from backups import runner
from backups import config as backup_config
import io
import os
import textwrap
import typing
import unittest
from unittest import mock
from pyfakefs import fake_filesystem_unittest  # type: ignore


def create_tree(fs, tree: typing.Sequence[str]) -> None:
  """Creates a tree of files and directories.

  Files use their paths as contents.

  Args:
    fs: TestCase.fs from a pyfakefs TestCase.
    tree: A sequence of paths. Paths that end with '/' are created as
        directories; otherwise created as files.
  """
  for entry in tree:
    if entry.endswith('/'):
      fs.create_dir(entry)
    else:
      fs.create_file(entry, contents=entry)


class TestBuildFileList(fake_filesystem_unittest.TestCase):
  """Tests for backups.runner._build_file_list()."""

  def setUp(self):
    # Mock out all filesystem access.
    self.setUpPyfakefs()

  def test_ignore_logic(self):
    """Tests that ignoring files and directories works."""
    src_dir = '/test'

    # A backup config that ignores a file and directory.
    inconfig = textwrap.dedent(f"""
    [backups.test]
    src_dir = "{src_dir}"
    ignore = '''
    file1
    dir1/
    '''
    """)
    configs = backup_config.read(io.StringIO(inconfig))
    self.assertEqual(len(configs), 1)
    config = configs[0]

    # Create a tree of files under src_dir.
    rel_tree = (
        'file1',
        'file2',
        'dir1/file3',
        'dir2/file4',
    )
    abs_tree = tuple([os.path.join(src_dir, f) for f in rel_tree])
    create_tree(self.fs, abs_tree)

    # Build the file list given the config.
    file_list = runner._build_file_list(config)

    expected_file_list = (
        'file2',
        'dir2/file4',
    )

    self.assertEqual(file_list, expected_file_list)

  def test_all_ignored(self):
    """Tests the behavior when all files are ignored."""
    src_dir = '/test'

    # A backup config that ignores a file and directory.
    inconfig = textwrap.dedent(f"""
    [backups.test]
    src_dir = "{src_dir}"
    ignore = '''
    file1
    dir1/
    '''
    """)
    configs = backup_config.read(io.StringIO(inconfig))
    self.assertEqual(len(configs), 1)
    config = configs[0]

    # Create a tree of files under src_dir.
    rel_tree = (
        'file1',
        'dir1/file3',
    )
    abs_tree = tuple([os.path.join(src_dir, f) for f in rel_tree])
    create_tree(self.fs, abs_tree)

    # Build the file list given the config.
    file_list = runner._build_file_list(config)

    # Should return an empty list since all files were ignored.
    self.assertEqual(file_list, tuple())

  def test_empty_src_dir(self):
    """Tests the behavior when src_dir is empty."""
    src_dir = '/test'

    # A backup config that ignores a file and directory.
    inconfig = textwrap.dedent(f"""
    [backups.test]
    src_dir = "{src_dir}"
    ignore = '''
    file1
    dir1/
    '''
    """)
    configs = backup_config.read(io.StringIO(inconfig))
    self.assertEqual(len(configs), 1)
    config = configs[0]

    # Create an empty src_dir.
    self.fs.create_dir(src_dir)

    # Build the file list given the config. Note that this also tests the case
    # where the ignore section refers to files that don't exist.
    file_list = runner._build_file_list(config)

    # Should return an empty list since no files were present.
    self.assertEqual(file_list, tuple())


class TestHashFiles(fake_filesystem_unittest.TestCase):
  """Tests for backups.runner._hash_files()."""

  def setUp(self):
    # Mock out all filesystem access.
    self.setUpPyfakefs()

  def test_smoke(self):
    """Tests that the hash changes or does not change as expected."""
    # Create a tree of files. The contents of each file will be its path.
    tree = (
        '/test/file1',
        '/test/dir1/file3',
    )
    create_tree(self.fs, tree)

    # TODO: Using explicit hashes is fragile. What really matters is that each
    # of these should hash to the original or to some unique value. Change this
    # test to build up a set of seen hashes and assert that should-be-unique
    # hashes do not appear in that set.

    # The hash for this tree should be consistent.
    actual_hash = runner._hash_files('/', tree)
    expected_hash = (
        '991727cf36071f338c21c15982cca651bbe99c5671be630942b9ad39c5de35e0'
    )
    self.assertEqual(actual_hash, expected_hash)
    original_hash = expected_hash

    # Modifying one file should change the hash.
    self.fs.remove_object('/test/file1')
    self.fs.create_file('/test/file1', contents='new-contents')
    actual_hash = runner._hash_files('/', tree)
    expected_hash = (
        'dfe0b4689d23b465ac5a88a42d05c736d66741dc618b9059afc1f7498c185e1c'
    )
    self.assertEqual(actual_hash, expected_hash)

    # Restoring its original contents should revert to the original hash.
    self.fs.remove_object('/test/file1')
    self.fs.create_file('/test/file1', contents='/test/file1')
    actual_hash = runner._hash_files('/', tree)
    expected_hash = original_hash
    self.assertEqual(actual_hash, expected_hash)

    # Renaming a file should change the hash, even though its contents
    # are the same.
    new_tree = (
        '/test/renamed',
        '/test/dir1/file3',
    )
    self.fs.create_file('/test/renamed', contents='/test/file1')
    actual_hash = runner._hash_files('/', new_tree)
    expected_hash = (
        '08323ada694d6bdfaec7b8b6313c52fa88bb69c08887d2d9b3cb99e47785e041'
    )
    self.assertEqual(actual_hash, expected_hash)

    # Adding a file to the list should change the hash.
    new_file_path = '/test/new-file'
    new_tree = (*tree, new_file_path)
    self.fs.create_file(new_file_path, contents=new_file_path)
    actual_hash = runner._hash_files('/', new_tree)
    expected_hash = (
        '058cd8b188f9486d9d0cb00ceff1f7244111abca803195b4fdfdacb145966cfe'
    )
    self.assertEqual(actual_hash, expected_hash)

    # Removing a file from the list should change the hash.
    new_tree = tree[:-1]
    actual_hash = runner._hash_files('/', new_tree)
    expected_hash = (
        '8f6f9d3a6c61a37726d7c40f423f7ac3b2c424aee8e5c1de8932a88f4b852cbe'
    )
    self.assertEqual(actual_hash, expected_hash)


class TestListExistingArchives(unittest.TestCase):
  """Tests for backups.runner._list_existing_archives()."""

  @mock.patch('backups.runner.boto3')
  def run_list_existing_archives(
      self, mock_boto3, inconfig: str, s3_response: dict, expected_prefix: str
  ) -> typing.Sequence[str]:
    """Calls runner._list_existing_archives() using the provided context.

    Args:
      inconfig: The config file contents to use to create a backup config.
          Must contain exactly one [backups.<name>] section.
      s3_response: The dict to return from calls to s3client.list_objects().
      expected_prefix: The expected value of the "Prefix" arg passed to
          s3client.list_objects().
    Returns:
      The return value of runner._list_existing_archives().
    """
    configs = backup_config.read(io.StringIO(inconfig))
    self.assertEqual(len(configs), 1)
    config = configs[0]

    # Mock out the response returned by the S3 client.
    mock_s3client = mock.MagicMock()
    mock_boto3.client.return_value = mock_s3client
    mock_s3client.list_objects.return_value = s3_response

    # Reset the @lru_cache so that we can mock the returned value. Without
    # this, only the first test to call _get_s3_client() would install a mock.
    runner._get_s3_client.cache_clear()

    # Ask the S3 client for the list of existing archives.
    existing_archives = runner._list_existing_archives(config)

    # Check that the client was called with the expeted params.
    mock_boto3.client.assert_called_with('s3')
    mock_s3client.list_objects.assert_called_with(
        Bucket=config.options.get('s3_bucket', '<NOT FOUND>'),
        Prefix=expected_prefix
    )

    return existing_archives

  def assert_assembled_prefix(self, inconfig: str, expected_prefix: str):
    """Helper that checks the prefix given a config file string."""
    # Call _list_existing_archives(), using the provided response when querying
    # S3.
    existing_archives = self.run_list_existing_archives(
        inconfig=inconfig,
        s3_response={
            'Contents': [
                {'Key': 'existing-archive-1'},
                {'Key': 'existing-archive-2'},
            ]
        },
        expected_prefix=expected_prefix,
    )

    # _list_existing_archives() should return the names provided in the
    # response message, in any order.
    expected_existing_archives = (
        'existing-archive-1',
        'existing-archive-2',
    )
    self.assertEqual(
        sorted(existing_archives),
        sorted(expected_existing_archives)
    )

  def test_prefix_with_all_fields(self):
    """Tests the prefix when s3_subpath and archive_prefix are set."""
    inconfig = textwrap.dedent("""
    [backups.test]
    s3_bucket = "s3-bucket"
    s3_subpath = "s3/sub/path"
    archive_prefix = "archive-prefix"
    src_dir = "<src-dir>"  # Required
    """)

    self.assert_assembled_prefix(
        inconfig=inconfig,
        expected_prefix='s3/sub/path/archive-prefix',
    )

  def test_prefix_with_no_s3_subpath(self):
    """Tests the generated prefix when only archive_prefix is set."""
    inconfig = textwrap.dedent("""
    [backups.test]
    s3_bucket = "s3-bucket"
    # No s3_subpath
    archive_prefix = "archive-prefix"
    src_dir = "<src-dir>"  # Required
    """)

    self.assert_assembled_prefix(
        inconfig=inconfig,
        expected_prefix='archive-prefix',
    )

  def test_prefix_with_no_archive_prefix(self):
    """Tests the generated prefix when only s3_subpath is set."""
    inconfig = textwrap.dedent("""
    [backups.test]
    s3_bucket = "s3-bucket"
    s3_subpath = "s3/sub/path"
    # No archive_prefix
    src_dir = "<src-dir>"  # Required
    """)

    self.assert_assembled_prefix(
        inconfig=inconfig,
        expected_prefix='s3/sub/path',
    )

  def test_prefix_with_no_prefix_fields(self):
    """Tests the prefix when neither s3_subpath nor archive_prefix are set."""
    inconfig = textwrap.dedent("""
    [backups.test]
    s3_bucket = "s3-bucket"
    # No s3_subpath
    # No archive_prefix
    src_dir = "<src-dir>"  # Required
    """)

    self.assert_assembled_prefix(
        inconfig=inconfig,
        expected_prefix='',
    )

  def test_missing_s3_bucket_fails(self):
    """Verifies that _list_existing_archives() fails without a bucket."""
    inconfig = textwrap.dedent("""
    [backups.test]
    # No s3_bucket
    s3_subpath = "s3/sub/path"
    archive_prefix = "archive-prefix"
    src_dir = "<src-dir>"  # Required
    """)

    self.assertRaisesRegex(
        runner.BackupError,
        's3_bucket',
        self.run_list_existing_archives,
        inconfig=inconfig,
        s3_response={'Contents': [{'Key': '<unused>'}]},
        expected_prefix='<unused>',
    )

  def test_empty_s3_bucket_fails(self):
    """Verifies that _list_existing_archives() fails with an empty bucket."""
    inconfig = textwrap.dedent("""
    [backups.test]
    s3_bucket = ""
    s3_subpath = "s3/sub/path"
    archive_prefix = "archive-prefix"
    src_dir = "<src-dir>"  # Required
    """)

    self.assertRaisesRegex(
        runner.BackupError,
        's3_bucket',
        self.run_list_existing_archives,
        inconfig=inconfig,
        s3_response={'Contents': [{'Key': '<unused>'}]},
        expected_prefix='<unused>',
    )

  def test_no_contents_in_response_fails(self):
    """Tests the behavior when the S3 response has no "Contents" key."""
    inconfig = textwrap.dedent("""
    [backups.test]
    s3_bucket = "s3-bucket"
    s3_subpath = "s3/sub/path"
    archive_prefix = "archive-prefix"
    src_dir = "<src-dir>"  # Required
    """)

    self.assertRaisesRegex(
        runner.BackupError,
        'Missing.*Contents',
        self.run_list_existing_archives,
        inconfig=inconfig,
        s3_response={},
        expected_prefix='<unused>',
    )

  def test_missing_key_keeps_going(self):
    """Tests the behavior when a 'Key' is missing from the S3 response."""
    inconfig = textwrap.dedent("""
    [backups.test]
    s3_bucket = "s3-bucket"
    s3_subpath = "s3/sub/path"
    archive_prefix = "archive-prefix"
    src_dir = "<src-dir>"  # Required
    """)
    # Reply with contents where one entry doesn't have 'Key'. The other entries
    # should still be returned.
    existing_archives = self.run_list_existing_archives(
        inconfig=inconfig,
        s3_response={
            'Contents': [
                {'No-key-present': 'existing-archive-1'},
                {'Key': 'existing-archive-2'},
            ]
        },
        expected_prefix='s3/sub/path/archive-prefix',
    )

    expected_existing_archives = (
        'existing-archive-2',
    )
    self.assertEqual(
        sorted(existing_archives),
        sorted(expected_existing_archives),
    )


class TestCreateLocalArchive(unittest.TestCase):
  """Tests for backups.runner._create_local_archive()."""

  @mock.patch('backups.runner.tarfile.open')
  def test_success(self, mock_tarfile_open):
    """Tests successful archive creation."""
    out_dir = '/outdir'
    archive_base = 'archive.tar'
    src_dir = '/src_dir'
    file_list = (
        'file1',
        'dir1/file2',
    )

    # Create the archive and check the returned path.
    archive_path = runner._create_local_archive(
        out_dir=out_dir,
        archive_base=archive_base,
        src_dir=src_dir,
        file_list=file_list,
    )
    self.assertEqual(archive_path, '/outdir/archive.tar')

    # Check that the archive was opened as expected.
    mock_tarfile_open.assert_called_with(
        name='/outdir/archive.tar',
        mode=f'x:{runner.COMPRESSION_TYPE}',
    )

    # The archive is returned via a "with/as" context manager; reach into
    # the mock tarfile.open to find it.
    mock_archive = mock_tarfile_open.return_value.__enter__.return_value

    # Check that expected files were added.
    mock_archive.add.assert_has_calls(
        calls=(
            mock.call(
                name='/src_dir/file1',
                arcname='file1',
                recursive=False,
            ),
            mock.call(
                name='/src_dir/dir1/file2',
                arcname='dir1/file2',
                recursive=False,
            ),
        ),
        any_order=True,
    )


class TestUploadFile(unittest.TestCase):
  """Tests for backups.runner._upload_file()."""

  @mock.patch('backups.runner.boto3')
  def test_successful_upload(self, mock_boto3):
    """Tests a successful upload."""
    inconfig = textwrap.dedent("""
    [backups.test]
    s3_bucket = "s3-bucket"
    s3_subpath = "s3/sub/path"
    src_dir = "<src-dir>"  # Required
    """)
    configs = backup_config.read(io.StringIO(inconfig))
    self.assertEqual(len(configs), 1)
    config = configs[0]

    # A fake S3 client to upload to.
    mock_s3client = mock.MagicMock()
    mock_boto3.client.return_value = mock_s3client

    # Reset the @lru_cache so that we can mock the returned value. Without
    # this, only the first test to call _get_s3_client() would install a mock.
    runner._get_s3_client.cache_clear()

    # One of the log statements calls getsize(), which won't work on a fake
    # path. Mock it out during the call.
    with mock.patch('backups.runner.os.path.getsize', return_value=0) as _:
      # Upload a file.
      runner._upload_file(
          config=config,
          local_file='/some/path/archive.tar',
      )

    # Verify that the expected file was uploaded to the expected place.
    mock_s3client.upload_file.assert_called_once_with(
        Filename='/some/path/archive.tar',
        Bucket='s3-bucket',
        Key='s3/sub/path/archive.tar',  # s3_subpath + basename(local_file)
    )

  @mock.patch('backups.runner.boto3')
  def test_successful_upload_without_s3_subpath(self, mock_boto3):
    """Tests a successful upload without a subpath."""
    inconfig = textwrap.dedent("""
    [backups.test]
    s3_bucket = "s3-bucket"
    # No s3_subpath
    src_dir = "<src-dir>"  # Required
    """)
    configs = backup_config.read(io.StringIO(inconfig))
    self.assertEqual(len(configs), 1)
    config = configs[0]

    # A fake S3 client to upload to.
    mock_s3client = mock.MagicMock()
    mock_boto3.client.return_value = mock_s3client

    # Reset the @lru_cache so that we can mock the returned value. Without
    # this, only the first test to call _get_s3_client() would install a mock.
    runner._get_s3_client.cache_clear()

    # One of the log statements calls getsize(), which won't work on a fake
    # path. Mock it out during the call.
    with mock.patch('backups.runner.os.path.getsize', return_value=0) as _:
      # Upload a file.
      runner._upload_file(
          config=config,
          local_file='/some/path/archive.tar',
      )

    # Verify that the expected file was uploaded to the expected place.
    mock_s3client.upload_file.assert_called_once_with(
        Filename='/some/path/archive.tar',
        Bucket='s3-bucket',
        Key='archive.tar',  # basename(local_file); no s3_subpath
    )

  def test_upload_without_bucket_fails(self):
    """Tests that uploading without an S3 bucket fails."""
    inconfig = textwrap.dedent("""
    [backups.test]
    # No s3_bucket
    s3_subpath = "s3/sub/path"
    src_dir = "<src-dir>"  # Required
    """)
    configs = backup_config.read(io.StringIO(inconfig))
    self.assertEqual(len(configs), 1)
    config = configs[0]

    self.assertRaisesRegex(
        runner.BackupError,
        's3_bucket must be set',
        runner._upload_file,
        config=config,
        local_file='/some/path/archive.tar',
    )


class TestDoBackup(unittest.TestCase):
  """Tests for backups.runner.do_backup()."""


if __name__ == '__main__':
  unittest.main()
