#!/usr/bin/env python3

from backups.config import ConfigDict, BackupConfig
import boto3
from datetime import datetime
from functools import lru_cache
import hashlib
import logging
import tempfile
import typing
import os
import zipfile


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


@lru_cache(None)
def _get_s3_client():
  """Returns the S3 client singleton."""
  return boto3.client('s3')


def _list_existing_archives(config: BackupConfig) -> typing.Sequence[str]:
  """Returns the paths of existing archives that match the config.

  Args:
    config: The backup config
  Returns:
    A sequence of paths, relative to the backup destination.
  """
  # Assemble the prefix to existing archives.
  parts = [
    config.options.get('s3_subpath'),
    config.options.get('archive_prefix'),
  ]

  response = _get_s3_client().list_objects(
      Bucket=config.options['s3_bucket'],
      Prefix='/'.join([p for p in parts if p]),
  )
  if 'Contents' not in response:
    return tuple()
  try:
    return tuple([c['Key'] for c in response['Contents']])
  except KeyError as e:
    logging.error(f'Failed to parse S3 response: {e}:\n{response}')


def _upload_archive(config: BackupConfig, local_archive: str):
  """Uploads the local archive to the backup destination."""
  parts = [
      config.options.get("s3_subpath"),
      os.path.basename(local_archive),
  ]
  object_name = '/'.join([p for p in parts if p])

  s3_bucket = config.options['s3_bucket']
  logging.info(
      f'Uploading\n  {local_archive}\nto' +
      f'\n  s3://{s3_bucket}/{object_name}...'
  )
  response = _get_s3_client().upload_file(
      Filename=local_archive,
      Bucket=s3_bucket,
      Key=object_name,
  )
  logging.info('Upload complete.')



def _create_local_archive(
    config: BackupConfig,
    archive_base: str,
    file_list: typing.Sequence[str],
    tmpdir: str,
) -> str:
  """Creates an archive of the specified files in a local temp dir.

  Returns:
    The path to the archive.
  """
  local_archive = os.path.join(tmpdir, archive_base)

  # TODO: Preserve owner/permissions. May be easiest to use the
  # commandline tool; see https://serverfault.com/a/901142 for file lists.
  logging.debug(f'Creating local archive {local_archive}...')
  with zipfile.ZipFile(
      file=local_archive, mode='w', compression=zipfile.ZIP_DEFLATED
  ) as archive:
    src_dir = config.src_dir
    logging.info(f'Archiving under {src_dir}...')
    for f in file_list:
      logging.info(f'Archiving {f}...')
      archive.write(
          filename=os.path.join(config.src_dir, f),
          arcname=f
      )
  logging.debug(f'Created local archive.')

  return local_archive


def do_backup(config: BackupConfig, now: datetime, dry_run: bool=False):
  # Get the list of files to archive.
  logging.debug('Getting list of files to archive...')
  if not os.path.exists(config.src_dir):
    raise BackupError(config.name, f"src_dir {config.src_dir} does not exist")
  file_list = _build_file_list(config)
  logging.debug('File list:\n  ' + '\n  '.join(file_list))

  # Hash the files.
  logging.debug('Hashing files...')
  tree_hash = _hash_files(config.src_dir, file_list)
  logging.debug(f'Hash: {tree_hash}')

  # If there's already an archive with this hash, we're done.
  logging.debug('Getting existing archives...')
  existing_archives = _list_existing_archives(config)
  logging.debug(
      f'Found {len(existing_archives)} archives:\n  ' +
      '\n  '.join(existing_archives)
  )
  for ea in existing_archives:
    if tree_hash in ea:
      logging.info(
          f'Skipping backup: Found existing archive with matching hash: ' +
          f's3://{config.options["s3_bucket"]}/{ea}'
      )
      return

  # Determine the name of the archive file.
  date = f'{now.replace(microsecond=0).isoformat()}'
  archive_base = (
      f'{config.options.get("archive_prefix", "")}{date}-{tree_hash}.zip')

  with tempfile.TemporaryDirectory() as tmpdir:
    # Create a local archive of the files.
    local_archive = _create_local_archive(
        config, archive_base, file_list, tmpdir)

    # Upload it.
    _upload_archive(config, local_archive)

  # Done!
