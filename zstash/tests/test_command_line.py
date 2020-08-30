#!/usr/bin/env python3
# Copyright 2020 Dave Bort <git@dbort.com>
# Use of this source code is governed by a MIT-style license that can be found
# in the LICENSE file or at https://opensource.org/licenses/MIT

"""Tests for zstash.command_line."""

from zstash import command_line
import unittest


class TestCommandLine(unittest.TestCase):

  def test_smoke(self):
    pass

# TODO: Mock out configs/runner, invoke through main()


if __name__ == '__main__':
  unittest.main()
