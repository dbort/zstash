#!/usr/bin/env python3
# Copyright 2020 David Bort <git@dbort.com>
# Use of this source code is governed by a MIT-style license that can be found
# in the LICENSE file or at https://opensource.org/licenses/MIT

"""Loads and validates backup config files."""

import collections.abc
import copy
import expandvars  # type: ignore  # No type stubs available
import gitignore_parser  # type: ignore  # No type stubs available
import os
import toml
import typing

# Alias for the config dictionary's type.
ConfigDict = typing.MutableMapping[str, typing.Any]

# Allowed top-level [section] names.
VALID_SECTION_NAMES = {'env', 'backups'}


class ConfigError(Exception):
  def __init__(self, message: str):
    self.message = message


class BackupConfig:
  """Describes the source of a backup.

  Attributes:
    name: Name of the backup, corresponding to "[backups.<name>]" in the
        config file.
    src_dir: The directory to back up.
    options: Config options as a mapping of strings to values.
    should_ignore: A function `should_ignore(path)->bool` that returns True if
        the provided path should be ignored (skipped) while backing up.
  """
  name: str
  src_dir: str
  options: ConfigDict

  # https://github.com/python/mypy/issues/708
  # should_ignore: typing.Callable[[str], bool]

  def __init__(self, name: str, options: ConfigDict):
    for k, v in options.items():
      if not isinstance(v, str):
        raise ConfigError(
            f'[backups.{name}] entry "{k}" has non-string value ({repr(v)})'
        )

    self.name = name
    self.options = copy.deepcopy(dict(options))
    if 'src_dir' not in options:
      raise ConfigError(f'Section [backups.{name}] missing "src_dir"')
    # Expand '~' or '~user' into a full path now so no-one else needs to worry
    # about it.
    self.src_dir = os.path.expanduser(options['src_dir'])
    del self.options['src_dir']

    if 'ignore' in options:
      self.should_ignore = _parse_gitignore(
          options['ignore'], self.src_dir)
      del self.options['ignore']
    else:
      self.should_ignore = lambda _: False


def _parse_gitignore(
    contents: str,
    base_dir: str,
) -> typing.Callable[[str], bool]:
  """Parses gitignore lines and returns a matcher function.

  Args:
    contents: The gitignore lines to parse.
    base_dir: The directory relative to which the gitignore rules should
        be applied.
  Returns:
    A function should_ignore(path) that returns True if the provided path
    should be ignored.
  """
  # The gitignore_parser module only accepts file paths. Mock out its call to
  # "open" so it will read our string no matter what path it opens.
  from unittest.mock import patch, mock_open
  with patch('builtins.open', mock_open(read_data=contents)):
    return gitignore_parser.parse_gitignore(
        full_path='<mocked>',
        base_dir=base_dir,
    )


def _read_config(infile: typing.TextIO) -> ConfigDict:
  """Reads and parses a backup config file."""
  try:
    config = toml.load(infile)
    unknown_sections = set(config.keys()) - VALID_SECTION_NAMES
    if unknown_sections:
      raise ConfigError('Unknown section(s): {}'.format(
          ', '.join([f'[{s}]' for s in unknown_sections])
      ))
    return config
  except toml.decoder.TomlDecodeError as e:  # type: ignore
    raise ConfigError(f'Error while parsing config file: {e}')


def _expand_vars(config: ConfigDict):
  """Expands environment variables in config value strings.

  If an 'env' section is present in the config, its keys/values extend the
  environment during this expansion. All members of the 'env' section must have
  string values.
  """
  def expand_dict(d):
    """Recursively expands env vars in all string values in the dict."""
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
              f'[env] section contains entry "{name}" whose value '
              + f'is not a string: {repr(value)}'
          )
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


def _get_backup_configs(config: ConfigDict) -> typing.Sequence[BackupConfig]:
  """Returns BackupConfigs describing [backups.<name>] entries of the config.

  Each entry will inherit from but override elements from the top-level
  [backups] section.
  """
  # The root [backups] section, parent of specific backups.
  root = config.get('backups')
  if not root:
    return tuple()

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
  return tuple(BackupConfig(k, v) for k, v in backups.items())  # type: ignore


def read(config_file: typing.TextIO) -> typing.Sequence[BackupConfig]:
  """Parses the provided config file and returns the backup configs.

  Args:
    config_file: An open text file to read the config from.
  Returns:
    A mapping from backup names ([backups.<backup name>]) to backup
    config dicts.
  """
  config = _read_config(config_file)
  _expand_vars(config)
  configs = _get_backup_configs(config)
  if not configs:
    raise ConfigError('No [backups.<name>] sections present')
  return configs
