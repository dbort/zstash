#!/usr/bin/env python3

from backups import config as backup_config
from backups import runner
import datetime
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

[backups.test]
s3_subpath="test"
archive_prefix="test-"

src_dir="~/src/simple-backups"
ignore="""
.git
.mypy_cache
.pyre*
__pycache__/
"""
'''

'''

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


def main(args: typing.Sequence) -> int:
  # xxx listen to log_path (and run it through expanduser())
  configs = backup_config.read(io.StringIO(raw_config))
  now = datetime.datetime.now(datetime.timezone.utc)
  for config in configs:
    logging.info(f'Performing backup for [backups.{config.name}]')
    runner.do_backup(config, now)
    logging.info(f'Done backing up [backups.{config.name}]')
  return 0


if __name__ == '__main__':
  logging.getLogger().setLevel(logging.INFO)
  sys.exit(main(sys.argv))
