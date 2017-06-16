function IndexPage(div) {
  this.tabs = [];
  this.currentTabIndex;
  this.DEFAULT_TAB = 0;
  this.masterDiv = div;
  this.defaultView = ["run","branch","errors","description"];
}

IndexPage.prototype = new TLSCanary();

IndexPage.prototype.load = function (uri) {
  this.dataURL = uri;
  var req = new XMLHttpRequest();
  req.onload = this.loadSuccess.bind(this);
  req.onerror = this.loadError.bind(this);
  req.open("GET", uri);
  req.send();
};

IndexPage.prototype.loadSuccess = function (e) {
  var doc = Data.parseDocument2(e.target.response.toString());
  this.metadata = "title";
  this.uriList = doc.uriList.reverse();
  this.makeViewObject(this.uriList[0], this.defaultView);
  this.updateView();
  this.init();
};

IndexPage.prototype.makeViewObject = function (obj, view) {
  this.fieldList = [];
  this.viewObject = {};
  for (var i in obj) {
    this.fieldList.push(i);
    this.viewObject[i] = false;
  }
  for (var k=0; k<view.length; k++) {
    eval ("this.viewObject." + view[k] + " = true;");
  }
};

IndexPage.prototype.init = function () {
  document.captureEvents(Event.MOUSEMOVE); // TODO: addEventListener
  document.onmousemove = this.getMouse.bind(this);

  // make tabs
  this.currentTabIndex = 0;
  this.addTab("Runs", true, this.uriList, "run", this.makeGrid);
  this.tabs[0].sortOrder = 1;

  var betaData = Data.filterBy(this.uriList, "branch", "Beta", false);
  this.addTab("Chart : Beta", true, betaData.reverse(), "errors", this.makeBarChart);

  var auroraData = Data.filterBy(this.uriList, "branch", "Aurora", false);
  this.addTab("Chart : Aurora", true, auroraData.reverse(), "errors", this.makeBarChart);

  var nightlyData = Data.filterBy(this.uriList, "branch", "Nightly", false);
  this.addTab("Chart : Nightly", true, nightlyData.reverse(), "errors", this.makeBarChart);

  var allData = Data.filterBy(this.uriList, "branch", "all", true);
  this.addTab("Chart : All", true, allData.reverse(), "errors", this.makeBarChart);

  this.addTab("?", true, this.uriList, "run", this.makeInfo);

  var title = "TLS Canary: A tool for finding Firefox SSL regressions";
  document.title = title;

  // add tab component
  this.tc = new TabContainer(this.masterDiv);
  this.tc.setTitle(title);
  this.tc.createTabs (this.tabs);
  this.tc.drawTabs();
  this.tc.changeTabSelection(this.DEFAULT_TAB);
  this.tabListener = {};
  this.tabListener.onChange = this.onTabChange.bind(this);
  this.tabListener.onRemove = this.removeTab.bind(this);
  this.tc.addListener(this.tabListener);
  this.tabs[this.DEFAULT_TAB].action(this.DEFAULT_TAB);

  this.floater = Utility.createElement("div", [{id:"floater"}]);
  this.floater.style.visibility = "hidden";
  this.masterDiv.appendChild(this.floater);
};

IndexPage.prototype.makeGrid = function(arg) {
  var currentTab = this.tabs[arg];
  this.grid = new URIGrid(currentTab.data, this.currentView, currentTab.field, currentTab.sortOrder, true);
  this.grid.addListener (this);
  this.tc.setContent(this.grid.html);
  this.tc.changeTabLabel(arg, "Runs : " + currentTab.data.length + " total");
};

IndexPage.prototype.makeInfo = function(arg) {
  var currentTab = this.tabs[arg];
  var div = Utility.createElement("div");
  var link = Utility.createElement("a", [{href:"https://github.com/mwobensmith/ssl_compat/"}]);
  link.appendChild(document.createTextNode("More info on GitHub repo here."));
  div.appendChild(link);
  this.tc.setContent(div);
};

IndexPage.prototype.makeBarChart = function(arg) {
  var table = Utility.createElement("table", [{width:"100%"}]);
  var tr1 = Utility.createElement("tr");
  var tr2 = Utility.createElement("tr");
  var tr3 = Utility.createElement("tr");

  var td1 = Utility.createElement("td");
  var td2 = Utility.createElement("td");
  var td3 = Utility.createElement("td");
  table.style.border = "none";
  td1.style.border = "none";
  td2.style.border = "none";
  td3.style.border = "none";

  var chartData = Data.getBarGraphData(this.tabs[arg].data, this.tabs[arg].field);

  var l = this.tabs[arg].data.length;
  var beginRun = this.tabs[arg].data[0].run;
  var endRun = this.tabs[arg].data[l-1].run;
  var msg = this.makePrettyDateString (beginRun, endRun);
  var label = Utility.createElement("h1");
  var str = document.createTextNode(msg);
  label.appendChild(str);
  td1.appendChild(label);
  tr1.appendChild(td1);

  tr2.appendChild(td2);

  var myCanvas = Utility.createElement("canvas");
  myCanvas.width = 800;
  myCanvas.height = 400;

  td3.appendChild(myCanvas);
  var myDiv = Utility.createElement("div");
  tr3.appendChild(td3);
  table.appendChild(tr1);
  table.appendChild(tr2);
  table.appendChild(tr3);

  Utility.appendChildren(myDiv, table);
  ctx2 = myCanvas.getContext("2d");
  this.tc.setContent (myDiv);
  var myPieChart = new Chart(ctx2).Bar(chartData, {animation:true});
};

IndexPage.prototype.makePrettyDateString = function (str1, str2) {
  var s1 = str1.split("-");
  var s2 = str2.split("-");
  var r1 = s1[0] + "-" + s1[1] + "-" + s1[2];
  var r2 = s2[0] + "-" + s2[1] + "-" + s2[2];
  return "Errors per run, from " + r1 + " to " + r2;
};
