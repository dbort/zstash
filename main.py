#!/usr/bin/env python3

import backups
from backups.config import ConfigDict
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

def do_backup(name: str, config: ConfigDict, dry_run: bool=False):
  logging.info(f'Preparing backup config [{name}]')
  logging.info(config)


def main(args: typing.Sequence) -> int:
  #xxx run paths through os.expanduser() for ~
  bb = backups.config.read(io.StringIO(raw_config))
  for name, backup in bb.items():
    do_backup(name, backup)
  return 0


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO)
  sys.exit(main(sys.argv))
