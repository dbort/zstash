#!/usr/bin/env python3

from setuptools import setup  # type: ignore  # No type stubs available


def readme():
  with open('README.rst') as f:
    return f.read()


setup(
    name='zstash',
    version='1.0',
    description='Basic backups to S3',
    long_description=readme(),
    # https://pypi.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: System :: Archiving :: Backup',
    ],
    keywords='backup archive cron S3 s3',
    url='http://github.com/dbort/zstash',
    author='Dave Bort',
    author_email='git@dbort.com',
    license='MIT',
    packages=['zstash'],
    install_requires=[
        'boto3',
        'expandvars',
        'gitignore-parser',
        'toml',
    ],
    include_package_data=True,
    entry_points = {
        'console_scripts': ['zstash=zstash.command_line:main'],
    },
    zip_safe=False,
)
