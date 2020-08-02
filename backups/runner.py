#!/usr/bin/env python3

from backups.config import ConfigDict, BackupConfig
import hashlib
import logging
import typing
import os

class BackupError(Exception):
  """Raised when an error occurs while performing a backup."""
  def __init__(self, name: str, message: str):
    self.message = f"Error while backing up [backups.{name}]: {message}"


def _build_file_list(config: BackupConfig) -> typing.Sequence[str]:
  """Returns the list of files specified by the config.

  Args:
    config: The config to use to find the files.
  Returns:
    A sequence of file paths relative to config.src_dir.
  """
  out_files = []
  for root, dirs, files in os.walk(config.src_dir):
    ignored = [
        d for d in dirs if config.should_ignore(os.path.join(root, d))
    ]
    for i in ignored:
      dirs.remove(i)
    for f in files:
      abs_path = os.path.join(root, f)
      if not config.should_ignore(abs_path):
        out_files.append(os.path.relpath(abs_path, config.src_dir))
  return tuple(out_files)


def _hash_files(base_dir: str, files: typing.Sequence[str]) -> str:
  """Hashes the named files and returns a hex checksum.

  The hash is stable for a given set of relative file paths and contents. Does
  not look at any file metadata like timestamps or owners.

  This means that the same set of files could live in any absolute location,
  and as long as their contents and relative paths are the same, they will
  produce the same hash.

  Args:
    base_dir: The path that the file paths are relative to.
    files: The files to hash, relative to base_dir.
  Returns:
    A hex checksum string.
  """
  out_hash = hashlib.sha256()
  for rel_path in sorted(files):
    abs_path = os.path.join(base_dir, rel_path)
    with open(abs_path, 'rb') as f:
      file_hash = hashlib.sha256()
      while True:
        buf = f.read(4096)
        if not buf:
          break
        file_hash.update(buf)
      # Hash the relative filename and the hex digest of the file. We don't
      # put the file contents directly into out_hash; if we did, a single file
      # consisting of all file contents and names concatenated together could
      # produce the same hash as a tree of files.
      out_hash.update(rel_path.encode('utf-8'))
      out_hash.update(file_hash.hexdigest().encode('utf-8'))
  return out_hash.hexdigest()


def do_backup(config: BackupConfig, dry_run: bool=False):
  logging.info(f'Preparing backup config [backups.{config.name}]')
  if not os.path.exists(config.src_dir):
    raise BackupError(config.name, f"src_dir {config.src_dir} does not exist")
  file_list = _build_file_list(config)
  tree_hash = _hash_files(config.src_dir, file_list)
  logging.info(f'Hash: {tree_hash}')

  # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-uploading-files.html

  # - List existing backups (s3 util)
  # - Quit if hash already exists
  # - Assemble archive name
  # - Create the archive (archive util)
  # - Upload to S3 (s3 util)
