
function updateUI(arg)
{
  window.document.getElementById("results_tab").innerHTML = "Results: " + arg;
}

function makeHeaderText(meta)
{
  var desc = "Fx " + meta.test_metadata.app_version + " " + meta.test_metadata.branch 
          + " vs Fx " + meta.base_metadata.app_version + " " + meta.base_metadata.branch;
  var time = meta.run_start_time.split(".")[0].replace("T","-").replace(":","-").replace(":","-");
  window.document.getElementById("header").innerHTML = "<h3>" + desc + "<br>" + time + "</h3>";
}

function makeGraphTab(meta)
{
  window.document.getElementById("graph").innerHTML = "graph coming soon";
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
  var contentDiv = window.document.getElementById("content");
  var tabs = ["results", "graph", "metadata"];
  for (var i=0;i<tabs.length;i++)
  {
        window.document.getElementById(tabs[i]).style.visibility = "hidden";
  }
  window.document.getElementById(tab).style.visibility = "visible";
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
      html += "data-formatter=\"commands\" ";
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
             + row.host + "\"><span class=\"fa fa-trash-o\"> &#128270; </span></button>";
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
  new_data = hosts;
  make_table (hosts, transform_data);
}


function load_log(transform_data)
{
  var xhr = new XMLHttpRequest();
  xhr.onload = function(arg) {
    json_data =  JSON.parse(xhr.responseText)[0];
    transform_log(transform_data,json_data);
    buildUI(json_data);
  }       
  xhr.open('GET', "log.json", true);
  xhr.send();  
}
    
function buildUI(data)
{
    makeHeaderText(data.meta);
    makeMetaTab(data.meta);
    makeGraphTab();
    apply_bootgrid();



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