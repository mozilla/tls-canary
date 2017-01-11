# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import os
import shutil
import subprocess
import tarfile
import tempfile

from firefox_app import FirefoxApp

logger = logging.getLogger(__name__)


# TODO: Ensure that all images are unmounted at exit.
# Images may still be mounted when global tmp_dir is removed at exit,
# for example when extraction throws an exception.

# TODO: Cache extracted files, too. Takes very long to unpack 100 MByte.


def __osx_mount_dmg(dmg_file, mount_point):
    global logger
    assert('"' not in dmg_file + mount_point)
    assert(dmg_file.endswith('.dmg'))
    cmd = '''hdiutil attach -readonly -noverify -noautoopen -noautoopenro''' \
          ''' -noautoopenrw -nobrowse -noidme -noautofsck -mount required''' \
          ''' -quiet -mountpoint "%s" "%s"''' % (mount_point, dmg_file)
    logger.debug("Executing shell command `%s`" % cmd)
    # Throws subprocess.CalledProcessError on non-zero exit value
    subprocess.check_call(cmd, shell=True)


def __osx_unmount_dmg(mount_point):
    global logger
    assert('"' not in mount_point)
    cmd = 'hdiutil detach -quiet -force "%s"' % mount_point
    logger.debug("Executing shell command `%s`" % cmd)
    # Throws subprocess.CalledProcessError on non-zero exit value
    subprocess.check_call(cmd, shell=True)


def __osx_extract(archive_file, tmp_dir):
    global logger

    logger.info("Extracting MacOS X archive")
    extract_dir = tempfile.mkdtemp(dir=tmp_dir, prefix='extracted_')
    mount_dir = tempfile.mkdtemp(dir=tmp_dir, prefix='mount_')
    logger.debug('Mounting image `%s` at mount point `%s`' % (archive_file, mount_dir))
    __osx_mount_dmg(archive_file, mount_dir)

    try:
        # Copy everything over
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        logger.debug('Copying files from mount point `%s` to `%s`' % (mount_dir, extract_dir))
        shutil.copytree(mount_dir, extract_dir, symlinks=True)

    except Exception, err:
        logger.error('Error while extracting image. Detaching image from mount point `%s`' % mount_dir)
        __osx_unmount_dmg(mount_dir)
        raise err

    except KeyboardInterrupt, err:
        logger.error('User abort. Detaching image from mount point `%s`' % mount_dir)
        __osx_unmount_dmg(mount_dir)
        raise err

    logger.debug('Detaching image from mount point `%s`' % mount_dir)
    __osx_unmount_dmg(mount_dir)

    return extract_dir


def __linux_extract(archive_file, tmp_dir):
    global logger

    logger.info("Extracting Linux archive")
    extract_dir = tempfile.mkdtemp(dir=tmp_dir, prefix='extracted_')
    logger.debug("Extracting Linux archive `%s` to `%s`" % (archive_file, extract_dir))

    try:
        with tarfile.open(archive_file) as tf:
            tf.extractall(extract_dir)

    except Exception, err:
        logger.error('Error while extracting image: %s' % err)
        raise err

    return extract_dir


def extract(platform, archive_file, tmp_dir):
    """Extract a Firefox archive file into a subfolder in the given temp dir."""
    global logger

    if platform == 'osx':
        extract_dir = __osx_extract(archive_file, tmp_dir)
    elif platform == "linux" or platform == "linux32":
        extract_dir = __linux_extract(archive_file, tmp_dir)
    else:
        extract_dir = None
    return FirefoxApp(extract_dir)
