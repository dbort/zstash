#!/usr/bin/env python3

import collections.abc
import expandvars
from gitignore_parser import parse_gitignore
import logging
import os
import sys
import toml
import typing

# Alias for the config dictionary's type.
ConfigDict = typing.MutableMapping[str, typing.Any]

config = r'''
[env]
FOUNDRY_ROOT="${HOME}/.local/share/FoundryVTT"

[config]
log_path="${HOME}/var/log/backup-foundry.log"

[backups]
s3_bucket="backup-collar-different-hide"

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


class ConfigError(Exception):
  def __init__(self, message: str):
    self.message = message


def read_config() -> ConfigDict:
  try:
    return toml.loads(config)
  except toml.decoder.TomlDecodeError as e:
    raise ConfigError(f'Error while parsing config file: {e}')


def expand_vars(config: ConfigDict):
  """Expands environment variables in the config.

  If an 'env' section is present in the config, its keys/values extend the
  environment during this expansion. All members of the 'env' section must
  have string values.
  """
  def expand_dict(d):
    """Recursively expands environment vars in all string values in the dict."""
    for k, v in d.items():
      if isinstance(v, collections.abc.Mapping):
        expand_dict(v)
      elif isinstance(v, str):
        d[k] = expandvars.expandvars(v, nounset=True)
        
  old_env = os.environ.copy()  # Save so we can restore it later.
  try:
    # Define env vars specified in the config, whose values may themselves
    # contain ${vars}. Do them in order in case one uses a value defined before
    # it.
    if 'env' in config:
      for name, value in config.get('env', {}).items():
        if not isinstance(value, str):
          raise ConfigError(
            f'[env] section contains entry "{name}" whose value ' +
            f'is not a string: {repr(value)}')
        expanded = expandvars.expandvars(value, nounset=True)
        config['env'][name] = expanded
        os.environ[name] = expanded
      # Don't re-expand these; don't need them anymore anyway.
      del config['env']
    # Expand strings in all other sections.
    expand_dict(config)
  except expandvars.UnboundVariable as e:
    raise ConfigError(f'Error while expanding variables: {e}')
  finally:
    # Restore the original environment before returning or raising.
    os.environ.clear()
    os.environ.update(old_env)


def get_backup_configs(config: ConfigDict) -> ConfigDict:
  """Returns a mapping of [backups.<name>] names to configs.

  Each entry will inherit from but override elements from the top-level
  [backups] section.
  """
  # The root [backups] section, parent of specific backups.
  root = config.get('backups')
  if not root:
    return []

  # Split [backups] into backups and everything else.
  backups = {}  # The [backups.*] sub-dicts.
  base = {}  # `root` without the sub-dicts.
  for k, v in root.items():
    if isinstance(v, collections.abc.Mapping):
      backups[k] = v
    else:
      base[k] = v

  # Make backups inherit from (but override) base.
  for k, v in backups.items():
    n = base.copy()
    n.update(v)
    backups[k] = n
  return backups


def main(args: typing.Sequence) -> int:
  #xxx run paths through os.expanduser() for ~
  try:
    config = read_config()
    expand_vars(config)
  except ConfigError as e:
    logging.critical(f'Failed while reading config: {e}')
    return 1
  backups = get_backup_configs(config)
  print(backups)
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv))
