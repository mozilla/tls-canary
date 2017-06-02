# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from setuptools import setup, find_packages

PACKAGE_VERSION = '3.0.1'

# Dependencies
with open('requirements.txt') as f:
    deps = f.read().splitlines()

setup(name='tls_canary',
      version=PACKAGE_VERSION,
      description='TLS/SSL Test Suite for Firefox',
      classifiers=[],
      keywords='mozilla',
      author='Christiane Ruetten',
      author_email='cr@mozilla.com',
      url='https://github.com/cr/tls-canary',
      license='MPL',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=deps,
      entry_points={"console_scripts": [
                    "tls_canary = main:main"
      ]}
)
