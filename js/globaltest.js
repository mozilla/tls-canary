/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

"use strict";

const { classes: Cc, interfaces: Ci, utils: Cu, results: Cr } = Components;

const DEFAULT_TIMEOUT = 10000;

Cu.import("resource://gre/modules/Services.jsm");
Cu.import("resource://gre/modules/XPCOMUtils.jsm");
Cu.import("resource://gre/modules/NetUtil.jsm");



function scan_url(args, report_cb) {

    let url = args.url;
    //const { classes: Cc, interfaces: Ci, utils: Cu, results: Cr } = Components;

    function collect_request_info(xhr) {
        return {dummy: true};
    }

    print("hello");

    // CAVE: no print and JSON globals from inside request handlers
    function load_handler(msg) {
        if (msg.target.readyState === 4) {
            report_cb(true, {origin: "load_handler", info: collect_request_info(msg.target)});
        } else {
            report_cb(false, {origin: "load_handler", info: collect_request_info(msg.target)});
        }
    }

    function error_handler(msg) {
        report_cb(false, {origin: "error_handler", info: collect_request_info(msg.target)});
    }

    function abort_handler(msg) {
        report_cb(false, {origin: "abort_handler", info: collect_request_info(msg.target)});
    }

    function timeout_handler(msg) {
        report_cb(false, {origin: "timeout_handler", info: collect_request_info(msg.target)});
    }

    function RedirectStopper() {}
    RedirectStopper.prototype = {
        // nsIChannelEventSink
        asyncOnChannelRedirect: function (oldChannel, newChannel, flags, callback) {
            throw Cr.NS_ERROR_ENTITY_CHANGED;
        },
        getInterface: function (iid) {
            return this.QueryInterface(iid);
        },
        QueryInterface: XPCOMUtils.generateQI([Ci.nsIChannelEventSink])
    };

    let req = Cc["@mozilla.org/xmlextras/xmlhttprequest;1"].createInstance(Ci.nsIXMLHttpRequest);
    try {
        req.mozBackgroundRequest = true;

        req.open("HEAD", "https://" + url, true);
        req.timeout = DEFAULT_TIMEOUT;
        req.channel.loadFlags |= Ci.nsIRequest.LOAD_ANONYMOUS | Ci.nsIRequest.LOAD_BYPASS_CACHE
            | Ci.nsIRequest.INHIBIT_PERSISTENT_CACHING;
        req.channel.notificationCallbacks = new RedirectStopper();
        req.addEventListener("load", load_handler, false);
        req.addEventListener("error", error_handler, false);
        req.addEventListener("abort", abort_handler, false);
        req.addEventListener("timeout", timeout_handler, false);
        req.send(null);
    } catch (error) {
        report_cb(false, {origin: "request_error", error: error, info: collect_request_info(req)});
    }
}


// Command object definition. Must be in-sync with Python world.
// This is used for keeping state throughout async command handling.
function Command(json_string) {
    let parsed_command = JSON.parse(json_string);
    this.id = parsed_command.id;
    this.mode = parsed_command.mode;
    this.args = parsed_command.args;
    // Strange workaround for a strange bug where the code path through an
    // XMLHTTPRequest's error handler has `JSON` and `print` undefined.
    this.JSON = JSON;
    this.print = print;
}

// Even though it's a prototype method it will require bind when passed as callback.
Command.prototype.report_result = function _report_result(success, response) {
    // Send a response back to the python world
    this.print(this.JSON.stringify({
        "id": this.id,
        "success": success,
        "response": response
    }));
};

Command.prototype.handle = function _handle() {
    switch (this.mode) {
        case "scan":
            // .bind is required for callback, because else we get
            // 'this is undefined' when called from request handlers.
            scan_url(this.args, this.report_result.bind(this));
            break;
        case "wakeup":
            while (mainThread.hasPendingEvents()) mainThread.processNextEvent(true);
            this.report_result(true, "OK");
            break;
        default:
            this.report_result(false, "Unknown command mode");
    }
};


// Respect async processing
let gThreadManager = Cc["@mozilla.org/thread-manager;1"].getService(Ci.nsIThreadManager);
let mainThread = gThreadManager.mainThread;

let cmd = new Command('{"id":"1","mode":"scan","args":{"url":"google.com","rank":1}}');
cmd.handle();

// Intentional re-use of cmd here. Old ref gone. Problem?
cmd = new Command('{"id":"2","mode":"wakeup"}');
cmd.handle();
