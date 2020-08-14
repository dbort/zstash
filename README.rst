The ``zstash`` tool backs up directory archives to S3 based on a TOML file
config. Archives will only be created and uploaded when the files have
changed.

Config file
-----------

``zstash`` config files are `TOML <https://toml.io/en/>`_ files that
describe one or more backup configs.

An example config file:

.. code-block:: toml

    # The environment is imported, but you can define your own variables
    # in the [env] section. Variables will be expanded in all strings
    # in the config file.
    [env]
    BASE_SUBDIR = "sub/dir"
    COMMON_BASE_DIR = "${HOME}/${BASE_SUBDIR}"  # HOME from the environment.


    # Definitions in the optional [backups] section will be inherited by all
    # backup configs. Backup configs can override values defined here.
    [backups]
    # s3_bucket: The bucket to upload to. Required.
    s3_bucket = "my-bucket-name"  # Inherited by the backup sections.


    # The config file must contain one or more [backups.<name>] sections. Each
    # will create a separate archive.
    [backups.config1]
    # Note that this config inherits s3_bucket from [backups].

    # archive_prefix: Prefix for the generated archive name, which will look
    # like "${archive_prefix}${date}-${hash}.tar.bz2". Optional.
    archive_prefix = "dir1-backup-"

    # s3_subdir: Subpath in the S3 bucket where the archive will live. Optional.
    s3_subdir = "s3/sub/path"

    # src_dir: The directory to archive and upload. Required.
    src_dir = "${COMMON_BASE_DIR}/dir1"

    # ignore: A gitignore-conforming set of file/directory patterns to ignore
    # when creating the archive. Optional.
    ignore = """
    __pycache__
    .git
    *.pyc
    *~
    """

    #
    # The above config will create an archive of the non-ignored files
    # under
    #
    #   ~/sub/dir/dir1
    #
    # with an archive name like
    #
    #   dir1-backup-2020-08-14T04:07:29+00:00-a2847b3ec04158f8.tar.bz2
    #
    # and upload it to
    #
    #   s3://my-bucket-name/s3/sub/path/
    #


    # An independent backup, creating its own archive, and uploading to a
    # different S3 bucket.
    [backups.config2]
    # Overrides the s3_bucket value from [backups]
    s3_bucket = "different-bucket"

    # A different source directory.
    src_dir = "${COMMON_BASE_DIR}/dir2"

    # It's ok not to specify archive_prefix, s3_subdir, or ignore.

Running
-------

Perform the backups specified by ``${HOME}/.config/zstash/backups.toml`` by
running

.. code-block:: shell

    $ zstash --config="${HOME}/.config/zstash/backups.toml"


To test a config, add the ``--dry_run`` option and it will do everything
except upload to S3.

cron
----

TODO:

* A good logging story. Would be nice if it rotated.
* Reminder that the env is usually empty when running from cron, so it's
  better to avoid relying on things like $HOME.
