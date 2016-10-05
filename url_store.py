# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os

__datasets = {
    'alexa': 'alexa_top_sites.csv',
    'debug': 'debug.csv',
    'google': 'google_ct_list.csv',
    'pulse': 'pulse_top_sites_list.csv',
    'smoke': 'smoke_list.csv',
    'test': 'test_url_list.csv',
    'top': 'top-1m.csv'
}


def list():
    datasets = __datasets.keys()
    datasets.sort()
    return datasets


def iter(datasets):
    if type(datasets) == str:
        datasets = [datasets]
    for dataset in datasets:
        if dataset.endswith('.csv'):
            csv_file = os.path.abspath(dataset)
        else:
            csv_file = self.__datasets[dataset]
        with open(csv_file, 'r') as f:
            for nr, url in csv.reader(csv_file):
                yield nr, url


class URLStore(object):
    def __init__(self, data_dir):
        self.__data_dir = os.path.abspath(data_dir)
        self.__loaded_datasets = []
        self.clear()

    def clear(self):
        """Clear all active URLs from store."""
        self.__urls = []

    def __len__(self):
        """Returns number of active URLs in store."""
        return len(self.__urls)

    def __iter__(self):
        """Iterate all active URLs in store."""
        for nr, url in self.__urls:
            yield nr, url

    @staticmethod
    def list():
        """List handles and files for all static URL databases."""
        return list()

    def load(self, datasets):
        """Load datasets arrayinto active URL store."""
        for nr, url in iter(datasets):
            self.__urls.append((nr, url))
        self.__loaded_datasets.append(datasets)

