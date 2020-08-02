#!/usr/bin/env python3

from backups.config import ConfigDict, BackupConfig
import logging


def do_backup(config: BackupConfig, dry_run: bool=False):
  logging.info(f'Preparing backup config [{config.name}]')
  logging.info(config.options)
  p = config.src_dir + '/line1'
  logging.info(f'should ignore {p}? {config.should_ignore(p)}')
  p = config.src_dir + '/line10'
  logging.info(f'should ignore {p}? {config.should_ignore(p)}')
  p = config.src_dir + '/lineXX'
  logging.info(f'should ignore {p}? {config.should_ignore(p)}')
