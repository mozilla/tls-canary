# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import os
import struct
import sys
import urllib.error
import urllib.request

from . import cache


logger = logging.getLogger(__name__)


def get_to_file(url, filename, agent=None):
    global logger

    try:
        # TODO: Validate the server's SSL certificate
        if agent is None:
            req = urllib.request.urlopen(url)
        else:
            req = urllib.request.urlopen(urllib.request.Request(url, data=None, headers={'User-Agent': agent}))
        file_size = int(req.info().get('Content-Length').strip())

        # Caching logic is: don't re-download if file of same size is
        # already in place. TODO: Switch to ETag if that's not good enough.
        # This already prevents cache clutter with incomplete files.
        if os.path.isfile(filename):
            if os.stat(filename).st_size == file_size:
                req.close()
                logger.warning('Skipping download, using cached file `%s` instead' % filename)
                return filename
            else:
                logger.warning('Purging incomplete or obsolete cache file `%s`' % filename)
                os.remove(filename)

        logger.debug('Downloading `%s` to %s' % (url, filename))
        downloaded_size = 0
        chunk_size = 32 * 1024
        with open(filename, 'wb') as fp:
            while True:
                chunk = req.read(chunk_size)
                if not chunk:
                    break
                downloaded_size += len(chunk)
                fp.write(chunk)

    except urllib.error.HTTPError as err:
        if os.path.isfile(filename):
            os.remove(filename)
        logger.error('HTTP error: %s, %s' % (err.code, url))
        return None

    except urllib.error.URLError as err:
        if os.path.isfile(filename):
            os.remove(filename)
        logger.error('URL error: %s, %s' % (err.reason, url))
        return None

    except KeyboardInterrupt:
        if os.path.isfile(filename):
            os.remove(filename)
        if sys.stdout.isatty():
            print()
        logger.critical('Download interrupted by user')
        return None

    return filename


class FirefoxDownloader(object):

    __base_url = 'https://download.mozilla.org/?product=firefox' \
                '-{release}&os={platform}&lang=en-US'
    build_urls = {
        'esr':     __base_url.format(release='esr-latest', platform='{platform}'),
        'release': __base_url.format(release='latest', platform='{platform}'),
        'beta':    __base_url.format(release='beta-latest', platform='{platform}'),
        'aurora':  __base_url.format(release='aurora-latest', platform='{platform}'),
        'nightly': __base_url.format(release='nightly-latest', platform='{platform}')
    }
    __platforms = {
        'osx':     {'platform': 'osx', 'extension': 'dmg'},
        'linux':   {'platform': 'linux64', 'extension': 'tar.bz2'},
        'linux32': {'platform': 'linux', 'extension': 'tar.bz2'},
        'win':     {'platform': 'win64', 'extension': 'exe'},
        'win32':   {'platform': 'win', 'extension': 'exe'}
    }

    @staticmethod
    def list():
        build_list = list(FirefoxDownloader.build_urls.keys())
        platform_list = list(FirefoxDownloader.__platforms.keys())
        test_default = "nightly"
        base_default = "release"
        return build_list, platform_list, test_default, base_default

    @staticmethod
    def detect_platform():
        is_64bit = struct.calcsize('P') * 8 == 64
        platform = None
        if sys.platform.startswith("darwin"):
            platform = "osx"
        elif sys.platform.startswith("linux"):
            platform = "linux" if is_64bit else "linux32"
        elif sys.platform.startswith("win"):
            platform = "win" if is_64bit else "win32"
        return platform

    @staticmethod
    def get_download_url(build, platform=None):
        if platform is None:
            platform = FirefoxDownloader.detect_platform()
        # We internally use slightly different platform naming, so translate
        # internal platform name to the platform name used in download URL.
        download_platform = FirefoxDownloader.__platforms[platform]['platform']
        if build in FirefoxDownloader.build_urls:
            return FirefoxDownloader.build_urls[build].format(platform=download_platform)
        else:
            return None

    def __init__(self, workdir, cache_timeout=24*60*60):
        self.__workdir = workdir
        self.__cache = cache.DiskCache(os.path.join(workdir, "cache"), cache_timeout, purge=True)

    def download(self, release, platform=None, use_cache=True):

        if platform is None:
            platform = self.detect_platform()

        if release not in self.build_urls:
            raise Exception("Failed to download unknown release `%s`" % release)
        if platform not in self.__platforms:
            raise Exception("Failed to download for unknown platform `%s`" % platform)

        extension = self.__platforms[platform]['extension']
        url = self.get_download_url(release, platform)
        cache_id = 'firefox-%s_%s.%s' % (release, platform, extension)

        # Always delete cached file when cache function is overridden
        if cache_id in self.__cache and not use_cache:
            self.__cache.delete(cache_id)

        # __get_to_file will not re-download if same-size file is already there.
        return get_to_file(url, self.__cache[cache_id])
