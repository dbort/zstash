#!/usr/bin/env python3
"""Support for executing a backup config."""

from backups.config import BackupConfig
import boto3  # type: ignore  # No type stubs available
from datetime import datetime
from functools import lru_cache
import hashlib
import logging
import tarfile
import tempfile
import typing
import os

# The archive container type. Only 'tar' is currently supported.
# TODO: Let the config override this if we ever support more formats.
ARCHIVE_FORMAT: str = 'tar'

# The archive compression type. One of (gz, bz2, xz), or empty for no
# compression.
# TODO: Let the config override this.
COMPRESSION_TYPE: str = 'bz2'

# The extension of the generated archive file.
ARCHIVE_EXTENSION: str = f'.{ARCHIVE_FORMAT}.{COMPRESSION_TYPE}'


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
      # TODO: Consider including the file permissions (rwxrwxrwx) in the hash
      # so that we re-archive if someone were to 'chmod +x'. Maybe watch the
      # owner/group, too.
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
    raise BackupError(config.name, 'Error reading from S3')


def _upload_file(
    config: BackupConfig, local_file: str, dry_run: bool = False
):
  """Uploads the local archive to the backup destination.

  Arg:
    config: The backup config. config.options['s3_bucket'] must be set
        to a non-empty string. config.options['s3_subpath'] is an optional
        prefix to the destination within the S3 bucket.
    local_file: Path to the local file to upload.
    dry_run: If truthy, do no actually upload the file to S3.
  """
  parts = [
      config.options.get("s3_subpath"),
      os.path.basename(local_file),
  ]
  object_name = '/'.join([p for p in parts if p])

  s3_bucket = config.options.get('s3_bucket')
  if not s3_bucket:
    raise BackupError(
        config.name,
        's3_bucket must be set to a non-empty string'
    )
  logging.info(
      f'Uploading\n  {local_file}\nto'
      + f'\n  s3://{s3_bucket}/{object_name}...'
  )
  if dry_run:
    logging.info("DRY RUN: Not uploading")
  else:
    _get_s3_client().upload_file(
        Filename=local_file,
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
  # Note: We use tar because it preserves file permissions and other metadata.
  # Python's zipfile module does not.
  assert ARCHIVE_FORMAT == 'tar'

  local_archive = os.path.join(tmpdir, archive_base)
  logging.debug(f'Creating local archive {local_archive}...')
  with tarfile.open(
      name=local_archive,
      # 'x' is like 'w' but raises an exception if the output file already
      # exists. Note that 'x:' is valid, and equivalent to 'x'.
      mode=f'x:{COMPRESSION_TYPE}'
  ) as archive:
    src_dir = config.src_dir
    logging.info(f'Archiving under {src_dir}...')
    for rel_path in file_list:
      logging.info(f'Archiving {rel_path}...')
      abs_path = os.path.join(config.src_dir, rel_path)
      archive.add(
          name=abs_path,
          arcname=rel_path,
          recursive=False,  # We already did the recursion.
      )
  logging.debug('Created local archive.')

  return local_archive


def do_backup(
    config: BackupConfig,
    now: datetime,
    dry_run: bool = False
) -> None:
  """Performs the backup described by the config.

  Args:
    config: The details of the backup to perform.
    now: The timestamp to consider to be "now".
    dry_run: If truthy, do everything except write to S3.
  """
  logging.debug('Getting list of files to archive...')
  if not os.path.exists(config.src_dir):
    raise BackupError(config.name, f"src_dir {config.src_dir} does not exist")
  file_list = _build_file_list(config)
  for f in file_list:
    logging.debug(f'+ {f}')

  logging.debug('Hashing files...')
  tree_hash = _hash_files(config.src_dir, file_list)
  logging.debug(f'Hash: {tree_hash}')

  # If there's already an archive with this hash, we're done.
  logging.debug('Getting existing archives...')
  existing_archives = _list_existing_archives(config)
  logging.debug(
      f'Found {len(existing_archives)} archives:\n  '
      + '\n  '.join(existing_archives)
  )
  for ea in existing_archives:
    if tree_hash in ea:
      logging.info(
          'Skipping backup: Found existing archive with matching hash: '
          + f's3://{config.options["s3_bucket"]}/{ea}'
      )
      return

  # Determine the name of the archive file.
  date = f'{now.replace(microsecond=0).isoformat()}'
  archive_base = (
      f'{config.options.get("archive_prefix", "")}'
      + f'{date}-{tree_hash}{ARCHIVE_EXTENSION}'
  )

  with tempfile.TemporaryDirectory() as tmpdir:
    # Create a local archive of the files.
    local_archive = _create_local_archive(
        config, archive_base, file_list, tmpdir)

    # Upload it.
    _upload_file(config, local_archive, dry_run=dry_run)

  # Done!
