# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import ConfigParser
import glob
import logging
import os
import shutil
import subprocess
import tempfile
import sys

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

    logger.info("Extracting archive")
    extract_dir = tempfile.mkdtemp(dir=tmp_dir, prefix='extracted_')
    mount_dir = tempfile.mkdtemp(dir=tmp_dir, prefix='mount_')
    logger.debug('Mounting image `%s` at mount point `%s`' % (archive_file, mount_dir))
    __osx_mount_dmg(archive_file, mount_dir)

    try:
        # Determine app subfolder
        # TODO: Handle potentially empty glob list
        app_folder_glob = glob.glob(os.path.join(mount_dir, '*.app'))
        if len(app_folder_glob) != 1:
            raise Exception("Can't determine Firefox app folder name in DMG")
        app_folder_name = os.path.basename(app_folder_glob[0])

        # Determine Firefox version
        app_ini = ConfigParser.SafeConfigParser()
        app_ini.read(os.path.join(mount_dir, app_folder_name, "Contents", "Resources", "application.ini"))
        app_version = app_ini.get("App", "Version")

        # Copy everything over
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        logger.debug('Copying files from mount point `%s` to `%s`' % (mount_dir, extract_dir))
        shutil.copytree(mount_dir, extract_dir, symlinks=True)

        logger.info("Extracted Firefox version is %s" % app_version)

    except Exception, err:
        logger.error('Error detected while extracting image. Detaching image from mount point `%s`' % mount_dir)
        __osx_unmount_dmg(mount_dir)
        raise err

    except KeyboardInterrupt, err:
        logger.error('User abort. Detaching image from mount point `%s`' % mount_dir)
        __osx_unmount_dmg(mount_dir)
        raise err

    logger.debug('Detaching image from mount point `%s`' % mount_dir)
    __osx_unmount_dmg(mount_dir)

    exe_file = os.path.join(extract_dir, app_folder_name, "Contents", "MacOS", "firefox")
    if not os.path.isfile(exe_file):
        exe_file = None
    return extract_dir, exe_file


def __linux_extract(archive_file, tmp_dir):
    global logger

    extract_dir_parent = tempfile.mkdtemp(dir=tmp_dir, prefix='extracted_')
    logger.debug('Unzipping archive `%s`' % (archive_file))

    # Create unique name for each downloaded build, equal to its filename
    app_dir_name = archive_file.split("/").pop().replace(".tar.bz2","");
    extract_dir = "%s/%s" % (extract_dir_parent,app_dir_name)

    cmd = "mkdir %s" % extract_dir
    subprocess.check_output(cmd, shell=True)

    # Unzip archive to extract directory
    cmd = "tar -xf %s -C %s" % (archive_file,extract_dir)
    subprocess.check_output(cmd, shell=True)

    exe_file = "%s/firefox/firefox-bin" % extract_dir

    return extract_dir, exe_file


def extract(platform, archive_file, tmp_dir):
    if platform == 'osx':
        extract_dir, exe_file = __osx_extract(archive_file, tmp_dir)
    elif platform == 'linux':
        extract_dir, exe_file = __linux_extract(archive_file, tmp_dir)
    else:
        extract_dir = None
        exe_file = None
    return extract_dir, exe_file
