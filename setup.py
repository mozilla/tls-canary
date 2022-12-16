# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from os import path
from setuptools import setup, find_packages

PACKAGE_NAME = 'tlscanary'
PACKAGE_VERSION = '4.0.2'

INSTALL_REQUIRES = [
    'coloredlogs',
    'cryptography',
    'hashfs',
    'python-dateutil',
    'worq'
]

SCHEDULER_REQUIRES = [
    'matplotlib',
    'schedule'
]

TESTS_REQUIRE = [
    'coverage',
    'pycodestyle',
    'pytest',
    'pytest-pycodestyle',
    'pytest-runner'
]

DEV_REQUIRES = TESTS_REQUIRE + SCHEDULER_REQUIRES

with open(path.join(path.abspath(path.dirname(__file__)), 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name=PACKAGE_NAME,
    version=PACKAGE_VERSION,
    description='TLS/SSL Test Suite for Mozilla Firefox',
    long_description=long_description,
    long_description_content_type='text/markdown',
    classifiers=[
        'Environment :: Console',
        'Development Status :: 7 - Inactive',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)',
        'Natural Language :: English',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Microsoft :: Windows :: Windows 10',
        'Operating System :: Microsoft :: Windows :: Windows 7',
        'Operating System :: Microsoft :: Windows :: Windows 8',
        'Operating System :: Microsoft :: Windows :: Windows 8.1',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Software Development :: Testing'
    ],
    keywords=['mozilla', 'firefox', 'tls', 'regression-testing', 'testing'],
    author='Christiane Ruetten',
    author_email='cr@mozilla.com',
    url='https://github.com/mozilla/tls-canary',
    download_url='https://github.com/mozilla/tls-canary/archive/latest.tar.gz',
    license='MPL2',
    packages=find_packages(exclude=["tests"]),
    include_package_data=True,  # See MANIFEST.in
    zip_safe=False,
    install_requires=INSTALL_REQUIRES,
    tests_require=TESTS_REQUIRE,
    extras_require={
        'dev': DEV_REQUIRES,  # For `pip install -e .[dev]`
        'scheduler': SCHEDULER_REQUIRES  # For `pip install -e .[scheduler]`
    },
    entry_points={
        'console_scripts': [
            'tlscanary = tlscanary.main:main',
            'tlscscheduler = tlscanary.scheduler.main:main'
        ]
    }
)
