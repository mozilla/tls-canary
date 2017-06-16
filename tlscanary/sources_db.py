# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import csv
import logging
import os
import pkg_resources as pkgr


logger = logging.getLogger(__name__)


def list_sources(override_dir=None):
    """
    This function trawls through all the sources CSV files in the module CSV directory and
    the given override directory, and generates a dictionary of database handle names and
    associated file names. Per default, the base part of the file name (without `.csv`) is
    used as handle for that list.

    Files in the override directory override files in the module directory.

    If the first line of a CSV file begins with a `#`, it is interpreted as a
    colon-separated list of keywords. If it contains the keyword `handle`, the last
    keyword is used as its handle instead of the file name derivative.

    If the line contains the keyword `default`, it is being used as the default list.
    When multiple CSV files use the `default` keyword, the lexicographically last file
    name is used as default.

    :param override_dir: str of directory used for overrides
    :return: (dict mapping handles to file names, str handle of default list)
    """
    global logger

    sources_list = {}
    default_source = None

    # First, look for CSV files in module resources
    csv_files = [os.path.abspath(pkgr.resource_filename(__name__, "sources/%s" % name))
                 for name in pkgr.resource_listdir(__name__, "sources")
                 if name.endswith(".csv")]

    # Then look for CSV files in the override directory
    if override_dir is not None and os.path.isdir(override_dir):
        for root, dirs, files in os.walk(override_dir):
            for name in files:
                if name.endswith(".csv"):
                    csv_files.append(os.path.abspath(os.path.join(root, name)))

    # Finally extract metadata from files and compile sources list
    for file_name in csv_files:
        logger.debug("Indexing database resource `%s`" % file_name)
        source_handle, is_default = parse_csv_header(file_name)
        sources_list[source_handle] = file_name
        if is_default:
            default_source = source_handle

    return sources_list, default_source


def parse_csv_header(file_name):
    """
    Read first line of file and try to interpret it as a series of colon-separated
    keywords if the line starts with a `#`. Currently supported keywords:

    - handle: The last keyword is interpreted as database vanity handle
    - default: The database is used as default database.

    If no handle is specified, the file name's base is used instead.

    :param file_name: str with file name to check
    :return: (string with handle, bool default state)
    """
    source_handle = os.path.splitext(os.path.basename(file_name))[0]
    is_default = False
    with open(file_name) as f:
        line = f.readline().strip()
    if line.startswith("#"):
        keywords = line.lstrip("#").split(":")
        if "handle" in keywords:
            source_handle = keywords[-1]
        if "default" in keywords:
            is_default = True
    return source_handle, is_default


class SourcesDB(object):
    """
    Class to represent the database store for host data. CSV files from the `sources`
    subdirectory of the module directory are considered as database source files.
    Additionally, CSV files inside the `sources` subdirectory of the working directory
    (usually ~/.tlscanary) are parsed and thus can override files from the module
    directory.

    Each database file is referenced by a unique handle. The first line of the CSV can
    be a special control line that modifies how the database file is handled. See
    sources_db.parse_csv_header().

    The CSV files are required to contain a  regular CSV header line, the column
    `hostname`, and optionally the column `rank`.
    """
    def __init__(self, args=None):
        self.__args = args
        if args is not None:
            self.__override_dir = os.path.join(args.workdir, "sources")
        else:
            self.__override_dir = None
        self.__list, self.default = list_sources(self.__override_dir)
        if self.default is None:
            self.default = self.__list.keys()[0]

    def list(self):
        """
        List handles of available source CSVs

        :return: list with handles
        """
        handles_list = self.__list.keys()
        handles_list.sort()
        return handles_list

    def read(self, handle):
        """
        Read the database file referenced by the given handle.

        :param handle: str with handle
        :return: Sources object containing the data
        """
        global logger
        if handle not in self.__list:
            logger.error("Unknown sources database handle `%s`. Continuing with empty set" % handle)
            return Sources(handle)
        file_name = self.__list[handle]
        source = Sources(handle, handle == self.default)
        source.load(file_name)
        source.trim(self.__args.limit)
        return source

    def write(self, source):
        """
        Write a Sources object to a CSV database file into the `sources` subdirectory of
        the working directory (usually ~/.tlscanary). The file is named <handle.csv>.
        Metadata like handle and default state are stored in the first line of the file.

        :param source: Sources object
        :return: None
        """
        sources_dir = os.path.join(self.__args.workdir, "sources")
        if not os.path.isdir(sources_dir):
            os.makedirs(sources_dir)
        file_name = os.path.join(sources_dir, "%s.csv" % source.handle)
        source.write(file_name)


class Sources(object):
    def __init__(self, handle, is_default=False):
        self.handle = handle
        self.is_default = is_default
        self.rows = []

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, item):
        return self.rows[item]

    def __iter__(self):
        for row in self.rows:
            yield row

    def append(self, row):
        """
        Add a row to the end of the current sources list

        :param row: dict of `rank` and `hostname`
        :return:  None
        """
        self.rows.append(row)

    def sort(self):
        """
        Sort rows according to rank

        :return: None
        """
        self.rows.sort(key=lambda row: int(row["rank"]))

    def load(self, file_name):
        """
        Load content of a sources database from a CSV file

        :param file_name: str containing existing file name
        :return: None
        """
        global logger
        self.handle, self.is_default = parse_csv_header(file_name)
        logger.debug("Reading `%s` sources from `%s`" % (self.handle, file_name))
        with open(file_name) as f:
            csv_reader = csv.DictReader(filter(lambda r: not r.startswith("#"), f))
        self.rows = [row for row in csv_reader]

    def trim(self, limit):
        """
        Trim length of sources list to given limit. Does not trim if
        limit is None.

        :param limit: int maximum length or None
        :return: None
        """
        if limit is not None:
            if len(self) > limit:
                self.rows = self.rows[:limit]

    def write(self, location):
        """
        Write out instance sources list to a CSV file. If location refers to
        a directory, the file is written there and the file name is chosen as
        <handle>.csv. Metadata like handle and default state are stored in the
        first line of the file.

        If location refers to a file name, it used as file name directly.
        The target directory must exist.

        :param location: directory or file name in an existing directory
        :return: None
        """
        global logger
        if os.path.isdir(location):
            file_name = os.path.join(location, "%s.csv" % self.handle)
        elif os.path.isdir(os.path.dirname(location)):
            file_name = location
        else:
            raise Exception("Can't write to location `%s`" % location)
        logger.debug("Writing `%s` sources to `%s`" % (self.handle, file_name))
        with open(file_name, "w") as f:
            header_keywords = []
            if self.is_default:
                header_keywords.append("default")
            header_keywords += ["handle", self.handle]
            f.write("#%s\n" % ":".join(header_keywords))
            csv_writer = csv.DictWriter(f, self.rows[0].keys())
            csv_writer.writeheader()
            csv_writer.writerows(self.rows)
        return file_name

    def from_set(self, src_set):
        """
        Use set to fill this Sources object. The set is expected to contain
        :param src_set: set with (rank, host) pairs
        :return: None
        """
        self.rows = [{"rank": str(rank), "hostname": hostname} for rank, hostname in src_set]

    def as_set(self, start=0, end=None):
        """
        Return rows of this sources list as a set. The set does not pertain any of
        the sources' meta data (DB handle, default). You can specify `start` and `end`
        to select just a chunk of data from the rows.

        Warning: There is no plausibility checking on `start` and `end` parameters.

        :param start: optional int marking beginning of chunk
        :param end: optional int marking end of chunk
        :return: set of (int rank, str hostname) pairs
        """
        if len(self.rows) == 0:
            return set()
        if end is None:
            end = len(self.rows)
        if "rank" in self.rows[0].keys():
            return set([(int(row["rank"]), row["hostname"]) for row in self.rows[start:end]])
        else:
            return set([(0, row["hostname"]) for row in self.rows[start:end]])
