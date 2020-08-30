#!/bin/bash
# Copyright 2020 Dave Bort <git@dbort.com>
# Use of this source code is governed by a MIT-style license that can be found
# in the LICENSE file or at https://opensource.org/licenses/MIT

# Runs tests and lint checks.
# Run 'pip3 install -r requirements-dev.txt' first.

set -eu
set -o pipefail

# TODO: Add a flag to run coverage.
# pip3 install coverage
# coverage run --source=zstash -m pytest --pyargs zstash
# coverage report
# coverage html

main() {
  echo '[test]'
  pytest --pyargs zstash
  echo '[flake8]'
  flake8 . && echo 'OK'
  echo '[mypy]'
  mypy . && echo 'OK'
  # echo '[pyre]'
  # pyre check && echo 'OK'
}

main "$@"
