# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from distutils import dir_util
import json
import logging
import os
import shutil

import cert


logger = logging.getLogger(__name__)
module_dir = os.path.split(__file__)[0]


def generate(args, header, error_set, start_time, append_runs_log=True):
    global logger

    # Create report directory if necessary.
    if not os.path.exists(args.reportdir):
        logger.debug('Creating report directory %s' % args.reportdir)
        os.makedirs(args.reportdir)

    timestamp = start_time.strftime("%Y-%m-%d-%H-%M-%S")
    run_dir = os.path.join(args.reportdir, "runs", timestamp)
    logger.info("Writing report to `%s`" % run_dir)

    # parse data from header
    log_lines = ["%s : %s" % (k, header[k]) for k in header]
    log_lines.append("++++++++++")
    log_lines.append("")

    # add site list
    for rank, host, result in error_set:
        log_data = collect_scan_info(result)
        if args.mode == 'performance':
            add_performance_info(log_data, result)
        if args.filter == 1:
            # Filter out stray timeout errors
            if log_data["error"]["message"] == "NS_BINDING_ABORTED" \
                    and log_data["site_info"]["connectionSpeed"] \
                    > result.response.original_cmd["args"]["timeout"] * 1000:
                continue
        log_lines.append("%d,%s %s" % (rank, host, json.dumps(log_data)))

    # Install static template files in report directory
    template_dir = os.path.join(module_dir, "template")
    dir_util.copy_tree(os.path.join(template_dir, "js"),
                       os.path.join(args.reportdir, "js"))
    dir_util.copy_tree(os.path.join(template_dir, "css"),
                       os.path.join(args.reportdir, "css"))
    shutil.copyfile(os.path.join(template_dir, "index.htm"),
                    os.path.join(args.reportdir, "index.htm"))

    # Create per-run directory for report output
    if not os.path.isdir(run_dir):
        os.makedirs(run_dir)

    cert_dir = os.path.join(run_dir, "certs")
    __extract_certificates(error_set, cert_dir)

    shutil.copyfile(os.path.join(template_dir, "report_template.htm"),
                    os.path.join(run_dir, "index.htm"))

    # Write the final log file
    with open(os.path.join(run_dir, "log.txt"), "w") as log:
        log.write('\n'.join(log_lines))

    # Append to runs.log
    if append_runs_log:
        run_log = {
                "run": header["timestamp"],
                "branch": header["branch"],
                "errors": len(error_set),
                "description": header["description"]
            }

        with open(os.path.join(args.reportdir, "runs", "runs.txt"), "a") as log:
            log.write(json.dumps(run_log) + '\n')


def __extract_certificates(error_set, cert_dir):
    global logger

    if not os.path.exists(cert_dir):
        os.makedirs(cert_dir)

    for rank, host, data in error_set:
        cert_file = os.path.join(cert_dir, "%s.der" % host)
        if "certificate_chain" in data.response.result["info"]:
            server_cert_string = ''.join(map(chr, data.response.result["info"]["certificate_chain"][0]))
            logger.debug("Writing certificate data for `%s` to `%s`" % (host, cert_file))
            with open(cert_file, "w") as f:
                f.write(server_cert_string)
        else:
            logger.debug("No certificate data available for `%s`" % host)


NSErrorMap = {
    # For network error messages that are not obtainable otherwise
    # https://developer.mozilla.org/en-US/docs/Mozilla/Errors
    0X00000000: "NS_OK",
    0X80004004: "NS_ERROR_ABORT",
    0X8000FFFF: "UNEXPECTED_ERROR",
    0X804B0002: "NS_BINDING_ABORTED",
    0X804B000A: "ERROR_MALFORMED_URI",
    0X804B000D: "CONNECTION_REFUSED_ERROR",
    0X804B0014: "NET_RESET_ERROR",
    0X804B001E: "DOMAIN_NOT_FOUND_ERROR",
}


def decode_ns_status(scan_result):
    status = scan_result.response.result["info"]["status"]
    try:
        return NSErrorMap[status]
    except KeyError:
        return "UNKNOWN_STATUS"


def decode_error_type(scan_result):
    status = scan_result.response.result["info"]["status"]
    if status & 0xff0000 == 0x5a0000:  # security module
        error_class = scan_result.response.result["info"]["error_class"]
        if error_class == 2:  # nsINSSErrorsService::ERROR_CLASS_BAD_CERT
            return "certificate"
        else:
            return "protocol"
    else:
        return "network"


def decode_raw_error(scan_result):
    if "raw_error" in scan_result.response.result["info"]:
        raw_error = scan_result.response.result["info"]["raw_error"]
        if "Error code:" in raw_error:
            return raw_error.split("Error code:")[1].split(">")[1].split("<")[0]
    return decode_ns_status(scan_result)


def collect_error_info(scan_result):
    error_info = {
        "message": decode_raw_error(scan_result),
        "code": "%s" % hex(scan_result.response.result["info"]["status"]),
        "type": decode_error_type(scan_result)
    }
    return error_info


def collect_site_info(scan_result):
    site_info = {
        "timestamp": scan_result.response.response_time,
        "connectionSpeed": scan_result.response.response_time - scan_result.response.command_time,
        "uri": scan_result.host,
        "rank": scan_result.rank
    }
    return site_info


def collect_certificate_info(scan_result):

    result = scan_result.response.result

    if not result["info"]["ssl_status_status"]:
        return {}

    status = result["info"]["ssl_status"]

    server_cert = status["serverCert"]
    parsed_server_cert = cert.Cert(result["info"]["certificate_chain"][0])

    root_cert = server_cert
    chain_length = 1
    while root_cert["issuer"] is not None:
        root_cert = root_cert["issuer"]
        chain_length += 1

    cert_info = {
        "nickname": server_cert["nickname"] if "nickname" in server_cert else "(no nickname)",
        "emailAddress": server_cert["emailAddress"],
        "subjectName": server_cert["subjectName"],
        "commonName": server_cert["commonName"],
        "organization": server_cert["organization"],
        "organizationalUnit": server_cert["organizationalUnit"],
        "issuerCommonName": server_cert["issuerCommonName"],
        "issuerOrganization": server_cert["issuerOrganization"],
        "sha1Fingerprint": server_cert["sha1Fingerprint"],
        "sha256Fingerprint": server_cert["sha256Fingerprint"],
        "chainLength": chain_length,
        "certifiedUsages": result["info"]["certified_usages"],
        "validityNotBefore": server_cert["validity"]["notBeforeGMT"],
        "validityNotAfter": server_cert["validity"]["notAfterGMT"],
        "isEV": str(status["isExtendedValidation"]),
        "subjectAltName": parsed_server_cert.subject_alt_name(),
        "signatureAlgorithm": parsed_server_cert.signature_hash_algorithm(),
        "keyUsage": server_cert["keyUsages"],
        "extKeyUsage": parsed_server_cert.ext_key_usage(),
        "rootCertificateSubjectName": root_cert["subjectName"],
        "rootCertificateOrganization": root_cert["organization"],
        "rootCertificateOrganizationalUnit": root_cert["organizationalUnit"],
        "rootCertificateSHA1Fingerprint": root_cert["sha1Fingerprint"],
    }

    return cert_info


def collect_scan_info(scan_result):
    return {
        "site_info": collect_site_info(scan_result),
        "error": collect_error_info(scan_result),
        "cert_info": collect_certificate_info(scan_result)
    }


def add_performance_info(log_data, scan_result):
    log_data['site_info']['connectionSpeedChange'] = scan_result.response.connection_speed_change
    log_data['site_info']['connectionSpeedSamples'] = scan_result.response.connection_speed_samples
