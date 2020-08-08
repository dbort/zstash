#!/usr/bin/env python3
# Copyright 2020 David Bort <git@dbort.com>
# Use of this source code is governed by a MIT-style license that can be found
# in the LICENSE file or at https://opensource.org/licenses/MIT

r"""A simple tool for backing up to S3.

Usage:
  simple-backups [-v|--verbose] [-d|--dry_run] \
      --config=<config-file> [--config=<config-file>]
"""

import argparse
from backups import config as backup_config
from backups import runner
import datetime
import logging
import traceback
import typing
import sys


def _parse_args(argv: typing.Sequence[str]) -> argparse.Namespace:
  """Parses commandline arguments.

  Args:
    argv: sys.argv or equivalent
  Returns:
    A Namespace describing the arguments.
  """
  parser = argparse.ArgumentParser(description='Back up local files to S3')
  parser.add_argument(
      '--config', action='append', required=True,
      help='Path to a TOML config file')
  parser.add_argument('--verbose', '-v', default=False, action='store_true')
  parser.add_argument('--dry_run', '-d', default=False, action='store_true')
  return parser.parse_args(argv[1:])


def main(argv: typing.Sequence[str]) -> int:
  # Parse args.
  args = _parse_args(argv)
  if args.verbose:
    logging.getLogger().setLevel(logging.DEBUG)

  # Read backup configs from config files.
  configs: typing.List[backup_config.BackupConfig] = []
  for config in args.config:
    logging.debug(f'Reading config from {config}')
    with open(config, 'r') as infile:
      configs.extend(backup_config.read(infile))

  # Perform the backups. Keep going even if one fails.
  failures = 0
  for config in configs:
    try:
      logging.info(f'Performing backup for [backups.{config.name}]')
      now = datetime.datetime.now(datetime.timezone.utc)
      runner.do_backup(config, now, dry_run=args.dry_run)
      logging.info(f'Done backing up [backups.{config.name}]')
    except Exception as e:
      logging.error(traceback.format_exc())
      logging.error(f'Failed while backing up [backups.{config.name}]: {e}')
      failures += 1

  # Make the process exit with an error if any of the backups failed.
  return failures


if __name__ == '__main__':
  logging.basicConfig(
      level=logging.INFO,
      format='%(asctime)s %(levelname).1s %(name)s] %(message)s',
      datefmt='%y%m%d %H:%M:%S%Z',
  )
  sys.exit(main(sys.argv))
