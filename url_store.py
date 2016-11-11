# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import csv
import os

__datasets = {
    'alexa': 'alexa_top_sites.csv',
    'alexa5k': 'alexa_top5k_sites.csv',
    'alexa10k': 'alexa_top10k_sites.csv',
    'debug': 'debug.csv',
    'google': 'google_ct_list.csv',
    'pulse': 'pulse_top_sites_list.csv',
    'smoke': 'smoke_list.csv',
    'test': 'test_url_list.csv',
    'top1m': 'top-1m.csv'
}


def list():
    dataset_list = __datasets.keys()
    dataset_list.sort()
    dataset_default = "alexa"
    assert dataset_default in dataset_list
    return dataset_list, dataset_default


def iter(dataset, data_dir):
    if dataset.endswith('.csv'):
        csv_file_name = os.path.abspath(dataset)
    else:
        csv_file_name = __datasets[dataset]
    with open(os.path.join(data_dir, csv_file_name)) as f:
        csv_reader = csv.reader(f)
        for row in csv_reader:
            assert 0 <= len(row) <= 2
            if len(row) == 2:
                rank, url = row
                yield int(rank), url
            elif len(row) == 1:
                rank = 0
                url = row[0]
                yield int(rank), url
            else:
                continue


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
        for rank, url in self.__urls:
            yield rank, url

    @staticmethod
    def list():
        """List handles and files for all static URL databases."""
        return list()

    def load(self, datasets):
        """Load datasets arrayinto active URL store."""
        if type(datasets) == str:
            datasets = [datasets]
        for dataset in datasets:
            for nr, url in iter(dataset, self.__data_dir):
                self.__urls.append((nr, url))
            self.__loaded_datasets.append(dataset)

