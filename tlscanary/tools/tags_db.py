# -*- coding: utf8 -*-

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import logging
import os

logger = logging.getLogger(__name__)


class TagsDB(object):
    """
    Class to manage snapshot tags
    """

    def __init__(self, args):
        self.__args = args
        self.__tags_file = os.path.join(self.__args.workdir, "tags.json")
        self.__tags = None  # Overwritten by TagsDB.load()
        self.load()

    def load(self) -> None:
        """
        Load TagDB from disk
        :return: None
        """
        try:
            with open(self.__tags_file, mode="r") as f:
                parsed = json.load(f)
        except FileNotFoundError:
            parsed = {}
        # Convert json arrays to sets
        self.__tags = {}
        for tag in parsed:
            assert type(parsed[tag]) is list
            self.__tags[tag] = set(parsed[tag])

    def remove_dangling(self, existing_refs: list, save: bool = False):
        """
        Remove all tag references to non-existent refs
        :param existing_refs: list of existing references
        :param save: optional bool whether TagDB to be saved to disk
        :return: None
        """
        changed = False
        for tag in self:
            for ref in self[tag]:
                if ref not in existing_refs:
                    self.remove(tag, ref, save=False)
                    changed = True
        if changed and save:
            self.save()

    def save(self):
        """
        Save TagDB to disk
        :return: None
        """
        for_parser = {}
        for tag in self:  # Iterates just associated tags
            for_parser[tag] = list(self[tag])
        with open(self.__tags_file, mode="w") as f:
            json.dump(for_parser, f, indent=4, sort_keys=True)

    def __contains__(self, tag: str) -> bool:
        """
        Implements `tag in TagDB()`
        :param tag: str with tag
        :return: bool
        """
        return tag in self.__tags and len(self.__tags[tag]) > 0

    def __getitem__(self, tag: str) -> set:
        """
        Implements `handles = TagDB()[tag]`
        :param tag: str with tag
        :return: set of str of handles (may be empty)
        """
        return self.tag_to_handles(tag)

    def __setitem__(self, tag: str, handle: str) -> None:
        """
        Implements `TagDB()[tag] = handle` for tagging a handle
        :param tag: str with tag
        :param handle: str with handle
        :return: None
        """
        self.add(tag, handle)

    def __delitem__(self, tag: str) -> None:
        """
        Implements `del TagDB()[tag]`, dropping a tag completely
        :param tag: str with tag
        :return: None
        """
        self.drop(tag)

    def __iter__(self):
        """
        Implements iterating over all tags that have associated handles
        :return:
        """
        for tag in self.__tags:
            if len(self.__tags[tag]) > 0:
                yield tag

    @staticmethod
    def is_valid_tag(tag):
        return type(tag) is str and tag.isalnum() and not tag.isdigit() and " " not in tag

    def tag_to_handles(self, tag: str) -> set:
        """
        Converts a tag to its associated handles
        :param tag: str with tag
        :return: set of str handles (may be empty)
        """
        try:
            return self.__tags[tag].copy()
        except KeyError:
            return set()

    def handle_to_tags(self, handle: str) -> set:
        """
        Converts a handle to its associated tags
        :param handle: str with handle
        :return: set of str with tags (may be empty)
        """
        tags = set()
        for tag in self.__tags:
            if handle in self.__tags[tag]:
                tags.add(tag)
        return tags

    def exists(self, tag: str, handle: str = None) -> bool:
        """
        Check whether a tag exists, or exists for a specific handle
        :param tag: str with tag
        :param handle: optional str with handle
        :return: bool
        """
        if handle is None:
            return tag in self.__tags
        else:
            if tag in self.__tags:
                return handle in self.__tags[tag]
            else:
                return False

    def list(self, tag: str = None) -> list:
        """
        Returns a list of tags, or handles associated with tag
        :param tag: optional str with tag
        :return: list of str of tags
        """
        if tag is None:
            return sorted(self.__tags.keys())
        else:
            return list(self.tag_to_handles(tag))

    def add(self, tag: str, handle: str, save: bool = True):
        """
        Associate tag with handle
        :param tag: str with tag
        :param handle: str with handle
        :param save: optional bool whether TagDB to be saved to disk
        :return: None
        """
        try:
            self.__tags[tag].add(handle)
        except KeyError:
            self.__tags[tag] = {handle}
        if save:
            self.save()

    def remove(self, tag: str, handle: str, save: bool = True):
        """
        Disassociate tag from handle
        :param tag: str with tag
        :param handle: str with handle
        :param save: optional bool whether TagDB to be saved to disk
        :return: None
        """
        try:
            self.__tags[tag].remove(handle)
        except KeyError:
            logger.warning("Tag `%s` does not exist" % tag)
            return  # Nothing changed, so no need to save
        except ValueError:
            logger.warning("Handle `%s` is not associated with tag `%s`" % (handle, tag))
            return  # Nothing changed, so no need to save
        if save:
            self.save()

    def drop(self, tag, save: bool = True):
        """
        Completely delete a tag and all of its handle associations
        :param tag: str with tag
        :param save: optional bool whether TagDB to be saved to disk
        :return: None
        """
        if tag in self.__tags and len(self.__tags[tag]) > 0:
            del self.__tags[tag]
        else:
            logger.debug("Not dropping non-existent tag `%s`" % tag)
            return  # No need to save
        if save:
            self.save()
