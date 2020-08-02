#!/usr/bin/env python3

from backups.config import ConfigDict, BackupConfig
import logging
import typing
import os

def build_file_list(config: BackupConfig) -> typing.Iterable[str]:
  for root, dirs, files in os.walk(config.src_dir):
    ignored = [
        d for d in dirs if config.should_ignore(os.path.join(root, d))
    ]
    for i in ignored:
      dirs.remove(i)
    for f in files:
      abs_path = os.path.join(root, f)
      if not config.should_ignore(abs_path):
        yield os.path.relpath(abs_path, config.src_dir)


def do_backup(config: BackupConfig, dry_run: bool=False):
  logging.info(f'Preparing backup config [{config.name}]')
  logging.info(config.options)
  file_list = build_file_list(config)
  s = '\n  '.join(file_list)
  logging.info(f"Files:\n  {s}")
