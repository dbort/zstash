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

  def test_smoke(self):
    # need to mock boto3.client('s3') and s3.list_objects(Bucket, Prefix)
    pass

  # TODO:
  # Combinations of s3_subpath and archive_prefix being present
  # s3_bucket missing
  # bad response, no Contents or Contents.Key
  # Also test this and the "archive already exists" logic


if __name__ == '__main__':
  unittest.main()
