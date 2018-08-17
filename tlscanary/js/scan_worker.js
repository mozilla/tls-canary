/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

"use strict";

const { classes: Cc, interfaces: Ci, utils: Cu, results: Cr } = Components;

const DEFAULT_TIMEOUT = 10000;

// This is a global random ID that is sent with every message to the Python world
const worker_id = Math.floor(Math.random() * 2**64);


Cu.import("resource://gre/modules/Services.jsm");
Cu.import("resource://gre/modules/XPCOMUtils.jsm");
Cu.import("resource://gre/modules/NetUtil.jsm");
Cu.import("resource://gre/modules/AppConstants.jsm");
Cu.importGlobalProperties(["XMLHttpRequest"]);

const nsINSSErrorsService = Ci.nsINSSErrorsService;
let nssErrorsService = Cc['@mozilla.org/nss_errors_service;1'].getService(nsINSSErrorsService);


function get_runtime_info() {
    return {
        nssInfo: Cc["@mozilla.org/security/nssversion;1"].getService(Ci.nsINSSVersion),
        appConstants: AppConstants
    };
}


function set_prefs(prefs) {
    for (let key in prefs) {
        let prop = prefs[key].split(";")[0];
        let value = prefs[key].split(";")[1];

        // Pref values are passed in as strings and must be examined
        // to determine the intended types and values.
        let type = "string"; // default
        if (value === "true" || value === "false") type = "boolean";
        if (!isNaN(value)) type = "number";
        if (value == undefined) type = "undefined";

        switch (type) {
            case "boolean":
                Services.prefs.setBoolPref(prop, value === "true" ? 1 : 0);
                break;
            case "number":
                Services.prefs.setIntPref(prop, value);
                break;
            case "string":
                Services.prefs.setPref(prop, value);
                break;
            default:
                throw "Unsupported pref type " + type;
        }
    }
}


function set_profile(profile_path) {
    let file = Cc["@mozilla.org/file/local;1"]
        .createInstance(Ci.nsIFile);
    file.initWithPath(profile_path);
    let dir_service = Cc["@mozilla.org/file/directory_service;1"]
        .getService(Ci.nsIProperties);
    let provider = {
        getFile: function(prop, persistent) {
            persistent.value = true;
            if (prop == "ProfD" || prop == "ProfLD" || prop == "ProfDS" ||
                prop == "ProfLDS" || prop == "PrefD" || prop == "TmpD") {
                return file.clone();
            }
            return null;
        },
        QueryInterface: function(iid) {
            if (iid.equals(Ci.nsIDirectoryServiceProvider) ||
                iid.equals(Ci.nsISupports)) {
                return this;
            }
            throw Cr.NS_ERROR_NO_INTERFACE;
        }
    };
    dir_service.QueryInterface(Ci.nsIDirectoryService)
        .registerProvider(provider);

    // The methods of 'provider' will retain this scope so null out
    // everything to avoid spurious leak reports.
    profile_path = null;
    dir_service = null;
    provider = null;

    return file.clone();
}


function collect_request_info(xhr, report_certs) {
    // Much of this is documented in https://developer.mozilla.org/en-US/docs/Web/API/
    // XMLHttpRequest/How_to_check_the_secruity_state_of_an_XMLHTTPRequest_over_SSL

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
    info.transport_security_info_status = false;
    info.ssl_status_status = false;

    // Try to query security info
    let sec_info = xhr.channel.securityInfo;
    if (sec_info == null) return info;
    info.security_info_status = true;

    if (sec_info instanceof Ci.nsITransportSecurityInfo) {
        sec_info.QueryInterface(Ci.nsITransportSecurityInfo);
        info.transport_security_info_status = true;
        info.security_state = sec_info.securityState;
        info.raw_error = sec_info.errorMessage;
        try {
            info.short_error_message = info.raw_error.split("Error code:")[1].split(">")[1].split("<")[0];
        } catch (e) {
            info.short_error_message = info.raw_error;
        }
    }

    if (sec_info instanceof Ci.nsITransportSecurityInfo) {
        info.ssl_status_status = false;
        let ssl_status = sec_info.QueryInterface(Ci.nsITransportSecurityInfo).SSLStatus;
        if (ssl_status != null) {
            info.ssl_status_status = true;
            info.ssl_status = ssl_status.QueryInterface(Ci.nsISSLStatus);
            // TODO: Find way to extract this py-side.
            try {
                let usages = {};
                let usages_string = {};
                info.ssl_status.server_cert.getUsagesString(true, usages, usages_string);
                info.certified_usages = usages_string.value;
            } catch (e) {
                info.certified_usages = null;
            }
        }
    }

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
            let cert_enumerator = XPCOMUtils.IterSimpleEnumerator(enumerator, Ci.nsIX509Cert);
            for (let cert of cert_enumerator) {
                cert_chain.push(cert);
            }
        }
        info.certificate_chain_length = cert_chain.length;
        info.certificate_chain = cert_chain;
    }

    if (info.ssl_status_status) {
        // Some values might be missing from the connection state, for example due
        // to a broken SSL handshake. Try to catch exceptions before report_result's
        // JSON serializing does.
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
        QueryInterface: XPCOMUtils.generateQI([Ci.nsIChannelEventSink])
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


// Command object definition. Must be in-sync with Python world.
// This is used for keeping state throughout async command handling.
function Command(json_string) {
    let parsed_command = JSON.parse(json_string);
    this.id = parsed_command.id ? parsed_command.id : Math.floor(Math.random() * 2**64);
    this.mode = parsed_command.mode;
    this.args = parsed_command.args;
    this.original_cmd = parsed_command;
    this.start_time = new Date();
}

// Even though it's a prototype method it will require bind when passed as callback.
Command.prototype.send_response = function _report_result(success, result) {
    // Send a response back to the python world
    print(JSON.stringify({
        "id": this.id,
        "worker_id": worker_id,
        "original_cmd": this.original_cmd,
        "success": success,
        "result": result,
        "command_time": this.start_time.getTime(),
        "response_time": new Date().getTime(),
    }));
};

Command.prototype.handle = function _handle() {
    switch (this.mode) {
        case "info":
            this.send_response(true, get_runtime_info());
            break;
        case "useprofile":
            set_profile(this.args.path);
            this.send_response(true, "ACK");
            break;
        case "setprefs":
            set_prefs(this.args.prefs);
            this.send_response(true, "ACK");
            break;
        case "scan":
            // .bind is required for callback to avoid
            // 'this is undefined' when called from request handlers.
            scan_host(this.args, this.send_response.bind(this));
            this.send_response(true, "ACK");
            break;
        case "quit":
            script_done = true;
            // Intentional fall-through
        case "wakeup":
            while (main_thread.hasPendingEvents()) main_thread.processNextEvent(true);
            this.send_response(true, "ACK");
            break;
        default:
            this.send_response(false, "Unknown command mode: " + this.mode);
    }
};


// The main loop only reads and handles commands from stdin.

let script_done = false;
let thread_manager = Cc["@mozilla.org/thread-manager;1"].getService(Ci.nsIThreadManager);
let main_thread = thread_manager.mainThread;

while (!script_done) {
    let cmd = null;
    try {
        cmd = new Command(readline());
        cmd.handle();
    } catch (error) {
        print(error);
    }
}
