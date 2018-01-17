/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

"use strict";

function makeHeaderText() {
  const desc = "<br>A site compatibility tool<br>for Firefox.";
  window.document.getElementById("header").innerHTML = "<h3 class='header'>" + desc + "</h3>";
}

function makeChartTab(fieldName) {
  var uriList = getSortedRows(fieldName);
  makeFieldControl(fieldName);
  resizeChartCanvas();
  const data = getChartData(uriList, fieldName);
  drawChart(data, fieldName);
}

function makeFieldControl(fieldName) {
  var branches = findBranches();
  var html = "";
  html += "<h3>Branch:&nbsp;&nbsp;<select id='fieldNames' name='fieldNames' >";
  for (var i = 0;i < branches.length;i++) {
    html += "<option value='" + branches[i] + "'";
    if (branches[i] === fieldName)
    {
      html += " selected"
    }
    html += ">" + branches[i] + "</option>";
  }
  html += "</select><br>";
  const div = window.document.getElementById("chart_text");
  div.innerHTML = html;
  window.document.getElementById("fieldNames").onchange = onFieldChange;
}

function onFieldChange(e) {
  var fieldName = e.target.value;
  var uriList = getSortedRows(fieldName);
  var data = getChartData(uriList, fieldName);
  updateChart(data, fieldName);
}

function findBranches() {
  var uriList = getSortedRows("All");
  var branches = [];
  var strTable = "";
  for (var i = 0;i < uriList.length;i++) {
    var labelString = uriList[i]["branch"].toString();
    if (strTable.indexOf(labelString) == -1 )
    {
      strTable += labelString;
      branches.push (labelString);
    }
  }
  branches.push ("All");
  return branches;
}

function updateChart(uriList, fieldName) {
  window.document.myChart.destroy();
  drawChart(uriList, fieldName);
}

function drawChart(data, fieldName) {
  const c = window.document.getElementById("chart_canvas");
  const ctx = c.getContext("2d");
  window.document.myChart = new Chart(ctx).Bar(data, {animation: true});
}

function resizeChartCanvas() {
  const canvas = $("#chart_canvas");
  const parent = $("#results");
  canvas.width(parent.width());
  canvas.height(350);
}

function getChartData(uriList, fieldName) {
  var labels = [];
  var data = [];
  for (var i=0; i<uriList.length; i++) {
    labels.push(uriList[i].run);
    data.push(Number(uriList[i].errors));
  }
  var dataset = {};
  dataset.label = "Number of errors";
  dataset.fillColor = "rgba(151,187,205,0.2)";
  dataset.strokeColor = "rgba(151,187,205,1)";
  dataset.pointColor = "rgba(151,187,205,1)";
  dataset.pointStrokeColor = "#fff";
  dataset.pointHighlightFill = "#fff";
  dataset.pointHighlightStroke = "rgba(151,187,205,1)";
  dataset.data = data;

  var o = {};
  o.labels = labels;
  o.datasets = [dataset];
  return o;
}

function navigate(tab) {
  const $nav = $("#nav");
  const listItems = $nav.children();
  const tabs = ["results", "chart"];
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
  var uriList = getSortedRows(selectedItem);
  var data = getChartData(uriList, selectedItem);
  updateChart(data, selectedItem);
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

function getSortedRows(fieldName) {
  var gridData = $("#grid").bootgrid().data(".rs.jquery.bootgrid").rows;
  var currentRows = [];
  var searchStr = $("#grid").bootgrid("getSearchPhrase");
  var currentColumns = getVisibleColumns();
  if (fieldName == "All")
  {
    fieldName = "";
  }
  for (var i = 0;i < gridData.length;i++) {
    var row = gridData[i];
    for (var j = 0;j < currentColumns.length;j++)
    {
      var field = row[currentColumns[j]].toString();
      if (field.search(searchStr) != -1 && field.search(fieldName) != -1)
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
  // Add an invisible column which allows one field to become the identifier
  columns.unshift(
    {
      name: "id",
      default: false,
      type: "str",
      width: "0%"
    }
  );

  var html = "<table id='grid' class='table table-condensed table-hover table-striped'><thead><tr>";
  for (var i = 0;i < columns.length;i++) {
    html += "<th data-column-id='" + columns[i].name + "' ";
    if (columns[i].name === "id")
    {
      html += "data-visible-in-selection='false'  data-searchable='false' ";
      html += "data-identifier='true' ";
    } 
    if (columns[i].name === "Actions")
    {
      html += "data-visible-in-selection='false' data-formatter='commands' data-searchable='false' ";
    }
    if (columns[i].name === "run")
    {
      html += "data-order='desc' data-formatter='link' "; 
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
    html += "<tr id=\'" + hosts[i]["run"] + "\'>";
    html += "<td>" + hosts[i]["run"] + "</td>"
    for (var j = 1;j < columns.length;j++)
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
    rowCount: [10,5,-1],
    selection: false,
    multiSelect: true,
    rowSelect: true,
    keepSelection: true,
    formatters: 
    {
      "commands": function(column, row) {
        var html = "";                  
        html += "<button type='button' title='Link' class='btn btn-xs btn-default command-link' data-row-id='runs/"
             + row.id + "/index.htm'><span>&#128279; </span></button> " +
              "<button type='button' title='Remove from list' class='btn btn-xs btn-default command-delete' data-row-id='"
             + row.id + "'><span class='fa fa-trash-o'> &times; </span></button>";
        return html;
      },
      "date": function(column, row) {
        var temp = String(row[column.id]).substr(0,13);
        var d = new Date(Number(temp));
        return d.toString();
      },
      "link": function(column, row) {
        var html = "<a href='runs/" + row.id + "/index.htm' target='_blank'>" + row.id + "</a>";
        return html;
      }
    }
  }).on("loaded.rs.jquery.bootgrid", function ()
  {
    grid.find(".command-link").on("click", function(e)
    {
        window.open("" + $(this).data("row-id"), "_blank");
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
    alert("Failed to load runs file.")
  }  
  logXHR.open("GET", "./runs/runs.json", true);
  logXHR.send();
}

function buildUI(jsonData, hosts, transformData) {
  makeHeaderText();
  makeTable(hosts, transformData);
  applyBootgrid();
  navigate("results");
  makeChartTab("All");
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
  transformXHR.open("GET", "./js/index_transform.json", true);
  transformXHR.send(); 
}

function init() {
  loadTransform();
}

init();
