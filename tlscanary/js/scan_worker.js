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

        try {
            // We are looking for an error code
            info.raw_error = info.status.toString(16);
        } catch (e) {
            info.raw_error = "unknown"
        }

        // Look up error code in error string table
        info.short_error_message = get_error_string(info.status.toString(16));
    }

    if (sec_info instanceof Ci.nsISSLStatusProvider) {
        info.ssl_status_status = false;
        let ssl_status = sec_info.QueryInterface(Ci.nsISSLStatusProvider).SSLStatus;
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
            let chain = server_cert.getChain().enumerate();
            while (chain.hasMoreElements()) {
                let child_cert = chain.getNext().QueryInterface(Ci.nsISupports)
                    .QueryInterface(Ci.nsIX509Cert);
                cert_chain.push(child_cert.getRawDER({}));
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

function get_error_string(error_code) {
  // https://developer.mozilla.org/en-US/docs/Mozilla/Errors
  // http://archive.is/UJFrv#selection-1947.0-2921.10

    var error_table = {
        "80004005": "PR_INVALID_ARGUMENT_ERROR",
        "8000FFFF": "UNEXPECTED_ERROR",
        "804B0001": "NS_BINDING_FAILED",
        "804B0002": "NS_BINDING_ABORTED",
        "804B0003": "NS_BINDING_REDIRECTED",
        "804B0004": "NS_BINDING_RETARGETED",
        "804B000A": "NS_ERROR_MALFORMED_URI",
        "804B000B": "NS_ERROR_ALREADY_CONNECTED",
        "804B000C": "NS_ERROR_NOT_CONNECTED",
        "804B000D": "NS_ERROR_CONNECTION_REFUSED",
        "804B000E": "NS_ERROR_NET_TIMEOUT",
        "804B000F": "NS_ERROR_IN_PROGRESS",
        "804B0010": "NS_ERROR_OFFLINE",
        "804B0011": "NS_ERROR_NO_CONTENT",
        "804B0012": "NS_ERROR_UNKNOWN_PROTOCOL",
        "804B0013": "NS_ERROR_PORT_ACCESS_NOT_ALLOWED",
        "804B0014": "NS_ERROR_NET_RESET",
        "804B0015": "NS_ERROR_FTP_LOGIN",
        "804B0016": "NS_ERROR_FTP_CWD",
        "804B0017": "NS_ERROR_FTP_PASV",
        "804B0018": "NS_ERROR_FTP_PWD",
        "804B0019": "NS_ERROR_NOT_RESUMABLE",
        "804B001B": "NS_ERROR_INVALID_CONTENT_ENCODING",
        "804B001C": "NS_ERROR_FTP_LIST",
        "804B001E": "NS_ERROR_UNKNOWN_HOST",
        "804B001F": "NS_ERROR_REDIRECT_LOOP",
        "804B0020": "NS_ERROR_ENTITY_CHANGED",
        "804B0021": "NS_ERROR_DNS_LOOKUP_QUEUE_FULL",
        "804B002A": "NS_ERROR_UNKNOWN_PROXY_HOST",
        "804B0033": "NS_ERROR_UNKNOWN_SOCKET_TYPE",
        "804B0034": "NS_ERROR_SOCKET_CREATE_FAILED",
        "804B003D": "NS_ERROR_CACHE_KEY_NOT_FOUND",
        "804B003E": "NS_ERROR_CACHE_DATA_IS_STREAM",
        "804B003F": "NS_ERROR_CACHE_DATA_IS_NOT_STREAM",
        "804B0040": "NS_ERROR_CACHE_WAIT_FOR_VALIDATION",
        "804B0041": "NS_ERROR_CACHE_ENTRY_DOOMED",
        "804B0042": "NS_ERROR_CACHE_READ_ACCESS_DENIED",
        "804B0043": "NS_ERROR_CACHE_WRITE_ACCESS_DENIED",
        "804B0044": "NS_ERROR_CACHE_IN_USE",
        "804B0046": "NS_ERROR_DOCUMENT_NOT_CACHED",
        "804B0047": "NS_ERROR_NET_INTERRUPT",
        "804B0047": "PR_END_OF_FILE_ERROR",
        "804B0048": "NS_ERROR_PROXY_CONNECTION_REFUSED",
        "804B0049": "NS_ERROR_ALREADY_OPENED",
        "804B004A": "NS_ERROR_UNSAFE_CONTENT_TYPE",
        "804B004B": "NS_ERROR_REMOTE_XUL",
        "804B0050": "NS_ERROR_INSUFFICIENT_DOMAIN_LEVELS",
        "804B0051": "NS_ERROR_HOST_IS_IP_ADDRESS",
        "80590001": "NS_ERROR_LDAP_OPERATIONS_ERROR",
        "80590002": "NS_ERROR_LDAP_PROTOCOL_ERROR",
        "80590003": "NS_ERROR_LDAP_TIMELIMIT_EXCEEDED",
        "80590004": "NS_ERROR_LDAP_SIZELIMIT_EXCEEDED",
        "80590005": "NS_ERROR_LDAP_COMPARE_FALSE",
        "80590006": "NS_ERROR_LDAP_COMPARE_TRUE",
        "80590007": "NS_ERROR_LDAP_STRONG_AUTH_NOT_SUPPORTED",
        "80590008": "NS_ERROR_LDAP_STRONG_AUTH_REQUIRED",
        "80590009": "NS_ERROR_LDAP_PARTIAL_RESULTS",
        "8059000A": "NS_ERROR_LDAP_REFERRAL",
        "8059000B": "NS_ERROR_LDAP_ADMINLIMIT_EXCEEDED",
        "8059000C": "NS_ERROR_LDAP_UNAVAILABLE_CRITICAL_EXTENSION",
        "8059000D": "NS_ERROR_LDAP_CONFIDENTIALITY_REQUIRED",
        "8059000E": "NS_ERROR_LDAP_SASL_BIND_IN_PROGRESS",
        "80590010": "NS_ERROR_LDAP_NO_SUCH_ATTRIBUTE",
        "80590011": "NS_ERROR_LDAP_UNDEFINED_TYPE",
        "80590012": "NS_ERROR_LDAP_INAPPROPRIATE_MATCHING",
        "80590013": "NS_ERROR_LDAP_CONSTRAINT_VIOLATION",
        "80590014": "NS_ERROR_LDAP_TYPE_OR_VALUE_EXISTS",
        "80590015": "NS_ERROR_LDAP_INVALID_SYNTAX",
        "80590020": "NS_ERROR_LDAP_NO_SUCH_OBJECT",
        "80590021": "NS_ERROR_LDAP_ALIAS_PROBLEM",
        "80590022": "NS_ERROR_LDAP_INVALID_DN_SYNTAX",
        "80590023": "NS_ERROR_LDAP_IS_LEAF",
        "80590024": "NS_ERROR_LDAP_ALIAS_DEREF_PROBLEM",
        "80590030": "NS_ERROR_LDAP_INAPPROPRIATE_AUTH",
        "80590031": "NS_ERROR_LDAP_INVALID_CREDENTIALS",
        "80590032": "NS_ERROR_LDAP_INSUFFICIENT_ACCESS",
        "80590033": "NS_ERROR_LDAP_BUSY",
        "80590034": "NS_ERROR_LDAP_UNAVAILABLE",
        "80590035": "NS_ERROR_LDAP_UNWILLING_TO_PERFORM",
        "80590036": "NS_ERROR_LDAP_LOOP_DETECT",
        "8059003C": "NS_ERROR_LDAP_SORT_CONTROL_MISSING",
        "8059003D": "NS_ERROR_LDAP_INDEX_RANGE_ERROR",
        "80590040": "NS_ERROR_LDAP_NAMING_VIOLATION",
        "80590041": "NS_ERROR_LDAP_OBJECT_CLASS_VIOLATION",
        "80590042": "NS_ERROR_LDAP_NOT_ALLOWED_ON_NONLEAF",
        "80590043": "NS_ERROR_LDAP_NOT_ALLOWED_ON_RDN",
        "80590044": "NS_ERROR_LDAP_ALREADY_EXISTS",
        "80590045": "NS_ERROR_LDAP_NO_OBJECT_CLASS_MODS",
        "80590046": "NS_ERROR_LDAP_RESULTS_TOO_LARGE",
        "80590047": "NS_ERROR_LDAP_AFFECTS_MULTIPLE_DSAS",
        "80590050": "NS_ERROR_LDAP_OTHER",
        "80590051": "NS_ERROR_LDAP_SERVER_DOWN",
        "80590052": "NS_ERROR_LDAP_LOCAL_ERROR",
        "80590053": "NS_ERROR_LDAP_ENCODING_ERROR",
        "80590054": "NS_ERROR_LDAP_DECODING_ERROR",
        "80590055": "NS_ERROR_LDAP_TIMEOUT",
        "80590056": "NS_ERROR_LDAP_AUTH_UNKNOWN",
        "80590057": "NS_ERROR_LDAP_FILTER_ERROR",
        "80590058": "NS_ERROR_LDAP_USER_CANCELLED",
        "80590059": "NS_ERROR_LDAP_PARAM_ERROR",
        "8059005A": "NS_ERROR_LDAP_NO_MEMORY",
        "8059005B": "NS_ERROR_LDAP_CONNECT_ERROR",
        "8059005C": "NS_ERROR_LDAP_NOT_SUPPORTED",
        "8059005D": "NS_ERROR_LDAP_CONTROL_NOT_FOUND",
        "8059005E": "NS_ERROR_LDAP_NO_RESULTS_RETURNED",
        "8059005F": "NS_ERROR_LDAP_MORE_RESULTS_TO_RETURN",
        "80590060": "NS_ERROR_LDAP_CLIENT_LOOP",
        "80590061": "NS_ERROR_LDAP_REFERRAL_LIMIT_EXCEEDED",
        "805A0063": "NS_ERROR_CSP_FRAME_ANCESTOR_VIOLATION",
        "805A0400": "NS_ERROR_CMS_VERIFY_NOT_SIGNED",
        "805A0401": "NS_ERROR_CMS_VERIFY_NO_CONTENT_INFO",
        "805A0402": "NS_ERROR_CMS_VERIFY_BAD_DIGEST",
        "805A0404": "NS_ERROR_CMS_VERIFY_NOCERT",
        "805A0405": "NS_ERROR_CMS_VERIFY_UNTRUSTED",
        "805A0407": "NS_ERROR_CMS_VERIFY_ERROR_UNVERIFIED",
        "805A0408": "NS_ERROR_CMS_VERIFY_ERROR_PROCESSING",
        "805A0409": "NS_ERROR_CMS_VERIFY_BAD_SIGNATURE",
        "805A040A": "NS_ERROR_CMS_VERIFY_DIGEST_MISMATCH",
        "805A040B": "NS_ERROR_CMS_VERIFY_UNKNOWN_ALGO",
        "805A040C": "NS_ERROR_CMS_VERIFY_UNSUPPORTED_ALGO",
        "805A040D": "NS_ERROR_CMS_VERIFY_MALFORMED_SIGNATURE",
        "805A040E": "NS_ERROR_CMS_VERIFY_HEADER_MISMATCH",
        "805A040F": "NS_ERROR_CMS_VERIFY_NOT_YET_ATTEMPTED",
        "805A0410": "NS_ERROR_CMS_VERIFY_CERT_WITHOUT_ADDRESS",
        "805A0420": "NS_ERROR_CMS_ENCRYPT_NO_BULK_ALG",
        "805A0421": "NS_ERROR_CMS_ENCRYPT_INCOMPLETE",
        "805A1F51": "SEC_ERROR_BAD_CRL_DP_URL",
        "805A1F52": "SEC_ERROR_UNKNOWN_PKCS11_ERROR",
        "805A1F53": "SEC_ERROR_LOCKED_PASSWORD",
        "805A1F54": "SEC_ERROR_EXPIRED_PASSWORD",
        "805A1F55": "SEC_ERROR_CRL_IMPORT_FAILED",
        "805A1F56": "SEC_ERROR_BAD_INFO_ACCESS_METHOD",
        "805A1F57": "SEC_ERROR_PKCS11_DEVICE_ERROR",
        "805A1F58": "SEC_ERROR_PKCS11_FUNCTION_FAILED",
        "805A1F59": "SEC_ERROR_PKCS11_GENERAL_ERROR",
        "805A1F5A": "SEC_ERROR_LIBPKIX_INTERNAL",
        "805A1F5B": "SEC_ERROR_BAD_INFO_ACCESS_LOCATION",
        "805A1F5C": "SEC_ERROR_FAILED_TO_ENCODE_DATA",
        "805A1F5D": "SEC_ERROR_BAD_LDAP_RESPONSE",
        "805A1F5E": "SEC_ERROR_BAD_HTTP_RESPONSE",
        "805A1F5F": "SEC_ERROR_UNKNOWN_AIA_LOCATION_TYPE",
        "805A1F60": "SEC_ERROR_POLICY_VALIDATION_FAILED",
        "805A1F61": "SEC_ERROR_INVALID_POLICY_MAPPING",
        "805A1F62": "SEC_ERROR_OUT_OF_SEARCH_LIMITS",
        "805A1F63": "SEC_ERROR_OCSP_BAD_SIGNATURE",
        "805A1F64": "SEC_ERROR_OCSP_RESPONDER_CERT_INVALID",
        "805A1F65": "SEC_ERROR_TOKEN_NOT_LOGGED_IN",
        "805A1F66": "SEC_ERROR_NOT_INITIALIZED",
        "805A1F67": "SEC_ERROR_CRL_ALREADY_EXISTS",
        "805A1F68": "SEC_ERROR_NO_EVENT",
        "805A1F69": "SEC_ERROR_INCOMPATIBLE_PKCS11",
        "805A1F6A": "SEC_ERROR_UNKNOWN_OBJECT_TYPE",
        "805A1F6B": "SEC_ERROR_CRL_UNKNOWN_CRITICAL_EXTENSION",
        "805A1F6C": "SEC_ERROR_CRL_V1_CRITICAL_EXTENSION",
        "805A1F6D": "SEC_ERROR_CRL_INVALID_VERSION",
        "805A1F6E": "SEC_ERROR_REVOKED_CERTIFICATE_OCSP",
        "805A1F6F": "SEC_ERROR_REVOKED_CERTIFICATE_CRL",
        "805A1F70": "SEC_ERROR_OCSP_INVALID_SIGNING_CERT",
        "805A1F71": "SEC_ERROR_UNRECOGNIZED_OID",
        "805A1F72": "SEC_ERROR_UNSUPPORTED_EC_POINT_FORM",
        "805A1F73": "SEC_ERROR_UNSUPPORTED_ELLIPTIC_CURVE",
        "805A1F74": "SEC_ERROR_EXTRA_INPUT",
        "805A1F75": "SEC_ERROR_BUSY",
        "805A1F76": "SEC_ERROR_REUSED_ISSUER_AND_SERIAL",
        "805A1F77": "SEC_ERROR_CRL_NOT_FOUND",
        "805A1F78": "SEC_ERROR_BAD_TEMPLATE",
        "805A1F79": "SEC_ERROR_MODULE_STUCK",
        "805A1F7A": "SEC_ERROR_UNSUPPORTED_MESSAGE_TYPE",
        "805A1F7B": "SEC_ERROR_DIGEST_NOT_FOUND",
        "805A1F7C": "SEC_ERROR_OCSP_OLD_RESPONSE",
        "805A1F7D": "SEC_ERROR_OCSP_FUTURE_RESPONSE",
        "805A1F7E": "SEC_ERROR_OCSP_UNAUTHORIZED_RESPONSE",
        "805A1F7F": "SEC_ERROR_OCSP_MALFORMED_RESPONSE",
        "805A1F80": "SEC_ERROR_OCSP_NO_DEFAULT_RESPONDER",
        "805A1F81": "SEC_ERROR_OCSP_NOT_ENABLED",
        "805A1F82": "SEC_ERROR_OCSP_UNKNOWN_CERT",
        "805A1F83": "SEC_ERROR_OCSP_UNKNOWN_RESPONSE_STATUS",
        "805A1F84": "SEC_ERROR_OCSP_UNAUTHORIZED_REQUEST",
        "805A1F85": "SEC_ERROR_OCSP_REQUEST_NEEDS_SIG",
        "805A1F86": "SEC_ERROR_OCSP_TRY_SERVER_LATER",
        "805A1F87": "SEC_ERROR_OCSP_SERVER_ERROR",
        "805A1F88": "SEC_ERROR_OCSP_MALFORMED_REQUEST",
        "805A1F89": "SEC_ERROR_OCSP_BAD_HTTP_RESPONSE",
        "805A1F8A": "SEC_ERROR_OCSP_UNKNOWN_RESPONSE_TYPE",
        "805A1F8B": "SEC_ERROR_CERT_BAD_ACCESS_LOCATION",
        "805A1F8C": "SEC_ERROR_UNKNOWN_SIGNER",
        "805A1F8D": "SEC_ERROR_UNKNOWN_CERT",
        "805A1F8E": "SEC_ERROR_CRL_NOT_YET_VALID",
        "805A1F8F": "SEC_ERROR_KRL_NOT_YET_VALID",
        "805A1F90": "SEC_ERROR_CERT_NOT_IN_NAME_SPACE",
        "805A1F91": "SEC_ERROR_CKL_CONFLICT",
        "805A1F92": "SEC_ERROR_OLD_KRL",
        "805A1F93": "SEC_ERROR_JS_DEL_MOD_FAILURE",
        "805A1F94": "SEC_ERROR_JS_ADD_MOD_FAILURE",
        "805A1F95": "SEC_ERROR_JS_INVALID_DLL",
        "805A1F96": "SEC_ERROR_JS_INVALID_MODULE_NAME",
        "805A1F97": "SEC_ERROR_CANNOT_MOVE_SENSITIVE_KEY",
        "805A1F98": "SEC_ERROR_NOT_FORTEZZA_ISSUER",
        "805A1F99": "SEC_ERROR_BAD_NICKNAME",
        "805A1F9A": "SEC_ERROR_RETRY_OLD_PASSWORD",
        "805A1F9B": "SEC_ERROR_INVALID_PASSWORD",
        "805A1F9C": "SEC_ERROR_KEYGEN_FAIL",
        "805A1F9D": "SEC_ERROR_PKCS12_KEY_DATABASE_NOT_INITIALIZED",
        "805A1F9E": "SEC_ERROR_PKCS12_UNABLE_TO_READ",
        "805A1F9F": "SEC_ERROR_PKCS12_UNABLE_TO_WRITE",
        "805A1FA0": "SEC_ERROR_PKCS12_UNABLE_TO_EXPORT_KEY",
        "805A1FA1": "SEC_ERROR_PKCS12_UNABLE_TO_LOCATE_OBJECT_BY_NAME",
        "805A1FA2": "SEC_ERROR_PKCS12_IMPORTING_CERT_CHAIN",
        "805A1FA3": "SEC_ERROR_PKCS12_UNABLE_TO_IMPORT_KEY",
        "805A1FA4": "SEC_ERROR_CERT_ADDR_MISMATCH",
        "805A1FA5": "SEC_ERROR_INADEQUATE_CERT_TYPE",
        "805A1FA6": "SEC_ERROR_INADEQUATE_KEY_USAGE",
        "805A1FA7": "SEC_ERROR_MESSAGE_SEND_ABORTED",
        "805A1FA8": "SEC_ERROR_PKCS12_DUPLICATE_DATA",
        "805A1FA9": "SEC_ERROR_USER_CANCELLED",
        "805A1FAA": "SEC_ERROR_PKCS12_CERT_COLLISION",
        "805A1FAB": "SEC_ERROR_PKCS12_PRIVACY_PASSWORD_INCORRECT",
        "805A1FAC": "SEC_ERROR_PKCS12_UNSUPPORTED_VERSION",
        "805A1FAD": "SEC_ERROR_PKCS12_UNSUPPORTED_PBE_ALGORITHM",
        "805A1FAE": "SEC_ERROR_PKCS12_CORRUPT_PFX_STRUCTURE",
        "805A1FAF": "SEC_ERROR_PKCS12_UNSUPPORTED_TRANSPORT_MODE",
        "805A1FB0": "SEC_ERROR_PKCS12_UNSUPPORTED_MAC_ALGORITHM",
        "805A1FB1": "SEC_ERROR_PKCS12_INVALID_MAC",
        "805A1FB2": "SEC_ERROR_PKCS12_DECODING_PFX",
        "805A1FB3": "SEC_ERROR_IMPORTING_CERTIFICATES",
        "805A1FB4": "SEC_ERROR_EXPORTING_CERTIFICATES",
        "805A1FB5": "SEC_ERROR_BAD_EXPORT_ALGORITHM",
        "805A1FB9": "SEC_ERROR_BAGGAGE_NOT_CREATED",
        "805A1FBA": "SEC_ERROR_SAFE_NOT_CREATED",
        "805A1FBB": "SEC_ERROR_KEY_NICKNAME_COLLISION",
        "805A1FBC": "SEC_ERROR_CERT_NICKNAME_COLLISION",
        "805A1FBD": "SEC_ERROR_NO_SLOT_SELECTED",
        "805A1FBE": "SEC_ERROR_READ_ONLY",
        "805A1FBF": "SEC_ERROR_NO_TOKEN",
        "805A1FC0": "SEC_ERROR_NO_MODULE",
        "805A1FC1": "SEC_ERROR_NEED_RANDOM",
        "805A1FC2": "SEC_ERROR_KRL_INVALID",
        "805A1FC3": "SEC_ERROR_REVOKED_KEY",
        "805A1FC4": "SEC_ERROR_KRL_BAD_SIGNATURE",
        "805A1FC5": "SEC_ERROR_KRL_EXPIRED",
        "805A1FC6": "SEC_ERROR_NO_KRL",
        "805A1FCF": "SEC_ERROR_DECRYPTION_DISALLOWED",
        "805A1FD0": "SEC_ERROR_UNSUPPORTED_KEYALG",
        "805A1FD1": "SEC_ERROR_PKCS7_BAD_SIGNATURE",
        "805A1FD2": "SEC_ERROR_PKCS7_KEYALG_MISMATCH",
        "805A1FD3": "SEC_ERROR_NOT_A_RECIPIENT",
        "805A1FD4": "SEC_ERROR_NO_RECIPIENT_CERTS_QUERY",
        "805A1FD5": "SEC_ERROR_NO_EMAIL_CERT",
        "805A1FD6": "SEC_ERROR_OLD_CRL",
        "805A1FD7": "SEC_ERROR_UNKNOWN_CRITICAL_EXTENSION",
        "805A1FD8": "SEC_ERROR_INVALID_KEY",
        "805A1FDA": "SEC_ERROR_CERT_USAGES_INVALID",
        "805A1FDB": "SEC_ERROR_PATH_LEN_CONSTRAINT_INVALID",
        "805A1FDC": "SEC_ERROR_CA_CERT_INVALID",
        "805A1FDD": "SEC_ERROR_EXTENSION_NOT_FOUND",
        "805A1FDE": "SEC_ERROR_EXTENSION_VALUE_INVALID",
        "805A1FDF": "SEC_ERROR_CRL_INVALID",
        "805A1FE0": "SEC_ERROR_CRL_BAD_SIGNATURE",
        "805A1FE1": "SEC_ERROR_CRL_EXPIRED",
        "805A1FE2": "SEC_ERROR_EXPIRED_ISSUER_CERTIFICATE",
        "805A1FE3": "SEC_ERROR_CERT_NO_RESPONSE",
        "805A1FE4": "SEC_ERROR_CERT_NOT_VALID",
        "805A1FE5": "SEC_ERROR_CERT_VALID",
        "805A1FE6": "SEC_ERROR_NO_KEY",
        "805A1FE7": "SEC_ERROR_FILING_KEY",
        "805A1FE8": "SEC_ERROR_ADDING_CERT",
        "805A1FE9": "SEC_ERROR_DUPLICATE_CERT_NAME",
        "805A1FEA": "SEC_ERROR_DUPLICATE_CERT",
        "805A1FEB": "SEC_ERROR_UNTRUSTED_CERT",
        "805A1FEC": "SEC_ERROR_UNTRUSTED_ISSUER",
        "805A1FED": "SEC_ERROR_NO_MEMORY",
        "805A1FEE": "SEC_ERROR_BAD_DATABASE",
        "805A1FEF": "SEC_ERROR_NO_NODELOCK",
        "805A1FF0": "SEC_ERROR_RETRY_PASSWORD",
        "805A1FF1": "SEC_ERROR_BAD_PASSWORD",
        "805A1FF2": "SEC_ERROR_BAD_KEY",
        "805A1FF3": "SEC_ERROR_UNKNOWN_ISSUER",
        "805A1FF4": "SEC_ERROR_REVOKED_CERTIFICATE",
        "805A1FF5": "SEC_ERROR_EXPIRED_CERTIFICATE",
        "805A1FF6": "SEC_ERROR_BAD_SIGNATURE",
        "805A1FF7": "SEC_ERROR_BAD_DER",
        "805A1FF8": "SEC_ERROR_INVALID_TIME",
        "805A1FF9": "SEC_ERROR_INVALID_AVA",
        "805A1FFA": "SEC_ERROR_INVALID_ALGORITHM",
        "805A1FFB": "SEC_ERROR_INVALID_ARGS",
        "805A1FFC": "SEC_ERROR_INPUT_LEN",
        "805A1FFD": "SEC_ERROR_OUTPUT_LEN",
        "805A1FFE": "SEC_ERROR_BAD_DATA",
        "805A1FFF": "SEC_ERROR_LIBRARY_FAILURE",
        "805A2000": "SEC_ERROR_IO",
        "805A2088": "SEC_ERROR_CERT_SIGNATURE_ALGORITHM_DISABLED",
        "805A2F8D": "SSL_ERROR_WEAK_SERVER_EPHEMERAL_DH_KEY",
        "805A2F8E": "SSL_ERROR_RX_UNEXPECTED_UNCOMPRESSED_RECORD",
        "805A2F8F": "SSL_ERROR_UNSAFE_NEGOTIATION",
        "805A2F90": "SSL_ERROR_RENEGOTIATION_NOT_ALLOWED",
        "805A2F91": "SSL_ERROR_DECOMPRESSION_FAILURE",
        "805A2F92": "SSL_ERROR_RX_MALFORMED_NEW_SESSION_TICKET",
        "805A2F93": "SSL_ERROR_RX_UNEXPECTED_NEW_SESSION_TICKET",
        "805A2F94": "SSL_ERROR_BAD_CERT_HASH_VALUE_ALERT",
        "805A2F95": "SSL_ERROR_BAD_CERT_STATUS_RESPONSE_ALERT",
        "805A2F96": "SSL_ERROR_UNRECOGNIZED_NAME_ALERT",
        "805A2F97": "SSL_ERROR_CERTIFICATE_UNOBTAINABLE_ALERT",
        "805A2F98": "SSL_ERROR_UNSUPPORTED_EXTENSION_ALERT",
        "805A2F99": "SSL_ERROR_SERVER_CACHE_NOT_CONFIGURED",
        "805A2F9A": "SSL_ERROR_NO_RENEGOTIATION_ALERT",
        "805A2F9B": "SSL_ERROR_USER_CANCELED_ALERT",
        "805A2F9C": "SSL_ERROR_INTERNAL_ERROR_ALERT",
        "805A2F9D": "SSL_ERROR_INSUFFICIENT_SECURITY_ALERT",
        "805A2F9E": "SSL_ERROR_PROTOCOL_VERSION_ALERT",
        "805A2F9F": "SSL_ERROR_EXPORT_RESTRICTION_ALERT",
        "805A2FA0": "SSL_ERROR_DECRYPT_ERROR_ALERT",
        "805A2FA1": "SSL_ERROR_DECODE_ERROR_ALERT",
        "805A2FA2": "SSL_ERROR_ACCESS_DENIED_ALERT",
        "805A2FA3": "SSL_ERROR_UNKNOWN_CA_ALERT",
        "805A2FA4": "SSL_ERROR_RECORD_OVERFLOW_ALERT",
        "805A2FA5": "SSL_ERROR_DECRYPTION_FAILED_ALERT",
        "805A2FA6": "SSL_ERROR_SESSION_NOT_FOUND",
        "805A2FA7": "SSL_ERROR_NO_TRUSTED_SSL_CLIENT_CA",
        "805A2FA8": "SSL_ERROR_CERT_KEA_MISMATCH",
        "805A2FA9": "SSL_ERROR_BAD_HANDSHAKE_HASH_VALUE",
        "805A2FAA": "SSL_ERROR_HANDSHAKE_NOT_COMPLETED",
        "805A2FAB": "SSL_ERROR_NO_COMPRESSION_OVERLAP",
        "805A2FAC": "SSL_ERROR_TOKEN_SLOT_NOT_FOUND",
        "805A2FAD": "SSL_ERROR_TOKEN_INSERTION_REMOVAL",
        "805A2FAE": "SSL_ERROR_NO_SERVER_KEY_FOR_ALG",
        "805A2FAF": "SSL_ERROR_SESSION_KEY_GEN_FAILURE",
        "805A2FB0": "SSL_ERROR_INIT_CIPHER_SUITE_FAILURE",
        "805A2FB1": "SSL_ERROR_IV_PARAM_FAILURE",
        "805A2FB2": "SSL_ERROR_PUB_KEY_SIZE_LIMIT_EXCEEDED",
        "805A2FB3": "SSL_ERROR_SYM_KEY_UNWRAP_FAILURE",
        "805A2FB4": "SSL_ERROR_SYM_KEY_CONTEXT_FAILURE",
        "805A2FB5": "SSL_ERROR_MAC_COMPUTATION_FAILURE",
        "805A2FB6": "SSL_ERROR_SHA_DIGEST_FAILURE",
        "805A2FB7": "SSL_ERROR_MD5_DIGEST_FAILURE",
        "805A2FB8": "SSL_ERROR_SOCKET_WRITE_FAILURE",
        "805A2FB9": "SSL_ERROR_DECRYPTION_FAILURE",
        "805A2FBA": "SSL_ERROR_ENCRYPTION_FAILURE",
        "805A2FBB": "SSL_ERROR_CLIENT_KEY_EXCHANGE_FAILURE",
        "805A2FBC": "SSL_ERROR_SERVER_KEY_EXCHANGE_FAILURE",
        "805A2FBD": "SSL_ERROR_EXTRACT_PUBLIC_KEY_FAILURE",
        "805A2FBE": "SSL_ERROR_SIGN_HASHES_FAILURE",
        "805A2FBF": "SSL_ERROR_GENERATE_RANDOM_FAILURE",
        "805A2FC0": "SSL_ERROR_CERTIFICATE_UNKNOWN_ALERT",
        "805A2FC1": "SSL_ERROR_UNSUPPORTED_CERT_ALERT",
        "805A2FC2": "SSL_ERROR_ILLEGAL_PARAMETER_ALERT",
        "805A2FC3": "SSL_ERROR_HANDSHAKE_FAILURE_ALERT",
        "805A2FC4": "SSL_ERROR_DECOMPRESSION_FAILURE_ALERT",
        "805A2FC5": "SSL_ERROR_HANDSHAKE_UNEXPECTED_ALERT",
        "805A2FC6": "SSL_ERROR_CLOSE_NOTIFY_ALERT",
        "805A2FC7": "SSL_ERROR_RX_UNKNOWN_ALERT",
        "805A2FC8": "SSL_ERROR_RX_UNKNOWN_HANDSHAKE",
        "805A2FC9": "SSL_ERROR_RX_UNKNOWN_RECORD_TYPE",
        "805A2FCA": "SSL_ERROR_RX_UNEXPECTED_APPLICATION_DATA",
        "805A2FCB": "SSL_ERROR_RX_UNEXPECTED_HANDSHAKE",
        "805A2FCC": "SSL_ERROR_RX_UNEXPECTED_ALERT",
        "805A2FCD": "SSL_ERROR_RX_UNEXPECTED_CHANGE_CIPHER",
        "805A2FCE": "SSL_ERROR_RX_UNEXPECTED_FINISHED",
        "805A2FCF": "SSL_ERROR_RX_UNEXPECTED_CLIENT_KEY_EXCH",
        "805A2FD0": "SSL_ERROR_RX_UNEXPECTED_CERT_VERIFY",
        "805A2FD1": "SSL_ERROR_RX_UNEXPECTED_HELLO_DONE",
        "805A2FD2": "SSL_ERROR_RX_UNEXPECTED_CERT_REQUEST",
        "805A2FD3": "SSL_ERROR_RX_UNEXPECTED_SERVER_KEY_EXCH",
        "805A2FD4": "SSL_ERROR_RX_UNEXPECTED_CERTIFICATE",
        "805A2FD5": "SSL_ERROR_RX_UNEXPECTED_SERVER_HELLO",
        "805A2FD6": "SSL_ERROR_RX_UNEXPECTED_CLIENT_HELLO",
        "805A2FD7": "SSL_ERROR_RX_UNEXPECTED_HELLO_REQUEST",
        "805A2FD8": "SSL_ERROR_RX_MALFORMED_APPLICATION_DATA",
        "805A2FD9": "SSL_ERROR_RX_MALFORMED_HANDSHAKE",
        "805A2FDA": "SSL_ERROR_RX_MALFORMED_ALERT",
        "805A2FDB": "SSL_ERROR_RX_MALFORMED_CHANGE_CIPHER",
        "805A2FDC": "SSL_ERROR_RX_MALFORMED_FINISHED",
        "805A2FDD": "SSL_ERROR_RX_MALFORMED_CLIENT_KEY_EXCH",
        "805A2FDE": "SSL_ERROR_RX_MALFORMED_CERT_VERIFY",
        "805A2FDF": "SSL_ERROR_RX_MALFORMED_HELLO_DONE",
        "805A2FE0": "SSL_ERROR_RX_MALFORMED_CERT_REQUEST",
        "805A2FE1": "SSL_ERROR_RX_MALFORMED_SERVER_KEY_EXCH",
        "805A2FE2": "SSL_ERROR_RX_MALFORMED_CERTIFICATE",
        "805A2FE3": "SSL_ERROR_RX_MALFORMED_SERVER_HELLO",
        "805A2FE4": "SSL_ERROR_RX_MALFORMED_CLIENT_HELLO",
        "805A2FE5": "SSL_ERROR_RX_MALFORMED_HELLO_REQUEST",
        "805A2FE6": "SSL_ERROR_TX_RECORD_TOO_LONG",
        "805A2FE7": "SSL_ERROR_RX_RECORD_TOO_LONG",
        "805A2FE8": "SSL_ERROR_BAD_BLOCK_PADDING",
        "805A2FE9": "SSL_ERROR_NO_CIPHERS_SUPPORTED",
        "805A2FEA": "SSL_ERROR_UNKNOWN_CIPHER_SUITE",
        "805A2FEB": "SSL_ERROR_FORTEZZA_PQG",
        "805A2FEC": "SSL_ERROR_SSL_DISABLED",
        "805A2FED": "SSL_ERROR_EXPIRED_CERT_ALERT",
        "805A2FEE": "SSL_ERROR_REVOKED_CERT_ALERT",
        "805A2FEF": "SSL_ERROR_BAD_CERT_ALERT",
        "805A2FF0": "SSL_ERROR_BAD_MAC_ALERT",
        "805A2FF1": "SSL_ERROR_BAD_MAC_READ",
        "805A2FF2": "SSL_ERROR_SSL2_DISABLED",
        "805A2FF3": "SSL_ERROR_POST_WARNING",
        "805A2FF4": "SSL_ERROR_BAD_CERT_DOMAIN",
        "805A2FF5": "SSL_ERROR_WRONG_CERTIFICATE",
        "805A2FF7": "SSL_ERROR_UNSUPPORTED_VERSION",
        "805A2FF8": "SSL_ERROR_UNSUPPORTED_CERTIFICATE_TYPE",
        "805A2FF9": "SSL_ERROR_BAD_SERVER",
        "805A2FFA": "SSL_ERROR_BAD_CLIENT",
        "805A2FFC": "SSL_ERROR_BAD_CERTIFICATE",
        "805A2FFD": "SSL_ERROR_NO_CERTIFICATE",
        "805A2FFE": "SSL_ERROR_NO_CYPHER_OVERLAP",
        "805A2FFF": "SSL_ERROR_US_ONLY_SERVER",
        "805A3000": "SSL_ERROR_EXPORT_ONLY_SERVER",
        "805A3FE7": "MOZILLA_PKIX_ERROR_CA_CERT_USED_AS_END_ENTITY",
        "805A3FE8": "MOZILLA_PKIX_ERROR_INADEQUATE_KEY_SIZE",
        "805A3FE9": "MOZILLA_PKIX_ERROR_V1_CERT_USED_AS_CA",
        "805A3FEB": "MOZILLA_PKIX_ERROR_NOT_YET_VALID_CERTIFICATE",
        "805A3FEC": "MOZILLA_PKIX_ERROR_NOT_YET_VALID_ISSUER_CERTIFICATE",
        "805A3FED": "MOZILLA_PKIX_ERROR_SIGNATURE_ALGORITHM_MISMATCH",
        "805A3FEE": "MOZILLA_PKIX_ERROR_OCSP_RESPONSE_FOR_CERT_MISSING",
        "805A3FEF": "MOZILLA_PKIX_ERROR_VALIDITY_TOO_LONG",
        "805A3FF0": "MOZILLA_PKIX_ERROR_REQUIRED_TLS_FEATURE_MISSING",
        "805A3FF1": "MOZILLA_PKIX_ERROR_INVALID_INTEGER_ENCODING",
        "805A3FF2": "MOZILLA_PKIX_ERROR_EMPTY_ISSUER_NAME",
        "805A3FF3": "MOZILLA_PKIX_ERROR_ADDITIONAL_POLICY_CONSTRAINT_FAILED",
        "805A3FFD": "MOZILLA_PKIX_ERROR_V1_CERT_USED_AS_CA"
    }

    var key = error_code.toUpperCase();
    var result = error_table[key];
    if (result == undefined) {
        result = "UNKNOWN_ERROR: " + key;
    }
    return result
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
