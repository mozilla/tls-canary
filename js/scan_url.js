/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

"use strict";

const Cc = Components.classes;
const Ci = Components.interfaces;
const Cu = Components.utils;
const Cr = Components.results;

// Register resource://app/ URI
let ios = Cc["@mozilla.org/network/io-service;1"].getService(Ci.nsIIOService);
let resHandler = ios.getProtocolHandler("resource").QueryInterface(Ci.nsIResProtocolHandler);
let mozDir = Cc["@mozilla.org/file/directory_service;1"].getService(Ci.nsIProperties).get("CurProcD", Ci.nsILocalFile);
let mozDirURI = ios.newFileURI(mozDir);
resHandler.setSubstitution("app", mozDirURI);


Cu.import("resource://gre/modules/Services.jsm");
Cu.import("resource://gre/modules/FileUtils.jsm");
Cu.import("resource://gre/modules/XPCOMUtils.jsm");
Cu.import("resource://gre/modules/NetUtil.jsm");
XPCOMUtils.defineLazyGetter(this, "Timer", function() {
  let timer = {};
  Cu.import("resource://gre/modules/Timer.jsm", timer);
  return timer;
});


if (!arguments || arguments.length < 1) {

  throw "Usage: xpcshell sslScan.js <-u=uri>\n";
}

/*

-u :  uri to scan (without scheme)

-d : local directory path

-p :  preferences to apply (multiple flags supported)
      NOTE: Boolean pref values must be passed in as false/true and not 0/1

-profile : path to profile

-r : (site) rank (integer)

-j : print JSON on error

-c : write certificate to disk with this path

-id : optional run ID

*/
  
const DEFAULT_TIMEOUT = 10000;
var completed = false;
var debug = false; 
var current_directory = "";
var certPath = false;
var host;
var prefs = [];
var rank = 0;
var run_id;
var print_json = false;
var profile_path;

for (var i=0;i<arguments.length;i++)
{
  if (arguments[i].indexOf("-d=") != -1)
  {
    current_directory = arguments[i].split("-d=")[1];
  }
  if (arguments[i].indexOf("-u=") != -1)
  {
    host = arguments[i].split("-u=")[1].toLowerCase();
    var temp = host.split(",");
    if (temp.length > 1)
    {
      rank = parseInt(temp[0]);
      host = temp[1];
    }
  }
  if (arguments[i].indexOf("-r=") != -1)
  {
    rank = parseInt(arguments[i].split("-r=")[1]);
  }
  if (arguments[i].indexOf("-profile=") != -1)
  {
    profile_path = arguments[i].split("-profile=")[1];
  } 
  if (arguments[i].indexOf("-p=") != -1)
  {
    var temp1 = arguments[i].split("-p=")[1];
    var temp2 = temp1.split("=");
    var o = {};
    o.name = temp2[0];
    o.value = temp2[1];
    prefs.push (o);
  }
  if (arguments[i].indexOf("-c=") != -1)
  {
    certPath = arguments[i].split("-c=")[1] + "/";
  }
  if (arguments[i].indexOf("-j=") != -1)
  {
    print_json = arguments[i].split("-j=")[1];
  }
  if (arguments[i].indexOf("-id=") != -1)
  {
    run_id = arguments[i].split("-id=")[1];
  }
}

try
{
  Cu.import("file:///" + current_directory + "/js/forge.min.js");
} catch (e)
{
  failRun (e.message + "\n\n")
}

try
{
  for (var i=0;i<prefs.length;i++)
  {
    var value = prefs[i].value;
    if ( value == "true" || value == "false" )
    {
      var n = (value == "false" ? 0 : 1);
      Services.prefs.setBoolPref(prefs[i].name, n);
    } else if (!isNaN(value))
    {
      Services.prefs.setIntPref(prefs[i].name,value);
    } else {
      Services.prefs.setPref(prefs[i].name,value);
    }
  }
} catch (e)
{
  infoMessage (e.message + "\n\n")
}

// custom prefs can go here
// Services.prefs.setIntPref("security.pki.netscape_step_up_policy", 3)

const nsINSSErrorsService = Ci.nsINSSErrorsService;
let nssErrorsService = Cc['@mozilla.org/nss_errors_service;1'].getService(nsINSSErrorsService);
const UNKNOWN_ERROR = 0;

function set_profile() {
  if (profile_path == undefined) 
  {
    failRun("profile path not defined");
    return;
  }
  
  let profd = profile_path;
  let file = Components.classes["@mozilla.org/file/local;1"]
                       .createInstance(Components.interfaces.nsILocalFile);
  file.initWithPath(profd);
  let dirSvc = Components.classes["@mozilla.org/file/directory_service;1"]
                         .getService(Components.interfaces.nsIProperties);
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
      if (iid.equals(Components.interfaces.nsIDirectoryServiceProvider) ||
          iid.equals(Components.interfaces.nsISupports)) {
        return this;
      }
      throw Components.results.NS_ERROR_NO_INTERFACE;
    }
  };
  dirSvc.QueryInterface(Components.interfaces.nsIDirectoryService)
        .registerProvider(provider);
  let obsSvc = Components.classes["@mozilla.org/observer-service;1"].
        getService(Components.interfaces.nsIObserverService);

  // The methods of 'provider' will retain this scope so null out everything
  // to avoid spurious leak reports.
  profd = null;
  dirSvc = null;
  provider = null;
  obsSvc = null;
  return file.clone();
}

function getErrorType(status) {
  let errType = "unknown";
  if ((status & 0xff0000) === 0x5a0000) { // Security module
    let errorClass;
    // getErrorClass will throw a generic 
    // NS_ERROR_FAILURE if the error code is
    // somehow not in the set of covered errors.
    try {
      errorClass = nssErrorsService.getErrorClass(status);
      if (errorClass == nsINSSErrorsService.ERROR_CLASS_BAD_CERT) {
        errType = "certificate";
      } else {
        errType = "protocol";
      }
    } catch (e) {
      infoMessage ("Can't retrieve error type");
    }
  } else {
    errType = "network";
  }
  return errType;
}

function analyzeSecurityInfo(xhr, error, hostname, errorCode) {
  if (error) {
    // try for an error string here first, 
    // in case we won't be able to get an error string later
    test_obj.error.type = error;
    test_obj.error.code = "0x" + errorCode.toString(16);
    test_obj.error.message = errorCodeLookup (errorCode);
  } 
  if (!xhr) {
    infoMessage("Request failed: no information available");
    return false;
  }
  try {
    let channel = xhr.channel;
    let secInfo = channel.securityInfo;

    if (secInfo instanceof Ci.nsITransportSecurityInfo) 
      secInfo.QueryInterface(Ci.nsITransportSecurityInfo);
    if (secInfo instanceof Ci.nsISSLStatusProvider) {
      if (secInfo.QueryInterface(Ci.nsISSLStatusProvider).SSLStatus != null)
      {
        try
        {
          var status = secInfo.QueryInterface(Ci.nsISSLStatusProvider).SSLStatus.QueryInterface(Ci.nsISSLStatus);
          /*
          let versions = ["SSL3", "1.0", "1.1", "1.2"];
          test_obj.tls_info.version = versions[status.protocolVersion];
          test_obj.tls_info.cipherName = status.cipherName;
          test_obj.tls_info.keyLength = status.keyLength.toString();
          test_obj.tls_info.secretKeyLength = status.secretKeyLength.toString();
          */
        } catch (e)
        {
          infoMessage ("Can't get TLS status: " + e.message)
        }
        try{
          var cert = status.serverCert;
          if (cert.sha1Fingerprint) 
          {
            try{
              if (certPath)
              {
                var certFile = openFile(certPath + host + ".der");
                var l={};
                var raw = cert.getRawDER (l);
                writeCertToDisk(certFile,buildDER(raw));
                FileUtils.closeSafeFileOutputStream(certFile);
              }
            } catch (e)
            {
              failRun (e.message);
            }
          }
          
          test_obj.cert_info.nickname = cert.nickname;
          test_obj.cert_info.emailAddress = cert.emailAddress;
          test_obj.cert_info.subjectName = cert.subjectName;
          test_obj.cert_info.commonName = cert.commonName;
          test_obj.cert_info.organization = cert.organization;
          test_obj.cert_info.organizationalUnit = cert.organizationalUnit;
          test_obj.cert_info.issuerCommonName = cert.issuerCommonName;
          test_obj.cert_info.issuerOrganization = cert.issuerOrganization;
          test_obj.cert_info.sha1Fingerprint = cert.sha1Fingerprint;
          test_obj.cert_info.sha256Fingerprint = cert.sha256Fingerprint;
          test_obj.cert_info.chainLength = cert.getChain().length.toString();

          try
          {
            var usages = {};
            var usagesString = {};
            cert.getUsagesString(true, usages, usagesString);
            test_obj.cert_info.certifiedUsages = usagesString.value;
          } catch (e)
          {
            infoMessage (e.message)
          }

          let validity = cert.validity.QueryInterface(Ci.nsIX509CertValidity);
          test_obj.cert_info.validityNotBefore = validity.notBeforeGMT;
          test_obj.cert_info.validityNotAfter = validity.notAfterGMT;
          test_obj.cert_info.isEV = status.isExtendedValidation.toString();
          
          var forgeCert = forge.pki.certificateFromPem(certToPEM(cert));
          var subjectAltName = forgeCert.getExtension({name: "subjectAltName"});
          var subjectAltNameStr = formatSubjectAltNames(subjectAltName);
          var tempStr = subjectAltNameStr;
          if (subjectAltNameStr.length > 24)
          {
              tempStr = subjectAltNameStr.substr(0,21) + "...";
          }
          test_obj.cert_info.subjectAltName = tempStr;
          test_obj.cert_info.signatureAlgorithm = forge.pki.oids[forgeCert.signatureOid];

          for (var e in forgeCert.extensions)
          {
            if (forgeCert.extensions[e].name == "keyUsage")
            {
                test_obj.cert_info.keyUsage = formatKeyUsage(forgeCert.extensions[e]);
            }
            if (forgeCert.extensions[e].name == "extKeyUsage")
            {
                test_obj.cert_info.extKeyUsage = formatExtKeyUsage(forgeCert.extensions[e]);
            }
          }

          var rootCert = getRootCert(cert); 
          test_obj.cert_info.rootCertificateSubjectName=rootCert.subjectName;
          test_obj.cert_info.rootCertificateOrganization=rootCert.organization;
          test_obj.cert_info.rootCertificateOrganizationalUnit=rootCert.organizationalUnit;
          test_obj.cert_info.rootCertificateSHA1Fingerprint=rootCert.sha1Fingerprint;
        } 
        catch (e)
        {
          infoMessage ("Can't get certificate: " + e.message)
        }
      }
      
      if (error)
      {
        var rawError = secInfo.errorMessage;
        try{
          if (rawError.split("(Error code: ").length > 1 )
          {
            test_obj.error.message = rawError.split("(Error code: ")[1].split(")")[0];
          } else {
            // new error string format in Fx46/Nightly?
            test_obj.error.message = rawError.split("Error code: ")[1].split("title=\"")[1].split("\">")[0].toLowerCase();
          }
        } catch (e) {
          infoMessage ("Can't get error message: " + e.message)
        }
      }
    }
  } catch(e) {
    failRun (e.message);
  }
}

function errorCodeLookup(error)
{
  // For network error messages that are not obtainable otherwise 
  // https://developer.mozilla.org/en-US/docs/Mozilla/Errors
  var msg;
  switch(error)
  {
    case 0x804b001e: 
      msg = "domain_not_found_error";
      break;
    case 0x804b000d: 
      msg = "connection_refused_error";
      break;
    case 0x804b0014: 
      msg = "net_reset_error";
      break;
    case 0x8000ffff: 
      msg = "unexpected_error";
      break;
    case 0x804b000a:
      msg = "error_malformed_uri";
      break;
    default:
      msg = "unknown_error";
      break;
  }
  return msg;
}

function buildDER(chars){
    var result = "";
    for (var i=0; i < chars.length; i++)
        result += String.fromCharCode(chars[i]);
    return result;
}

function certToPEM(cert) {
  let der = cert.getRawDER({});
  let derString = buildDER(der);
  let base64Lines = btoa(derString).replace(/(.{64})/g, "$1\n");
  let output = "-----BEGIN CERTIFICATE-----\n";
  for (let line of base64Lines.split("\n")) {
    if (line.length > 0) {
      output += line + "\n";
    }
  }
  output += "-----END CERTIFICATE-----";
  return output;
}

// Thanks Keeler!
function formatAltName(altName) {
  switch (altName.type) {
    case 2: return "DNS name:" + altName.value;
    case 7: return "IP address:" + altName.ip;
    default: return "(unsupported)";
  }
}

function formatSubjectAltNames(altNames) {
  if (!altNames) {
    return "(no subject alternative names extension)";
  }
  if (!altNames.altNames || altNames.altNames.length < 1) {
    return "(empty subject alternative names extension)";
  }
  var result = "";
  altNames.altNames.forEach(function(altName) {
    var spacer = result.length ? ", " : "";
    result += spacer + formatAltName(altName);
  });
  return result;
}
function formatKeyUsage(extension) {
  var result = "";
  for (var usage of ["digitalSignature", "nonRepudiation", "keyEncipherment",
                     "dataEncipherment", "keyAgreement", "keyCertSign"]) {
    if (extension[usage]) {
      result += (result.length > 0 ? ", " : "") + usage;
    }
  }
  return result;
}

function formatExtKeyUsage(extension) {
  var result = "";
  for (var usage of ["serverAuth", "clientAuth", "codeSigning",
                     "emailProtection", "timeStamping", "OCSPSigning"]) {
    if (extension[usage]) {
      result += (result.length > 0 ? ", " : "") + usage;
    }
  }
  return result;
}

function getRootCert(cert)
{
  var chain = cert.getChain().enumerate();
  var childCert;
  while ( chain.hasMoreElements() )
  {
    childCert = chain.getNext().QueryInterface(Ci.nsISupports).QueryInterface(Ci.nsIX509Cert);
  }
  return childCert;
}

function RedirectStopper() {}
RedirectStopper.prototype = {
  // nsIChannelEventSink
  asyncOnChannelRedirect: function(oldChannel, newChannel, flags, callback) {
    throw Cr.NS_ERROR_ENTITY_CHANGED;
  },
  getInterface: function(iid) {
    return this.QueryInterface(iid);
  },
  QueryInterface: XPCOMUtils.generateQI([Ci.nsIChannelEventSink])
};


function queryHost(hostname, callback) {
  let timeout;
  function completed(error, xhr) {
    clearTimeout();
    callback(error, xhr);
  }
  function errorHandler(e) {
    clearTimeout();
    completed(e.target.channel.QueryInterface(Ci.nsIRequest).status, e.target);
  }
  function readyHandler(e) {
    if (e.target.readyState === 4) {
      clearTimeout();
      completed(null, e.target); // no error
    }
  }
  function clearTimeout()
  {
    if (timeout) {
      Timer.clearTimeout(timeout);
      timeout = null;
    }  
  }
  try {
    let req = Cc["@mozilla.org/xmlextras/xmlhttprequest;1"].createInstance(Ci.nsIXMLHttpRequest);
    timeout = Timer.setTimeout(() => completed(UNKNOWN_ERROR, req), DEFAULT_TIMEOUT+2000);
    req.open("HEAD", "https://" + hostname, true);
    req.timeout = DEFAULT_TIMEOUT;
    req.channel.notificationCallbacks = new RedirectStopper();
    req.addEventListener("error", errorHandler, false);
    req.addEventListener("load", readyHandler, false);
    req.send();
  } catch (e) {
    infoMessage("Runtime error for XHR: " + e.message)
    completed(-1, req);
  }
}

function writeCertToDisk(outputStream, data) {
  outputStream.write(data, data.length);
}

function loadURI(uri) {
  function recordResult(hostname, error, xhr) {
    let speed = new Date().getTime() - test_obj.site_info.connectionSpeed;
    test_obj.site_info.connectionSpeed = speed.toString();

    let currentError = error ? getErrorType(error) : null;
    analyzeSecurityInfo(xhr, currentError, hostname, error);
    if (error) {
      if (print_json) {
        dump(JSON.stringify({
          error: true,
          rank: test_obj.site_info.rank,
          url: test_obj.site_info.uri,
          test_obj: test_obj
        }) + "\n");
      } else {
        dump(JSON.stringify({
          error: true,
          rank: test_obj.site_info.rank,
          url: test_obj.site_info.uri
        }) + "\n");
      }
    } else {
      dump(JSON.stringify({
        error: false,
        rank: test_obj.site_info.rank,
        url: test_obj.site_info.uri
      }) + "\n");
    }
  }
  function handleResult(err, xhr) {
    recordResult(uri, err, xhr);
    completed = true;
  }
  queryHost(uri, handleResult);
  waitForAResponse(() => completed != true);
}

function waitForAResponse(condition) {
  try {
    let threadManager = Cc["@mozilla.org/thread-manager;1"].getService(Ci.nsIThreadManager);
    let mainThread = threadManager.currentThread;
    while (condition()) {
      mainThread.processNextEvent(true);
    }
  } catch(e) {
    failRun (e.message);
  }
}
 
function openFile(path, mode) {
  let file = Cc["@mozilla.org/file/local;1"].createInstance(Components.interfaces.nsILocalFile);
  file.initWithPath(path);
  try
  {
    var fos = FileUtils.openFileOutputStream(file, mode);
    return fos;
  } catch (e)
  {
    failRun (e.message)
  }
}

function createTestObject()
{
  var o = {};
  o.site_info = {};
  o.site_info.uri= host;
  o.site_info.rank=rank;
  o.site_info.connectionSpeed = new Date().getTime();
  o.site_info.timestamp= new Date().getTime().toString();
  
  o.error = {};
  o.error.code="";
  o.error.type="";
  o.error.message="";

  // This part temporarily disabled, because our script only reports
  // on errors, and in error situations, we don't have a valid TLS
  // connection to obtain these values.

  /*
  o.tls_info = {};
  o.tls_info.version="";
  o.tls_info.cipherName="";
  o.tls_info.keyLength="";
  o.tls_info.secretKeyLength="";
  */

  o.cert_info = {};
  o.cert_info.isEV="";
  o.cert_info.certifiedUsages="";
  o.cert_info.chainLength="";
  o.cert_info.nickname="";
  o.cert_info.emailAddress="";
  o.cert_info.subjectName="";
  o.cert_info.commonName="";
  o.cert_info.subjectAltName="";
  o.cert_info.keyUsage="";
  o.cert_info.extKeyUsage="";
  o.cert_info.organization="";
  o.cert_info.organizationalUnit="";
  o.cert_info.validityNotBefore="";
  o.cert_info.validityNotAfter="";
  o.cert_info.signatureAlgorithm = "";
  o.cert_info.sha1Fingerprint="";
  o.cert_info.sha256Fingerprint="";
  o.cert_info.issuerName="";
  o.cert_info.issuerOrganization="";
  o.cert_info.rootCertificateSubjectName="";
  o.cert_info.rootCertificateOrganization="";
  o.cert_info.rootCertificateOrganizationalUnit="";
  o.cert_info.rootCertificateSHA1Fingerprint="";
  
  return o;
}

function infoMessage(arg)
{
  if (debug)
  {
    dump ("ERROR: " + arg + "\n");
  }
}
function failRun(arg)
{
  dump ("FAIL: fatal error: " + arg + "\n");
  completed = true;
}

try {
  set_profile();
  var test_obj = createTestObject();
  loadURI(host);
} catch (e) {
  failRun(e.message);
}
