

function makeHeaderText(meta)
{
  var desc = "Fx " + meta.test_metadata.app_version + " " + meta.test_metadata.branch 
          + " vs Fx " + meta.base_metadata.app_version + " " + meta.base_metadata.branch;
  var time = meta.run_start_time.split(".")[0].replace("T","-").replace(":","-").replace(":","-");
  window.document.getElementById("header").innerHTML = "<h3>" + desc + "<br>" + time + "</h3>";
  window.document.title = "TLS Canary Report: " + desc;
}

function makeGraphTab(uriList, fieldName)
{
  var fieldNum = drawGraph(uriList, fieldName);
  var html = "";

  /*
  html += "<select>";

  var columns = getVisibleColumns();
  
  for (var i=0;i<columns.length;i++)
  {
    html += "<option value=\"" + columns[i] + "\"";
    if ( columns[i] == fieldName )
    {
      html += " selected"
    }
    html += ">" + columns[i] + "</option>";
  }
  html += "</select>";
  */
  html += "<h3>Field: " + fieldName + ", <br>" + fieldNum + " unique value(s)</h3>";

  var div = window.document.getElementById("graph_text");
  div.innerHTML = html;
  div.style.position = "absolute";
  div.style.top = "0";
    var $parent = $("#graph_canvas");
  div.style.left = $parent.width() * 1 + "px";


}

function drawGraph (uriList, fieldName)
{
  resizeGraphCanvas();
  var c = window.document.getElementById("graph_canvas");

  var ctx = c.getContext("2d");
  var data = getPieGraphData(uriList, fieldName);

  var myChart = new Chart(ctx).Pie(data, {animation:false});
  return data.length;
}
function resizeGraphCanvas()
{
  var $canvas = $("#graph_canvas");
  var $parent = $("#graph");
  $canvas.width($parent.width() * .4);
  $canvas.height($canvas.width());
}
function getPieGraphData (uriList, fieldName) {
  var chartFields = [];
  var strTable = "";
  for (var i=0;i<uriList.length;i++)
  {
    var labelString = uriList[i][fieldName].toString();
    if (strTable.indexOf(labelString) == -1 )
    {
      strTable += labelString;
      chartFields.push (
        {
          label:labelString,
          value:1
        });
    } else {
      for (var j=0;j<chartFields.length;j++)
      {
        if (chartFields[j].label == labelString)
        {
          chartFields[j].value++;
        }
      }
    }
  }
  var colorArray = returnColorArray(chartFields.length);

  for (var i=0; i<chartFields.length; i++) {
    chartFields[i].color = colorArray[i];
  }
  return chartFields;
};

// Credit here goes to http://krazydad.com/tutorials/makecolors.php
function byte2Hex(n) {
  var nybHexString = "0123456789ABCDEF";
  return String(nybHexString.substr((n >> 4) & 0x0F,1)) + nybHexString.substr(n & 0x0F,1);
}

function RGB2Color(r,g,b) {
  return '#' + byte2Hex(r) + byte2Hex(g) + byte2Hex(b);
}

function returnColorArray (n) {
  var a = [];
  var frequency = 0.3;
  for (var i = 0; i < n; ++i) {
    var red   = Math.sin(frequency*i + 0) * 127 + 128;
    var green = Math.sin(frequency*i + 2) * 127 + 128;
    var blue  = Math.sin(frequency*i + 4) * 127 + 128;

    a.push (RGB2Color(red,green,blue));
  }
  return a;
}

function convertMilliseconds(n) {
  var hours = Math.floor (n/3600000);
  var minutes = Math.floor(n / 60000) % hours;
  var seconds = ((n % 60000) / 1000).toFixed(0);
  //return hours + " : " + minutes + ":" + (seconds < 10 ? '0' : '') + seconds;
  return Math.floor (n/60000) + " minutes";
}

function makeMetaTab(meta)
{
  var element = window.document.getElementById("metadata");
  var html = "";

  var argv_args = "";
  for (var i=0;i<meta.argv.length;i++)
  {
    argv_args += meta.argv[i] + "<br>";
  }

  var args = "";
  for (var i in meta.args)
  {
    args += i + " : " + meta.args[i] + "<br>";
  }

  var metaArray = [];
  metaArray.push (["<b>Source name, number of sites</b>", meta.args.source + ", " + meta.sources_size]);
  metaArray.push (["<b>Total test time</b>", convertMilliseconds(new Date (meta.run_finish_time) - new Date (meta.run_start_time))]);
  metaArray.push (["<b>Platform</b>", meta.test_metadata.appConstants.platform]);
  metaArray.push (["<b>TLS Canary version</b>", meta.tlscanary_version]);
  metaArray.push (["<b>argv parameters</b>", meta.argv.toString()]);
  metaArray.push (["<b>Run log</b>", "<a href=\"log.json\">&#128279; link</a>"]);
  metaArray.push (["<b>OneCRL environment</b>", meta.args.onecrl]);
  metaArray.push (["<b>Test build</b>", meta.test_metadata.app_version + " " + meta.test_metadata.branch])
  metaArray.push (["<b>Test build origin</b>", meta.test_metadata.package_origin]);
  metaArray.push (["<b>Test build ID</b>", meta.test_metadata.application_ini.buildid]);
  metaArray.push (["<b>Test build NSS</b>", meta.test_metadata.nss_version]);
  metaArray.push (["<b>Test build NSPR</b>", meta.test_metadata.nspr_version]);
  metaArray.push (["<b>Test profile</b>", "<a href=\"test_profile.zip\">&#128193; link</a>"]);
  metaArray.push (["<b>Base build</b>", meta.base_metadata.app_version + " " + meta.base_metadata.branch])
  metaArray.push (["<b>Base build origin</b>", meta.base_metadata.package_origin]);
  metaArray.push (["<b>Base build ID</b>", meta.base_metadata.application_ini.buildid]);
  metaArray.push (["<b>Base build NSS</b>", meta.base_metadata.nss_version]);
  metaArray.push (["<b>Base build NSPR</b>", meta.base_metadata.nspr_version]);
  metaArray.push (["<b>Base profile</b>", "<a href=\"base_profile.zip\">&#128193; link</a>"]);


  html += "<table id=\"grid-metadata\" class=\"table table-condensed table-hover table-striped\">";
  html += "<thead>";
  html += "<tr>";
  html += "<th data-column-id=\"t0\" width=\"30%\"></th>";
  html += "<th data-column-id=\"t1\" width=\"70%\"></th>";
  html += "</tr>";
  html += "</thead>";

  for (var i=0;i<metaArray.length;i++)
  {
    html += "<tbody>";
    html += "<tr>";
    html += "<td>" + metaArray[i][0] + "</td>";
    html += "<td>" + metaArray[i][1] + "</td>";
    html += "</tr>";
    html += "</tbody>";

  }
  html += "</table>";

  element.innerHTML = html;

}

function navigate(tab)
{
  var $nav = $("#nav");
  var listItems = $nav.children();

  var tabs = ["results", "graph", "metadata"];

  for (var i=0;i<tabs.length;i++)
  {
        window.document.getElementById(tabs[i]).style.visibility = "hidden";    
        listItems[i].id = tabs[i] + "_tab";
  }
  window.document.getElementById(tab).style.visibility = "visible";
  window.document.getElementById(tab + "_tab").id = "selected";

}

function getVisibleColumns()
{
  var gridData = $('#grid').bootgrid("getCurrentRows");

  var columnData = $("#grid").bootgrid("getColumnSettings");
  var columns = [];
  for (var i=0;i<columnData.length;i++)
  {
      if (columnData[i].visible)
      {
        if (columnData[i].id != "Actions")
        {
          columns.push (columnData[i].id);
        }
      }
  }
  return columns;
}
function getSortedRows()
{
  var gridData = $('#grid').bootgrid().data('.rs.jquery.bootgrid').rows;

  var currentRows = [];
  var searchStr = $('#grid').bootgrid("getSearchPhrase");
  var currentColumns = getVisibleColumns();

  for (var i=0;i<gridData.length;i++)
  {
    var row = gridData[i];
    for (var j=0;j<currentColumns.length;j++)
    {
      var field = row[currentColumns[j]].toString();
     
     
      if ( field.indexOf(searchStr) != -1 )

      {
        currentRows.push (row);
        break;
      }
      
    }
  }
  return currentRows;
}

function make_table(hosts, columns)
{
  // First, add new column for our grid actions
  columns.push ({
    name:"Actions",
    default:true,
    type:null,
    width:"20%"
  })
  var html = "<table id=\"grid\" class=\"table table-condensed table-hover table-striped\"><thead><tr>";
  for (var i=0;i<columns.length;i++)
  {
    html += "<th data-column-id=\"" + columns[i].name + "\" ";
    if (columns[i].name == "rank")
    {
      html += "data-order=\"asc\" ";
      html += "data-identifier=\"true\" ";
    }
    if (columns[i].name == "Actions")
    {
      html += "data-visible-in-selection=\"false\" data-formatter=\"commands\" ";
    }
    if (!columns[i].default)
    {
      html += "data-visible=\"false\" ";
    }
    if (columns[i].type == "int")
    {
      html += "data-type=\"numeric\" ";
    }
    if (columns[i].width != undefined)
    {
      html += "data-width=\"" + columns[i].width + "\" ";
    } else {
      html += "data-width=\"20%\" ";
    }


    // 
    html += ">" + columns[i].name + "</th>"
  }
  html += "</tr></thead><tbody>";

  for (var i=0;i<hosts.length;i++)
  {
    html += "<tr id=\'" + hosts[i]["rank"] + "\'>";
    for (var j=0;j<columns.length;j++)
    {
      html += "<td>" + hosts[i][columns[j].name] + "</td>"
    }
    html += "</tr>";
  }
  html += "</tbody></table>";
  var contentDiv = document.getElementById("results");
  contentDiv.style.visibility = "hidden";
  contentDiv.innerHTML = html;
}

function apply_bootgrid()
{
  var grid = $("#grid").bootgrid(
  {
    rowCount:[15,10,5,-1],
    selection: false,
    multiSelect: true,
    rowSelect: true,
    keepSelection: true,
    formatters: 
    {
      "commands": function(column, row)
      {  
        var html = "";
        if (row.not_before != undefined && row.not_before != "")
        {
          html += "<a href=\"./certs/" + row.host 
               + ".der\"><button type=\"button\" class=\"btn btn-xs btn-default\">&#128274;</button></a> ";
        }                    
        html += "<button type=\"button\" class=\"btn btn-xs btn-default command-link\" data-row-id=\"" 
             + row.host + "\"><span>&#128279; </span></button> " +
              "<button type=\"button\" class=\"btn btn-xs btn-default command-tls_obs\" data-row-id=\"" 
             + row.host + "\"><span class=\"fa fa-trash-o\"> &#128270; </span></button> " +
              "<button type=\"button\" class=\"btn btn-xs btn-default command-delete\" data-row-id=\"" 
             + row.rank + "\"><span class=\"fa fa-trash-o\"> &times; </span></button>";
        return html;
      },
      "date": function(column,row)
      {
        var temp = String(row[column.id]).substr(0,13);
        var d = new Date(Number(temp));
        return d.toString();
      }
    }
  }).on("loaded.rs.jquery.bootgrid", function ()
  {
    grid.find(".command-link").on("click", function(e)
    {
        window.open("https://" + $(this).data("row-id"), "_blank")
        ;
    }).end().find(".command-tls_obs").on("click", function(e)
    {
        window.open("https://observatory.mozilla.org/analyze.html?host=" + $(this).data("row-id") + "#tls", "_blank")
    }).end().find(".command-delete").on("click", function(e)
    {
      var items = [];
      items.push ($(this).data("row-id"));
      
      $("#grid").bootgrid("remove", items);

    });
    var contentDiv = document.getElementById("results");
    contentDiv.style.visibility = "visible";
  });
}

function find_prop (obj, prop, defval)
{
  if (defval == undefined) defval = null;
  prop = prop.split('.');
  for (var i = 0; i < prop.length; i++) {
      if(typeof obj[prop[i]] == 'undefined')
          return defval;
      obj = obj[prop[i]];
  }
  return obj;
}

function transform_log(transform_data,json_data)
{
  var hosts = [];
  for (var i=0;i<json_data.data.length;i++)
  {
    var host = {};
    for (var j=0;j<transform_data.length;j++)
    {
      var prop = find_prop(json_data.data[i], transform_data[j].prop, "");
      host[transform_data[j].name] = prop;
    }
    hosts.push (host);
  }
  return hosts;
}


function load_log(transform_data)
{
  var xhr = new XMLHttpRequest();
  xhr.onload = function(arg) {
    json_data =  JSON.parse(xhr.responseText)[0];
    var hosts = transform_log(transform_data,json_data);
    buildUI(json_data, hosts, transform_data);
  }       
  xhr.open('GET', "log.json", true);
  xhr.send();  
}
    
function buildUI(json_data, hosts, transform_data)
{
  makeHeaderText(json_data.meta);
  makeMetaTab(json_data.meta);
  make_table (hosts, transform_data);
  apply_bootgrid();
  makeGraphTab(hosts, "error");
  navigate("results");
}

function load_transform()
{
  var xhr = new XMLHttpRequest();
  xhr.onload = function(arg) {
    var transform_data =  JSON.parse(xhr.responseText);
    columns = transform_data;
    load_log(transform_data);
  }       
  xhr.open('GET', "transform.json", true);
  xhr.send(); 
}

function init()
{
  load_transform();
}

init();