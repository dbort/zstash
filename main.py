#!/usr/bin/env python3

import backups
from backups.config import ConfigDict, BackupConfig
import io
import logging
import typing
import sys

raw_config = r'''
[env]
FOUNDRY_ROOT="${HOME}/.local/share/FoundryVTT"

[backups]
s3_bucket="backup-collar-different-hide"
log_path="${HOME}/var/log/backup-foundry.log"

# Can also have an "ignore=..." here that will be inherited.

[backups.worlds]
s3_subpath="foundry/worlds"
archive_prefix="foundry-worlds-"

src_dir="${FOUNDRY_ROOT}/Data/worlds"
ignore="""
line1
line2
"""

[backups.config]
s3_subpath="foundry/config"
archive_prefix="foundry-config-"

src_dir="${FOUNDRY_ROOT}/Config"
ignore="""
"""
'''

def do_backup(config: BackupConfig, dry_run: bool=False):
  logging.info(f'Preparing backup config [{config.name}]')
  logging.info(config.options)
  p = config.src_dir + '/line1'
  logging.info(f'should ignore {p}? {config.should_ignore(p)}')
  p = config.src_dir + '/line10'
  logging.info(f'should ignore {p}? {config.should_ignore(p)}')
  p = config.src_dir + '/lineXX'
  logging.info(f'should ignore {p}? {config.should_ignore(p)}')


def main(args: typing.Sequence) -> int:
  #xxx run paths through os.expanduser() for ~
  configs = backups.config.read(io.StringIO(raw_config))
  for config in configs:
    do_backup(config)
  return 0


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO)
  sys.exit(main(sys.argv))
