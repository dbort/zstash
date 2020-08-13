#!/usr/bin/env python3
# Copyright 2020 David Bort <git@dbort.com>
# Use of this source code is governed by a MIT-style license that can be found
# in the LICENSE file or at https://opensource.org/licenses/MIT

"""Tests for backups.config."""

from zstash import config as backup_config
import io
import os
import textwrap
import typing
import unittest


def read_config_with_environment(
    inconfig: str,
    env: dict,
) -> typing.Sequence[backup_config.BackupConfig]:
    """Reads a config string using a known environment.

    Args:
      inconfig: The multi-line config file to read.
      env: A dict to use to replace the environment while reading.
    Returns:
      The results of backup_config.read().
    """
    old_env = os.environ.copy()
    try:
      os.environ.clear()
      os.environ.update(env)
      return backup_config.read(io.StringIO(inconfig))
    finally:
      os.environ.clear()
      os.environ.update(old_env)


class TestConfigs(unittest.TestCase):
  """General tests for config parsing/validation."""

  def test_minimal(self):
    """Reads a minimal config."""
    inconfig = textwrap.dedent("""
        [backups.test]
        src_dir = "test:src_dir"
        """)

    # Read the config file.
    configs = backup_config.read(io.StringIO(inconfig))

    # The file should produce a single config.
    self.assertEqual(len(configs), 1)
    self.assertEqual(configs[0].name, 'test')
    self.assertEqual(configs[0].src_dir, 'test:src_dir')

  def test_src_dir_required(self):
    """Tests that src_dir is required for a backup."""
    inconfig = textwrap.dedent("""
        [backups.test]
        """)

    # Reading the config file should raise a ConfigError because of the missing
    # src_dir.
    self.assertRaisesRegex(
        backup_config.ConfigError,
        'src_dir',
        backup_config.read,
        io.StringIO(inconfig),
    )

  def test_src_dir_tilde_expansion(self):
    """Tests that ~ expansion happens for src_dir."""
    inconfig = textwrap.dedent("""
        [backups.test]
        src_dir = "~/subdir"
        """)

    # Read the config file with a known envrionment.
    configs = read_config_with_environment(inconfig, {'HOME': '<home>'})

    # The file should produce a single config.
    self.assertEqual(len(configs), 1)
    self.assertEqual(configs[0].name, 'test')

    # The ~ should have been expanded to ${HOME}.
    self.assertEqual(configs[0].src_dir, '<home>/subdir')

  def test_no_backups_fails(self):
    """Verifies that a config with no backup sections fails."""
    # Defines an [env] section but no [backups.<name>] sections.
    env_only = textwrap.dedent("""
        [env]
        VAR = "x"
        """)
    # Defines a root [backups] section but no [backups.<name>] sections.
    backups_only = textwrap.dedent("""
        [backups]
        src_dir = "backups:src_dir"
        """)
    # Defines an [env] section and a root [backups] section but no
    # [backups.<name>] sections.
    env_and_backups_only = textwrap.dedent("""
        [env]
        VAR = "x"
        [backups]
        src_dir = "backups:src_dir"
        """)
    # Completely empty config.
    empty_config = ""

    for inconfig in (
        env_only,
        backups_only,
        env_and_backups_only,
        empty_config
    ):
      # Reading the config file should raise a ConfigError because of the
      # missing [backups.<name>] sections.
      self.assertRaisesRegex(
          backup_config.ConfigError,
          'No.*backup.*sections present',
          backup_config.read,
          io.StringIO(inconfig),
      )

  def test_inheritance(self):
    """Tests that backup sections inherit and override vars from [backups]."""
    inconfig = textwrap.dedent("""
        [backups]
        src_dir = "backups:src_dir"
        var1 = "backups:var1"
        [backups.test1]
        [backups.test2]
        src_dir = "test2:src_dir"
        [backups.test3]
        var1 = "test3:var1"
        extra = "test3:extra"
        """)

    # Read the config file.
    configs = backup_config.read(io.StringIO(inconfig))

    # The file should produce three configs.
    self.assertEqual(len(configs), 3)

    # The first config should have inherited everything from [backups]
    config = configs[0]
    self.assertEqual(config.name, 'test1')
    self.assertEqual(config.src_dir, 'backups:src_dir')
    self.assertEqual(config.options['var1'], 'backups:var1')

    # The second config should have inherited var1 from [backups] and
    # overridden src_dir.
    config = configs[1]
    self.assertEqual(config.name, 'test2')
    self.assertEqual(config.src_dir, 'test2:src_dir')
    self.assertEqual(config.options['var1'], 'backups:var1')

    # The third config should have inherited src_dir from [backups], overridden
    # var1, and defined an extra variable.
    config = configs[2]
    self.assertEqual(config.name, 'test3')
    self.assertEqual(config.src_dir, 'backups:src_dir')
    self.assertEqual(config.options['var1'], 'test3:var1')
    self.assertEqual(config.options['extra'], 'test3:extra')

    # The 'extra' variable should not appear in the other configs.
    self.assertNotIn('extra', configs[0].options)
    self.assertNotIn('extra', configs[1].options)

  def test_unknown_section_fails(self):
    """Tests that an unknown section name causes a failure."""
    inconfig = textwrap.dedent("""
        [backups.test]
        src_dir = "backups:src_dir"
        [unknown]
        extra = "extra"
        """)

    # Reading the config file should raise a ConfigError because of the unknown
    # section.
    self.assertRaisesRegex(
        backup_config.ConfigError,
        'Unknown section',
        backup_config.read,
        io.StringIO(inconfig),
    )

  def test_non_string_values_fail(self):
    """Tests that non-string values cause a failure."""
    # These are valid TOML but our validation rejects them.
    test_cases = (
        'non_string_number = 1',
        'native_date = 1979-05-27T07:32:00-08:00',
        'array = [ "a", "b", "c" ]',
        # A sub-dict of [backups.test].
        '[backups.test.subtest]\nvar = "var"',
    )

    for tc in test_cases:
      inconfig = textwrap.dedent(f"""
          [backups.test]
          {tc}
          """)

      # Reading the config file should raise a ConfigError because of the
      # non-string value type.
      self.assertRaisesRegex(
          backup_config.ConfigError,
          'non-string value',
          backup_config.read,
          io.StringIO(inconfig),
      )

  def test_bad_toml_fails(self):
    """Tests that invalid TOML syntax causes a failure."""
    inconfig = textwrap.dedent("""
        [backups
        """)

    # Reading the config file should raise a ConfigError because of the unknown
    # section.
    self.assertRaisesRegex(
        backup_config.ConfigError,
        'Error while parsing',
        backup_config.read,
        io.StringIO(inconfig),
    )


class TestExpandVars(unittest.TestCase):
  """Test variable expansion."""

  def test_smoke(self):
    """Tests variable expansion in a minimal valid config file layout."""
    inconfig = textwrap.dedent("""
        [env]
        SUBDIR = ".local/config"
        # Uses an externally-defined env var and a locally defined var.
        COMPOSED_PATH = "${HOME}/${SUBDIR}"
        [backups]
        backups_key = "backups_key:${COMPOSED_PATH}"
        src_dir = "<src_dir>"  # Required
        [backups.test1]
        backups_test1_key = "backups_test1_key:${COMPOSED_PATH}"
        [backups.test2]
        backups_test2_key = "backups_test2_key:${COMPOSED_PATH}"
        """)

    # Read the config file with a known envrionment.
    configs = read_config_with_environment(inconfig, {'HOME': '<home>'})

    # The file should produce two configs.
    self.assertEqual(len(configs), 2)
    self.assertEqual(configs[0].name, 'test1')
    self.assertEqual(configs[1].name, 'test2')

    # The value set in the [backups] section should have been expanded.
    self.assertEqual(
        configs[0].options['backups_key'],
        'backups_key:<home>/.local/config',
    )
    self.assertEqual(
        configs[1].options['backups_key'],
        'backups_key:<home>/.local/config',
    )

    # The value set in the [backups.testN] section should have been expanded.
    self.assertEqual(
        configs[0].options['backups_test1_key'],
        'backups_test1_key:<home>/.local/config',
    )
    self.assertEqual(
        configs[1].options['backups_test2_key'],
        'backups_test2_key:<home>/.local/config',
    )

  def test_no_env_section_ok(self):
    """Verifies that it's ok not to have an env section."""
    inconfig = textwrap.dedent("""
        [backups.test]
        src_dir = "${HOME}"
        """)

    # Read the config file with a known envrionment.
    configs = read_config_with_environment(inconfig, {'HOME': '<home>'})

    # The file should produce a single config.
    self.assertEqual(len(configs), 1)
    self.assertEqual(configs[0].name, 'test')

    # The external environment variable should have been expanded.
    self.assertEqual(configs[0].src_dir, '<home>')

  def test_expansion_styles(self):
    """Tests different ways of specifying variable expansion."""
    inconfig = textwrap.dedent("""
        [env]
        SUBDIR = ".local/config"
        [backups.test]
        src_dir = "<src_dir>"  # Required
        test1 = "test1:${SUBDIR}"
        test2 = "test2:$SUBDIR"
        test3 = "test3:${SUBDIR:-default}"
        test4 = "test4:${UNDEFINED:-default}"
        """)

    # Reading the config file should produce a single config.
    configs = backup_config.read(io.StringIO(inconfig))
    self.assertEqual(len(configs), 1)
    self.assertEqual(configs[0].name, 'test')

    options = configs[0].options
    # ${VAR} expansion should work.
    self.assertEqual(options['test1'], 'test1:.local/config')
    # $VAR expansion should work.
    self.assertEqual(options['test2'], 'test2:.local/config')
    # ${VAR:-default} expansion should expand to VAR when present.
    self.assertEqual(options['test3'], 'test3:.local/config')
    # ${VAR:-default} expansion should expand to the default when VAR is
    # undefined, and should not raise an UnboundVariable exception.
    self.assertEqual(options['test4'], 'test4:default')

  def test_unbound_variable_raises(self):
    """Tests the behavior when an expanded variable isn't bound."""
    inconfig = textwrap.dedent("""
        [backups.test]
        src_dir = "${UNDEFINED}"
        """)

    # Reading the config file should raise a ConfigError because of the unbound
    # variable.
    self.assertRaisesRegex(
        backup_config.ConfigError,
        'unbound variable',
        backup_config.read,
        io.StringIO(inconfig),
    )

  def test_non_string_env_raises(self):
    """Tests the behavior when an env var has a non-string value."""
    inconfig = textwrap.dedent("""
        [env]
        # A number, not a string.
        COUNT = 4
        [backups.test]
        src_dir = "${COUNT}"
        """)

    # Reading the config file should raise a ConfigError because of the
    # non-string value.
    self.assertRaisesRegex(
        backup_config.ConfigError,
        'value is not a string',
        backup_config.read,
        io.StringIO(inconfig),
    )


class TestGitignore(unittest.TestCase):
  # Test that we've hooked up gitignore parsing correctly. Don't bother testing
  # all aspects of gitignore semantics; trust gitignore_parser and its tests.

  def test_smoke(self):
    """Tests that gitignore sections affect should_ignore()."""
    inconfig = textwrap.dedent("""
        [backups.test]
        src_dir = "srcdir"
        ignore = '''
        ignored
        '''
        """)

    # Read the config file with a known envrionment.
    configs = backup_config.read(io.StringIO(inconfig))

    # The file should produce a single config.
    self.assertEqual(len(configs), 1)
    self.assertEqual(configs[0].name, 'test')
    config = configs[0]

    # Check a path that should be ignored and one that shouldn't.
    self.assertTrue(config.should_ignore('srcdir/ignored'))
    self.assertFalse(config.should_ignore('srcdir/kept'))

  def test_env_expansion_in_ignore(self):
    """Tests that env expansion happens in ignore entries."""
    inconfig = textwrap.dedent("""
        [env]
        TO_IGNORE = "ignored"
        [backups.test]
        src_dir = "srcdir"
        ignore = '''
        ${TO_IGNORE}
        '''
        """)

    # Read the config file with a known envrionment.
    configs = backup_config.read(io.StringIO(inconfig))

    # The file should produce a single config.
    self.assertEqual(len(configs), 1)
    self.assertEqual(configs[0].name, 'test')
    config = configs[0]

    # Check a path that should be ignored and one that shouldn't.
    self.assertTrue(config.should_ignore('srcdir/ignored'))
    self.assertFalse(config.should_ignore('srcdir/kept'))


if __name__ == '__main__':
  unittest.main()
