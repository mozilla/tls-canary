#!/usr/bin/env python2

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from cryptography import x509
from cryptography.hazmat import backends
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import ExtensionOID


class Cert(object):
    """Class for handling X509 certificates"""

    def __init__(self, data):
        """
        Cert constructor

        It can handle PEM and DER encoded strings and lists of int bytes.

        :param data: bytes or list of int
        """
        if type(data) == list:
            data = bytes(data)
        if type(data) != bytes:
            raise Exception("data must be bytes or list of int bytes")
        self.__raw_data = data
        if b"-----BEGIN CERTIFICATE-----" in data:
            self.x509 = x509.load_pem_x509_certificate(data, backends.default_backend())
            self.__raw_type = "PEM"
        else:
            self.x509 = x509.load_der_x509_certificate(data, backends.default_backend())
            self.__raw_type = "DER"

    def as_pem(self):
        """
        Convert certificate to PEM-encoded string

        :return: str
        """
        return self.x509.public_bytes(encoding=serialization.Encoding.PEM)

    def as_der(self):
        """
        Convert certificate to DER-encoded string

        :return: str
        """
        return self.x509.public_bytes(encoding=serialization.Encoding.DER)

    def signature_hash_algorithm(self):
        """
        Extract certificate's hash algorithm

        :return: str
        """
        return self.x509.signature_hash_algorithm.name

    def subject_alt_name(self):
        """
        Extract certificate's alt names

        :return: unicode
        """
        try:
            alt_names = self.x509.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
            alt_name_strings = [alt_name.value for alt_name in alt_names]
            return ",".join(alt_name_strings)
        except x509.ExtensionNotFound:
            return "(no subject alt name)"

    def ext_key_usage(self):
        """
        Extract certificate's permitted extended usages

        :return: str
        """
        try:
            usages = self.x509.extensions.get_extension_for_oid(ExtensionOID.EXTENDED_KEY_USAGE).value
            usages_strings = [usage._name for usage in usages]
            return ",".join(usages_strings)
        except x509.ExtensionNotFound:
            return "(no ext key usage)"
