#!/bin/bash
# Copyright 2020 David Bort <git@dbort.com>
# Use of this source code is governed by a MIT-style license that can be found
# in the LICENSE file or at https://opensource.org/licenses/MIT

# Runs tests and lint checks.

set -eu
set -o pipefail

main() {
  echo '[test]'
  python3 -m unittest discover --verbose
  echo '[flake8]'
  flake8 . && echo 'OK'
  echo '[mypy]'
  mypy . && echo 'OK'
  echo '[pyre]'
  pyre check && echo 'OK'
}

main "$@"
