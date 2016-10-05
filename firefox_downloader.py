# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import sys
import time
import urllib2
import math


class FirefoxDownloader(object):

    _base_url = 'https://download.mozilla.org/?product=firefox' \
                '-{release}&os={platform}&lang=en-US'
    _build_urls = {
        'esr':     _base_url.format(release='esr-latest', platform='{platform}'),
        'release': _base_url.format(release='latest', platform='{platform}'),
        'beta':    _base_url.format(release='beta-latest', platform='{platform}'),
        'aurora':  _base_url.format(release='aurora-latest', platform='{platform}'),
        'nightly': _base_url.format(release='nightly-latest', platform='{platform}')
    }
    _platforms = {
        'osx':     {'platform': 'osx', 'extension': 'dmg'},
        'linux':   {'platform': 'linux64', 'extension': 'tar.bz2'},
        'linux32': {'platform': 'linux', 'extension': 'tar.bz2'},
        'win':     {'platform': 'win64', 'extension': 'exe'},
        'win32':   {'platform': 'win', 'extension': 'exe'}
    }

    def __init__(self, workdir, cache_timeout=4*60*60):
        self.workdir = workdir
        self.download_cache = os.path.join(workdir, 'download_cache')
        self.cache_timeout = cache_timeout  # Default is four hours

        # Create cache directory if necessary
        if not os.path.exists(self.download_cache):
            print('Creating cache directory %s' % self.download_cache)
            os.makedirs(self.download_cache, mode=0755)

    def purge_cache(self):
        """Remove stale files from cache"""
        # print 'WARNING: not purging cache for development purposes'
        # return
        now = time.time()  # Current time as epoch
        stale_limit = now - self.cache_timeout
        for (root, dirs, files) in os.walk(self.download_cache):
            for file_name in files:
                full_name = os.path.join(root, file_name)
                mtime = os.path.getmtime(full_name)  # Modification time as epoch
                if mtime < stale_limit:
                    print 'Purging stale cache file `%s`' % full_name
                    os.remove(full_name)

    @staticmethod
    def _get_to_file(url, filename):
        try:

            # TODO: Validate the server's SSL certificate
            req = urllib2.urlopen(url)
            file_size = int(req.info().getheader('Content-Length').strip())

            # Caching logic is: don't re-download if file of same size is
            # already in cache. Switch to ETag if that's not good enough.
            # This already prevents cache clutter with incomplete files.
            if os.path.isfile(filename):
                if os.stat(filename).st_size == file_size:
                    req.close()
                    print 'Skipping download using cached file `%s`' % filename
                    return filename
                else:
                    print 'Purging incomplete or obsolete cache file `%s`' % filename
                    os.remove(filename)

            print 'Downloading `%s` to %s' % (url, filename)
            downloaded_size = 0
            chunk_size = 32 * 1024
            with open(filename, 'wb') as fp:
                next_status_update = time.time()  # To enforce initial update
                while True:
                    chunk = req.read(chunk_size)
                    if not chunk:
                        break
                    downloaded_size += len(chunk)
                    fp.write(chunk)

                    # Update status if stdout is a terminal
                    if sys.stdout.isatty():
                        percent = int(math.floor((1.0 * downloaded_size / file_size) * 100.0))
                        now = time.time()
                        if now > next_status_update:
                            next_status_update = now + 0.5  # Twice per second
                            sys.stdout.write('\r%d/%d %d%%'
                                             % (downloaded_size, file_size, percent))
                            sys.stdout.flush()

                # The final status update
                if sys.stdout.isatty():
                    sys.stdout.write('\r%d/%d %d%%' % (downloaded_size, file_size, 100))

        except urllib2.HTTPError, err:
            if os.path.isfile(filename):
                os.remove(filename)
            print 'HTTP error:', err.code, url
            return None

        except urllib2.URLError, err:
            if os.path.isfile(filename):
                os.remove(filename)
            print 'URL error:', err.reason, url
            return None

        except KeyboardInterrupt:
            if os.path.isfile(filename):
                os.remove(filename)
            print '\nDownload interrupted'
            return None

        return filename

    def download(self, release, platform, use_cache=True):
        if release not in self._build_urls:
            raise Exception("Failed to download unknown release `%s`" % release)
        if platform not in self._platforms:
            raise Exception("Failed to download for unknown platform `%s`" % platform)

        platform = self._platforms[platform]['platform']
        extension = self._platforms[platform]['extension']
        url = self._build_urls[release].format(platform=platform)
        file_name = 'firefox-%s_%s.%s' % (release, platform, extension)
        cache_file = os.path.join(self.download_cache, file_name)

        # Purge obsolete files from cache
        self.purge_cache()

        # Always delete cached file when cache function is overridden
        if os.path.exists(file_name) and not use_cache:
            os.remove(file_name)

        # _get_to_file will not re-download if same-size file is already there.
        return self._get_to_file(url, cache_file)
