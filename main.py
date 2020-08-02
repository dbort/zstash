#!/usr/bin/env python3

from gitignore_parser import parse_gitignore
import os
import sys
import toml
from typing import Sequence

#xxx os.envion["FOUNDRY_ROOT"] = "..."
#xxx can use os.path.expandvars(str) to expand env vars
config = r'''
[env]
FOUNDRY_ROOT="${HOME}/.local/share/FoundryVTT"

[config]
log_path="${HOME}/var/log/backup-foundry.log"

[backups]
s3_bucket="backup-collar-different-hide"

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


def read_config() -> dict:
  return toml.loads(config)


def expand_vars(config: dict):
  old_env = os.environ.copy()
  try:
    # Define vars specified in the config, whose values may themselves
    # contain ${vars}.
    for name, value in config.get('env', {}).items():
      expanded = os.path.expandvars(value)
      config['env'][name] = expanded
      os.environ[name] = expanded
    # Expand strings in all other sections.
  finally:
    os.environ.clear()
    os.environ.update(old_env)


def main(args: Sequence):
  config = read_config()
  expand_vars(config)
  print(config)


if __name__ == '__main__':
  main(sys.argv)
