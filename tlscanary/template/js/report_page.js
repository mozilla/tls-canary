/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

"use strict";

function makeHeaderText(meta) {
  const desc = "Fx " + meta.test_metadata.app_version + " " + meta.test_metadata.branch 
          + " vs Fx " + meta.base_metadata.app_version + " " + meta.base_metadata.branch;
  const time = meta.run_start_time.split(".")[0].replace("T","-").replace(":","-").replace(":","-");
  window.document.getElementById("header").innerHTML = "<h3 class='header'>" + desc + "<br>" + time + "</h3>";
  window.document.title = "TLS Canary Report: " + desc;
}

function makeChartTab(uriList, fieldName) {
  makeFieldControl(fieldName);
  resizeChartCanvas();
  const data = getPieChartData(uriList, fieldName);
  drawChart(data, fieldName);
  updateChartCaption(data, fieldName);

  const div = window.document.getElementById("chart_text");
  div.style.position = "absolute";
  div.style.top = "0";
  div.style.left = $("#chart_canvas").width() * 1.2 + "px";
}

function makeFieldControl(fieldName) {
  var html = "";
  html += "<h3>Field:&nbsp;&nbsp;<select id='fieldNames' name='fieldNames' >";
  var columns = getVisibleColumns();
  for (var i = 0;i < columns.length;i++) {
    html += "<option value='" + columns[i] + "'";
    if (columns[i] === fieldName)
    {
      html += " selected"
    }
    html += ">" + columns[i] + "</option>";
  }
  html += "</select>";
  html += "<span id='chart_caption'></span>";
  const div = window.document.getElementById("chart_text");
  div.innerHTML = html;
  window.document.getElementById("fieldNames").onchange = onFieldChange;
}

function onFieldChange(e) {
  var fieldName = e.target.value;
  var uriList = getSortedRows();
  var data = getPieChartData(uriList, fieldName);
  updateChart(data, fieldName);
  updateChartCaption(data, fieldName);
}

function updateChart(uriList, fieldName) {
  window.document.myChart.destroy();
  drawChart(uriList, fieldName);
}

function updateChartCaption(uriList, fieldName) {
  const div = window.document.getElementById("chart_text");
  div.style.left = $("#chart_canvas").width() * 1.2 + "px";
  window.document.getElementById("chart_caption").innerHTML = "<h3>" + uriList.length + "&nbsp;unique&nbsp;value(s)</h3>";
}

function drawChart(data, fieldName) {
  const c = window.document.getElementById("chart_canvas");
  const ctx = c.getContext("2d");
  window.document.myChart = new Chart(ctx).Pie(data, {animation: false});
}

function resizeChartCanvas() {
  const canvas = $("#chart_canvas");
  const parent = $("#container");
  var w = parent.width();
  var h = parent.height();
  var d = w < h ? w * .4 : h * .4;
  canvas.width(d);
  canvas.height(canvas.width());
}

function getPieChartData(uriList, fieldName) {
  var chartFields = [];
  var strTable = "";
  for (var i = 0;i < uriList.length;i++) {
    var labelString = uriList[i][fieldName].toString();
    if (strTable.indexOf(labelString) == -1 )
    {
      strTable += labelString;
      chartFields.push (
        {
          label: labelString,
          value: 1
        }
      );
    } else {
      for (var j = 0;j < chartFields.length;j++) {
        if (chartFields[j].label === labelString)
        {
          chartFields[j].value++;
        }
      }
    }
  }
  var colorArray = returnColorArray(chartFields.length);
  for (var i = 0;i < chartFields.length; i++) {
    chartFields[i].color = colorArray[i];
  }
  return chartFields;
}

// Credit here goes to http://krazydad.com/tutorials/makecolors.php
function byte2Hex(n) {
  const nybHexString = "0123456789ABCDEF";
  return String(nybHexString.substr((n >> 4) & 0x0F,1)) + nybHexString.substr(n & 0x0F,1);
}

function RGB2Color(r,g,b) {
  return "#" + byte2Hex(r) + byte2Hex(g) + byte2Hex(b);
}

function returnColorArray(n) {
  const colorArray = [];
  const frequency = 0.3;
  for (var i = 0; i < n; ++i) {
    var freqIndex = frequency * i;
    var red = Math.sin(freqIndex + 0) * 127 + 128;
    var green = Math.sin(freqIndex + 2) * 127 + 128;
    var blue = Math.sin(freqIndex + 4) * 127 + 128;
    colorArray.push (RGB2Color(red,green,blue));
  }
  return colorArray;
}

function convertMilliseconds(n) {
  var hours = Math.floor(n / 3600000);
  var minutes = Math.floor(n / 60000) % hours;
  var seconds = ((n % 60000) / 1000).toFixed(0);
  return Math.floor(n / 60000) + " minutes";
}

function makeMetaTab(meta) {
  const metaArray = [
    ["<b>Source name, number of sites</b>", meta.args.source + ", " + meta.sources_size],
    ["<b>Total test time</b>", convertMilliseconds(new Date (meta.run_finish_time) - new Date (meta.run_start_time))],
    ["<b>Platform</b>", meta.test_metadata.appConstants.platform],
    ["<b>TLS Canary version</b>", meta.tlscanary_version],
    ["<b>argv parameters</b>", meta.argv.toString()],
    ["<b>Run log</b>", "<a href='log.json'>&#128279; link</a>"],
    ["<b>OneCRL environment</b>", meta.args.onecrl],
    ["<b>Test build</b>", meta.test_metadata.app_version + " " + meta.test_metadata.branch],
    ["<b>Test build origin</b>", meta.test_metadata.package_origin],
    ["<b>Test build ID</b>", meta.test_metadata.application_ini.buildid],
    ["<b>Test build NSS</b>", meta.test_metadata.nss_version],
    ["<b>Test build NSPR</b>", meta.test_metadata.nspr_version],
    ["<b>Test profile</b>", "<a href='test_profile.zip'>&#128193; link</a>"],
    ["<b>Base build</b>", meta.base_metadata.app_version + " " + meta.base_metadata.branch],
    ["<b>Base build origin</b>", meta.base_metadata.package_origin],
    ["<b>Base build ID</b>", meta.base_metadata.application_ini.buildid],
    ["<b>Base build NSS</b>", meta.base_metadata.nss_version],
    ["<b>Base build NSPR</b>", meta.base_metadata.nspr_version],
    ["<b>Base profile</b>", "<a href='base_profile.zip'>&#128193; link</a>"]
  ];

  var html = "";
  html += "<table id='grid-metadata' width='100%' class='table table-condensed table-hover table-striped'>";
  html += "<thead>";
  html += "<tr>";
  html += "<th data-column-id='t0' width='30%'></th>";
  html += "<th data-column-id='t1' width='70%'></th>";
  html += "</tr>";
  html += "</thead>";
  html += "<tbody>";

  for (var i = 0;i < metaArray.length;i++) {
    html += "<tr>";
    html += "<td>" + metaArray[i][0] + "</td>";
    html += "<td>" + metaArray[i][1] + "</td>";
    html += "</tr>";
  }

  html += "</tbody>";
  html += "</table>";

  const element = window.document.getElementById("metadata");
  element.innerHTML = html;
}

function navigate(tab) {
  const $nav = $("#nav");
  const listItems = $nav.children();
  const tabs = ["results", "chart", "metadata"];
  for (var i = 0;i < tabs.length;i++) {
      window.document.getElementById(tabs[i]).style.visibility = "hidden";
      listItems[i].id = tabs[i] + "_tab";
  }
  window.document.getElementById(tab).style.visibility = "visible";
  window.document.getElementById(tab + "_tab").id = "selected";
  if (tab === "chart")
  {
    refreshChartTab();
  }
}

function refreshChartTab() {
  var selectedItem = window.document.getElementById("fieldNames").value;
  makeFieldControl(selectedItem);
  updateChartCaption (window.document.myChart.segments, selectedItem) 
}

function getVisibleColumns() {
  var gridData = $("#grid").bootgrid("getCurrentRows");
  var columnData = $("#grid").bootgrid("getColumnSettings");
  var columns = [];
  for (var i = 0;i < columnData.length;i++) {
      if (columnData[i].visible)
      {
        if (columnData[i].id !== "Actions")
        {
          columns.push (columnData[i].id);
        }
      }
  }
  return columns;
}

function getSortedRows() {
  var gridData = $("#grid").bootgrid().data(".rs.jquery.bootgrid").rows;
  var currentRows = [];
  var searchStr = $("#grid").bootgrid("getSearchPhrase");
  var currentColumns = getVisibleColumns();
  for (var i = 0;i < gridData.length;i++) {
    var row = gridData[i];
    for (var j = 0;j < currentColumns.length;j++)
    {
      var field = row[currentColumns[j]].toString();
      if (field.search(searchStr) != -1)
      {
        currentRows.push(row);
        break;
      }
    }
  }
  return currentRows;
}

function makeTable(hosts, columns) {
  // First, add new column for our grid actions
  columns.push(
    {
      name: "Actions",
      default: true,
      type: null,
      width: "20%"
    }
  );
  var html = "<table id='grid' class='table table-condensed table-hover table-striped'><thead><tr>";
  for (var i = 0;i < columns.length;i++) {
    html += "<th data-column-id='" + columns[i].name + "' ";
    if (columns[i].name === "rank")
    {
      html += "data-order='asc' ";
      html += "data-identifier='true' ";
    }
    if (columns[i].name === "Actions")
    {
      html += "data-visible-in-selection='false' data-formatter='commands' data-searchable='false' ";
    }
    if (!columns[i].default)
    {
      html += "data-visible='false' ";
    }
    if (columns[i].type === "int")
    {
      html += "data-type='numeric' ";
    }
    if (typeof(columns[i].width) !== "undefined")
    {
      html += "data-width='" + columns[i].width + "' ";
    } else {
      html += "data-width='20%' ";
    }
    html += ">" + columns[i].name + "</th>"
  }
  html += "</tr></thead><tbody>";
  for (var i = 0;i < hosts.length;i++) {
    html += "<tr id=\'" + hosts[i]["rank"] + "\'>";
    for (var j = 0;j < columns.length;j++)
    {
      html += "<td>" + hosts[i][columns[j].name] + "</td>"
    }
    html += "</tr>";
  }
  html += "</tbody></table>";
  const contentDiv = document.getElementById("results");
  contentDiv.style.visibility = "hidden";
  contentDiv.innerHTML = html;
}

function applyBootgrid() {
  const grid = $("#grid").bootgrid(
  {
    css:
    {
      paginationButton: "labels_small"
    },
    rowCount: [15,10,5,-1],
    selection: false,
    multiSelect: true,
    rowSelect: true,
    keepSelection: true,
    formatters: 
    {
      "commands": function(column, row) {
        var html = "";
        if (typeof(row.not_before) !== "undefined" && row.not_before != "")
        {
          html += "<a href='./certs/" + row.host
               + ".der'><button type='button' class='btn btn-xs btn-default'>&#128274;</button></a> ";
        }                    
        html += "<button type='button' class='btn btn-xs btn-default command-link' data-row-id='"
             + row.host + "'><span>&#128279; </span></button> " +
              "<button type='button' class='btn btn-xs btn-default command-tls_obs' data-row-id='"
             + row.host + "'><span class='fa fa-trash-o'> &#128270; </span></button> " +
              "<button type='button' class='btn btn-xs btn-default command-delete' data-row-id='"
             + row.rank + "'><span class='fa fa-trash-o'> &times; </span></button>";
        return html;
      },
      "date": function(column, row) {
        var temp = String(row[column.id]).substr(0,13);
        var d = new Date(Number(temp));
        return d.toString();
      }
    }
  }).on("loaded.rs.jquery.bootgrid", function ()
  {
    grid.find(".command-link").on("click", function(e)
    {
        window.open("https://" + $(this).data("row-id"), "_blank");
    }).end().find(".command-tls_obs").on("click", function(e)
    {
        window.open("https://observatory.mozilla.org/analyze.html?host=" + $(this).data("row-id") + "#tls", "_blank")
    }).end().find(".command-delete").on("click", function(e)
    {
      var items = [];
      items.push ($(this).data("row-id"));
      $("#grid").bootgrid("remove", items);
    });
    const contentDiv = document.getElementById("results");
    contentDiv.style.visibility = "visible";
  });
}

function findProp(obj, prop, defVal) {
  if (typeof(defVal) === "undefined") defVal = null;
  prop = prop.split(".");
  for (var i = 0; i < prop.length; i++) {
      if(typeof obj[prop[i]] === "undefined")
          return defVal;
      obj = obj[prop[i]];
  }
  return obj;
}

function transformLog(transformData, jsonData) {
  const hosts = [];
  for (var i = 0;i < jsonData.data.length;i++) {
    var host = {};
    for (var j = 0;j < transformData.length;j++)
    {
      var prop = findProp(jsonData.data[i], transformData[j].prop, "");
      host[transformData[j].name] = prop;
    }
    hosts.push(host);
  }
  return hosts;
}

function loadLog(transformData) {
  const logXHR = new XMLHttpRequest();
  logXHR.onload = function(arg) {
    const jsonData = JSON.parse(this.responseText)[0];
    const hosts = transformLog(transformData,jsonData);
    buildUI(jsonData, hosts, transformData);
  }       
  logXHR.onerror = function(arg) {
    alert("Failed to load log file.")
  }  
  logXHR.open("GET", "log.json", true);
  logXHR.send();
}

function buildUI(jsonData, hosts, transformData) {
  makeHeaderText(jsonData.meta);
  makeMetaTab(jsonData.meta);
  makeTable(hosts, transformData);
  applyBootgrid();
  makeChartTab(hosts, "error");
  navigate("results");
}

function loadTransform() {
  const transformXHR = new XMLHttpRequest();
  transformXHR.onload = function(arg) {
    const transformData = JSON.parse(this.responseText);
    loadLog(transformData);
  }
  transformXHR.onerror = function(arg) {
    alert("Failed to load transform.json file.")
  }       
  transformXHR.open("GET", "../../js/transform.json", true);
  transformXHR.send(); 
}

function init() {
  loadTransform();
}

init();
