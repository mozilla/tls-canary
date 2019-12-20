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

let custom_commands = [];

// generateQI was moved from XPCOMUtils to ChromeUtils in Fx 63
let generateQI = ChromeUtils.generateQI ? ChromeUtils.generateQI : XPCOMUtils.generateQI;
if (!generateQI) {
    print("WARNING: no valid generateQI found");
}


function get_runtime_info() {
    const ac = JSON.parse(JSON.stringify(AppConstants));
    for (let key in ac) {
        if (key.endsWith("API_KEY")) {
            ac[key] = "__STRIPPED__";
        }
    }
    return {
        nssInfo: Cc["@mozilla.org/security/nssversion;1"].getService(Ci.nsINSSVersion),
        appConstants: ac
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

function register_command(name, callback) {
    custom_commands[name] = callback;
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
        case "quit":
            script_done = true;
            // Intentional fall-through
        case "wakeup":
            while (main_thread.hasPendingEvents()) main_thread.processNextEvent(true);
            this.send_response(true, "ACK");
            break;
        default:
            let custom_command = custom_commands[this.mode];
            if (undefined !== custom_command) {
                custom_command(this.args, this.send_response.bind(this));
                this.send_response(true, "ACK");
            } else {
                this.send_response(false, "Unknown command mode: " + this.mode);
            }
    }
};


// The main loop only reads and handles commands from stdin.
let script_done = false;
let thread_manager = Cc["@mozilla.org/thread-manager;1"].getService(Ci.nsIThreadManager);
let main_thread = thread_manager.mainThread;

function run_loop() {
    while (!script_done) {
        let cmd = null;
        try {
            cmd = new Command(readline());
            cmd.handle();
        } catch (error) {
            print(error);
        }
    }
}