# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import glob
import os
import shutil
import subprocess
import tempfile


# TODO: Ensure that all images are unmounted at exit.
# Images may still be mounted when global tmp_dir is removed at exit,
# for example when extraction throws an exception.

# TODO: Cache extracted files, too. Takes very long to unpack 100 MByte.


def _osx_mount_dmg(dmg_file, mount_point):
    assert('"' not in dmg_file + mount_point)
    assert(dmg_file.endswith('.dmg'))
    cmd = 'hdiutil attach -noverify -noautoopen -noautoopenro -nobrowse -noidme -mount required ' \
          '-quiet -mountpoint "%s" "%s"' % (mount_point, dmg_file)
    # Throws subprocess.CalledProcessError on non-zero exit value
    subprocess.check_call(cmd, shell=True)


def _osx_unmount_dmg(mount_point):
    assert('"' not in mount_point)
    cmd = 'hdiutil detach -quiet -force "%s"' % mount_point
    # Throws subprocess.CalledProcessError on non-zero exit value
    subprocess.check_call(cmd, shell=True)


def _osx_extract(archive_file, tmp_dir):
    extract_dir = tempfile.mkdtemp(dir=tmp_dir, prefix='extracted_')
    mount_dir = tempfile.mkdtemp(dir=tmp_dir, prefix='mount_')
    print 'Mounting image `%s` at mount point `%s`' % (archive_file, mount_dir)
    _osx_mount_dmg(archive_file, mount_dir)
    # Copy everything over
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)
    print 'Copying files from mount point `%s` to `%s`' % (mount_dir, extract_dir)
    shutil.copytree(mount_dir, extract_dir, symlinks=True)
    print 'Detaching image from mount point `%s`' % (mount_dir)
    _osx_unmount_dmg(mount_dir)
    # TODO: Handle potentially empty glob list
    exe_file = glob.glob(os.path.join(extract_dir, 'Firefox*.app/Contents/MacOS/firefox-bin'))[0]
    if not os.path.isfile(exe_file):
        exe_file = None
    return extract_dir, exe_file


def extract(platform, archive_file, tmp_dir):
    if platform == 'osx':
        extract_dir, exe_file = _osx_extract(archive_file, tmp_dir)
    else:
        print 'Unsupported platform for extractor: %s' % platform
        extract_dir = None
        exe_file = None
    return extract_dir, exe_file
