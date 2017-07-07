# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import dateutil.parser
from distutils import dir_util
import json
import logging
import os
import shutil

import cert


logger = logging.getLogger(__name__)
module_dir = os.path.split(__file__)[0]


def generate(mode, logs, output_dir):
    global logger

    logger.debug("Generating `%s` report for %d logs in `%s`" % (mode, len(logs), output_dir))

    if mode == "html":
        for log_name in sorted(logs.keys()):
            log = logs[log_name]
            meta = log.get_meta()
            if meta["mode"] != "regression":
                logger.warning("Skipping report generation for non-regression log `%s`" % log_name)
                continue
            if not log.has_finished():
                logger.warning("Skipping report generation for incomplete log `%s`" % log_name)
                continue
            if not log.is_compatible():
                logger.warning("Skipping report generation for incompatible log `%s`" % log_name)
                continue
            html_report(log, output_dir)

    else:
        logger.critical("Report generator mode `%s` not implemented" % mode)


def html_report(log, report_dir):
    global logger

    # Create report directory if necessary.
    if not os.path.exists(report_dir):
        logger.debug('Creating report directory %s' % report_dir)
        os.makedirs(report_dir)

    # Fetch log metadata
    meta = log.get_meta()
    run_start_time = dateutil.parser.parse(meta["run_start_time"])
    run_finish_time = dateutil.parser.parse(meta["run_finish_time"])
    timestamp = run_start_time.strftime("%Y-%m-%d-%H-%M-%S")

    # Read the complete runs log to see if this log was already reported
    runs_log_file = os.path.join(report_dir, "runs", "runs.txt")
    runs_log = {}
    try:
        with open(runs_log_file) as f:
            for line in f.readlines():
                logger.debug("Line read from runs.txt: `%s`" % line.strip())
                run = json.loads(line)
                runs_log[run["run"]] = run
    except IOError:
        # Raised when the file does not yet exist
        pass

    if timestamp in runs_log:
        logger.warning("Skipping log `%s` which was already reported before" % log.handle)
        return

    # Build the report's header from log metadata
    header = {
        "mode": meta["mode"],
        "timestamp": timestamp,
        "branch": meta["test_metadata"]["branch"].capitalize(),
        "source": meta["args"]["source"],
        "test build url": meta["test_metadata"]["download_url"] if "download_url" in meta["test_metadata"] else None,
        "test build metadata": "%s, %s" % (meta["test_metadata"]["nss_version"],
                                           meta["test_metadata"]["nspr_version"]),
        "Total time": "%d minutes" % int(round((run_finish_time - run_start_time).total_seconds() / 60.0))
    }
    if "base_metadata" not in meta:
        header.update({
            "description": "Fx%s %s" % (meta["test_metadata"]["app_version"],
                                        meta["test_metadata"]["branch"])
        })
    else:
        header.update({
            "description": "Fx%s %s vs Fx%s %s" % (meta["test_metadata"]["app_version"],
                                                   meta["test_metadata"]["branch"],
                                                   meta["base_metadata"]["app_version"],
                                                   meta["base_metadata"]["branch"]),
            "release build url": meta["base_metadata"]["download_url"] if "download_url"
                                                                          in meta["base_metadata"] else None,
            "release build metadata": "%s, %s" % (meta["base_metadata"]["nss_version"],
                                                  meta["base_metadata"]["nspr_version"])
        })
    if "total_change" in meta:
        header.update({"Total percent speed change": "%s" % int(meta["total_change"])})

    run_dir = os.path.join(report_dir, "runs", timestamp)
    logger.info("Writing HTML report to `%s`" % run_dir)

    # Append data from header
    log_lines = ["%s : %s" % (k, header[k]) for k in header]
    log_lines.append("++++++++++")
    log_lines.append("")

    # add site list
    meta = log.get_meta()
    for log_line in log:
        result = {
            "host": log_line["host"],
            "rank": log_line["rank"],
            "response": log_line["response"]
        }
        log_data = collect_scan_info(result)
        if meta["mode"] == "performance":  # FIXME: This will probably not be necessary any more
            add_performance_info(log_data, result)
        if meta["args"]["filter"] == 1:
            # Filter out stray timeout errors
            if log_data["error"]["message"] == "NS_BINDING_ABORTED" \
                    and log_data["site_info"]["connectionSpeed"] \
                    > result["response"]["original_cmd"]["args"]["timeout"] * 1000:
                continue
        log_lines.append("%d,%s %s" % (result["rank"], result["host"], json.dumps(log_data)))

    # Install static template files in report directory
    template_dir = os.path.join(module_dir, "template")
    dir_util.copy_tree(os.path.join(template_dir, "js"),
                       os.path.join(report_dir, "js"))
    dir_util.copy_tree(os.path.join(template_dir, "css"),
                       os.path.join(report_dir, "css"))
    shutil.copyfile(os.path.join(template_dir, "index.htm"),
                    os.path.join(report_dir, "index.htm"))

    # Create per-run directory for report output
    if not os.path.isdir(run_dir):
        os.makedirs(run_dir)

    cert_dir = os.path.join(run_dir, "certs")
    __extract_certificates(log, cert_dir)

    shutil.copyfile(os.path.join(template_dir, "report_template.htm"),
                    os.path.join(run_dir, "index.htm"))

    # Write the final log file
    with open(os.path.join(run_dir, "log.txt"), "w") as log_file:
        log_file.write('\n'.join(log_lines))

    # Append to runs.log
    new_run_log = {
            "run": header["timestamp"],
            "branch": header["branch"],
            "errors": len(log),
            "description": header["description"]
        }
    runs_log[timestamp] = new_run_log

    logger.debug("Writing back runs log to `%s`" % runs_log_file)
    with open(runs_log_file, "w") as f:
        f.writelines(["%s\n" % json.dumps(runs_log[timestamp]) for timestamp in sorted(runs_log.keys())])


def __extract_certificates(log, cert_dir):
    global logger

    if not os.path.exists(cert_dir):
        os.makedirs(cert_dir)

    for log_line in log:
        result = {
            "host": log_line["host"],
            "rank": log_line["rank"],
            "response": log_line["response"]
        }
        cert_file = os.path.join(cert_dir, "%s.der" % result["host"])
        if "certificate_chain" in result["response"]["result"]["info"]:
            server_cert_string = "".join(map(chr, result["response"]["result"]["info"]["certificate_chain"][0]))
            logger.debug("Writing certificate data for `%s` to `%s`" % (result["host"], cert_file))
            with open(cert_file, "w") as f:
                f.write(server_cert_string)
        else:
            logger.debug("No certificate data available for `%s`" % result["host"])


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
    status = scan_result["response"]["result"]["info"]["status"]
    try:
        return NSErrorMap[status]
    except KeyError:
        return "UNKNOWN_STATUS"


def decode_error_type(scan_result):
    status = scan_result["response"]["result"]["info"]["status"]
    if status & 0xff0000 == 0x5a0000:  # security module
        error_class = scan_result["response"]["result"]["info"]["error_class"]
        if error_class == 2:  # nsINSSErrorsService::ERROR_CLASS_BAD_CERT
            return "certificate"
        else:
            return "protocol"
    else:
        return "network"


def decode_raw_error(scan_result):
    if "raw_error" in scan_result["response"]["result"]["info"]:
        raw_error = scan_result["response"]["result"]["info"]["raw_error"]
        if "Error code:" in raw_error:
            return raw_error.split("Error code:")[1].split(">")[1].split("<")[0]
    return decode_ns_status(scan_result)


def collect_error_info(scan_result):
    error_info = {
        "message": decode_raw_error(scan_result),
        "code": "%s" % hex(scan_result["response"]["result"]["info"]["status"]),
        "type": decode_error_type(scan_result)
    }
    return error_info


def collect_site_info(scan_result):
    site_info = {
        "timestamp": scan_result["response"]["response_time"],
        "connectionSpeed": scan_result["response"]["response_time"] - scan_result["response"]["command_time"],
        "uri": scan_result["host"],
        "rank": scan_result["rank"]
    }
    return site_info


def collect_certificate_info(scan_result):

    result = scan_result["response"]["result"]

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
    log_data["site_info"]["connectionSpeedChange"] = scan_result["response"]["connection_speed_change"]
    log_data["site_info"]["connectionSpeedSamples"] = scan_result["response"]["connection_speed_samples"]
