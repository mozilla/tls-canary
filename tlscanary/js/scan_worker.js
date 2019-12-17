/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

"use strict";

function collect_request_info(xhr, report_certs) {
    // This function copies and parses various properties of the connection state object
    // and wraps them into an info object to be returned with the command response.
    // Much of this is documented in https://developer.mozilla.org/en-US/docs/Web/API/
    // XMLHttpRequest/How_to_check_the_secruity_state_of_an_XMLHTTPRequest_over_SSL,
    // but that source has gone out of date with Firefox 63.

    let info = {};
    info.status = xhr.channel.QueryInterface(Ci.nsIRequest).status;
    info.original_uri = xhr.channel.originalURI.asciiSpec;
    info.uri = xhr.channel.URI.asciiSpec;

    try {
        info.error_class = nssErrorsService.getErrorClass(info.status);
    } catch (e) {
        info.error_class = null;
    }

    info.security_info_status = false;
    info.security_state_status = false;
    info.security_state = null;
    info.ssl_status_status = false;
    info.ssl_status_errors = null;
    info.certified_usages = null;
    info.certificate_chain_length = null;
    info.certificate_chain = null;
    info.error_code = null;
    info.raw_error = null;
    info.short_error_message = null;

    // Try to query security info
    let sec_info = xhr.channel.securityInfo;
    if (sec_info == null)
        return info;

    // If sec_info is not null, it contains SSL state info
    info.security_info_status = true;

    // Ci.nsISSLStatusProvider was removed in Firefox 63 and
    // SSLStatus moved to Ci.nsITransportSecurityInfo, so only
    // query the interface if it exists.
    if (Ci.hasOwnProperty("nsISSLStatusProvider"))
        if (sec_info instanceof Ci.nsISSLStatusProvider) {
            sec_info.QueryInterface(Ci.nsISSLStatusProvider);
        }
    if (sec_info instanceof Ci.nsITransportSecurityInfo) {
        sec_info.QueryInterface(Ci.nsITransportSecurityInfo);
    }

    // At this point, sec_info should be decorated with either one of the following property sets:
    //
    // Fx 63+
    //   securityState, errorCode, errorCodeString, failedCertList, SSLStatus
    // Fx 52-62
    //   securityState, errorCode, errorMessage, failedCertList, SSLStatus

    // Process available SSL state and transfer to info object
    if (sec_info.securityState != null) {
        info.security_state_status = true;
        info.security_state = sec_info.securityState;
    } else {
        print("WARNING: securityInfo.securityState is null");
    }

    if (sec_info.SSLStatus != null) {
        info.ssl_status_status = true;
        info.ssl_status = sec_info.SSLStatus;
        // TODO: Find way to extract this py-side.
        try {
            let usages = {};
            let usages_string = {};
            info.ssl_status.server_cert.getUsagesString(true, usages, usages_string);
            info.certified_usages = usages_string.value;
        } catch (e) {
            info.certified_usages = null;
        }
    } else {
        // Warning is too noisy
        // print("WARNING: securityInfo.SSLStatus is null");
    }

    // Process errorCodeString or errorMessage
    if (sec_info.hasOwnProperty("errorMessage")) {
        // Old message format wich needs to be parsed
        info.raw_error = sec_info.errorMessage;
        if (info.raw_error) {
            try {
                info.short_error_message = info.raw_error.split("Error code:")[1].split(">")[1].split("<")[0];
            } catch (e) {
                print("WARNING: unexpected errorMessage format: " + e.toString());
                info.short_error_message = info.raw_error;
            }
        } else {
            info.raw_error = null;
            info.short_error_message = null;
        }
    } else if (sec_info.hasOwnProperty("errorCodeString")) {
        info.raw_error = sec_info.errorCodeString;
        info.short_error_message = sec_info.errorCodeString;
    } else {
        print("WARNING: securityInfo has neither errorCodeString nor errorMessage");
    }
    if (sec_info.hasOwnProperty("errorCode")) {
        info.error_code = sec_info.errorCode;
    } else {
        print("WARNING: securityInfo has no errorCode");
    }

    // Extract certificate objects if requested
    if (info.ssl_status_status && report_certs) {
        let server_cert = info.ssl_status.serverCert;
        let cert_chain = [];
        if (server_cert.sha1Fingerprint) {
            cert_chain.push(server_cert.getRawDER({}));
            let chain = [];
            if (info.ssl_status.succeededCertChain != null) {
                chain = info.ssl_status.succeededCertChain;
            } else if (info.ssl_status.failedCertChain != null) {
                chain = info.ssl_status.failedCertChain;
            }
            let enumerator = chain.getEnumerator();

            // XPCOMUtils.IterSimpleEnumerator removed in Firefox 63 (bug 1484496)
            let cert_enumerator = XPCOMUtils.IterSimpleEnumerator ?
                XPCOMUtils.IterSimpleEnumerator(enumerator, Ci.nsIX509Cert) : enumerator;
            for (let cert of cert_enumerator) {
                cert_chain.push(cert);
            }
        }
        info.certificate_chain_length = cert_chain.length;
        info.certificate_chain = cert_chain;
    }

    // Some values might be missing from the connection state, for example due
    // to a broken SSL handshake. Try to catch exceptions before report_result's
    // JSON serializing does.
    if (info.ssl_status_status) {
        let sane_ssl_status = {};
        info.ssl_status_errors = [];
        for (let key in info.ssl_status) {
            if (!info.ssl_status.hasOwnProperty(key)) continue;
            try {
                sane_ssl_status[key] = JSON.parse(JSON.stringify(info.ssl_status[key]));
            } catch (e) {
                sane_ssl_status[key] = null;
                info.ssl_status_errors.push({key: e.toString()});
            }
        }
        info.ssl_status = sane_ssl_status;
    }

    return info;
}


function scan_host(args, response_cb) {

    let host = args.host;
    let report_certs = args.include_certificates === true;

    function load_handler(msg) {
        if (msg.target.readyState === 4) {
            response_cb(true, {origin: "load_handler", info: collect_request_info(msg.target, report_certs)});
        } else {
            response_cb(false, {origin: "load_handler", info: collect_request_info(msg.target, report_certs)});
        }
    }

    function error_handler(msg) {
        response_cb(false, {origin: "error_handler", info: collect_request_info(msg.target, report_certs)});
    }

    function abort_handler(msg) {
        response_cb(false, {origin: "abort_handler", info: collect_request_info(msg.target, report_certs)});
    }

    function timeout_handler(msg) {
        response_cb(false, {origin: "timeout_handler", info: collect_request_info(msg.target, report_certs)});
    }

    // This gets called when a redirect happens.
    function RedirectStopper() {}
    RedirectStopper.prototype = {
        asyncOnChannelRedirect: function (oldChannel, newChannel, flags, callback) {
            // This callback prevents redirects, and the request's error handler will be called.
            callback.onRedirectVerifyCallback(Cr.NS_ERROR_ABORT);
        },
        getInterface: function (iid) {
            return this.QueryInterface(iid);
        },
        QueryInterface: generateQI([Ci.nsIChannelEventSink])
    };

    let request = new XMLHttpRequest();
    try {
        request.mozBackgroundRequest = true;
        request.open("HEAD", "https://" + host, true);
        request.timeout = args.timeout ? args.timeout * 1000 : DEFAULT_TIMEOUT;
        request.channel.loadFlags |= Ci.nsIRequest.LOAD_ANONYMOUS
            | Ci.nsIRequest.LOAD_BYPASS_CACHE
            | Ci.nsIRequest.INHIBIT_PERSISTENT_CACHING
            | Ci.nsIRequest.VALIDATE_NEVER;
        request.channel.notificationCallbacks = new RedirectStopper();
        request.addEventListener("load", load_handler, false);
        request.addEventListener("error", error_handler, false);
        request.addEventListener("abort", abort_handler, false);
        request.addEventListener("timeout", timeout_handler, false);
        request.send(null);
    } catch (error) {
        // This is supposed to catch malformed host names, but could
        // potentially mask other errors.
        response_cb(false, {origin: "request_error", error: error, info: collect_request_info(request, false)});
    }
}

register_command("scan", scan_host);

run_loop();