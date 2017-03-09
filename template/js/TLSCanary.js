function TLSCanary(div) {
  this.name = "TLSCanary";
  this.dataURL;
  this.tabs = [];
  this.currentTabIndex;
  this.DEFAULT_TAB = 1;
  this.masterDiv = div;
  this.defaultView = ["site_info.uri", "error.code", "error.type", "error.message"];
}

TLSCanary.prototype.getMouse = function(e) {
  this.mouseX = e.pageX;
  this.mouseY = e.pageY;
};

TLSCanary.prototype.load = function (uri) {
  this.dataURL = uri;
  var req = new XMLHttpRequest();
  req.onload = this.loadSuccess.bind(this);
  req.onerror = this.loadError.bind(this);
  req.open("GET", uri);
  req.send();
};

TLSCanary.prototype.loadSuccess = function (e) {
  var doc = Data.parseDocument(e.target.response.toString());
  this.metadata = doc.metadata;
  this.uriList = doc.uriList;
  if (this.uriList.length === 0) {
    var o = {};
    o.site_info = {};
    o.site_info.uri = "none";
    o.error = {};
    o.error.code = "none";
    o.error.type = "none";
    o.error.message = "No errors found!";
    this.uriList = [o];
  }

  this.makeViewObject(this.uriList[0], this.defaultView);
  this.updateView();
  this.init();
};

TLSCanary.prototype.loadError = function (e) {
  alert("Cannot load data");
};

TLSCanary.prototype.init = function () {
  document.captureEvents(Event.MOUSEMOVE); // TODO: addEventListener
  document.onmousemove = this.getMouse.bind(this);

  // make tabs
  this.currentTabIndex = this.DEFAULT_TAB;
  this.addTab("Fields", true, this.fieldList, "", this.makeFieldsUI);
  this.addTab("Grid", true, Data.sortByField(this.uriList, "site_info.uri"), "site_info.uri", this.makeGrid);
  this.addTab("Chart : error.message : " + this.uriList.length, true, this.uriList, "error.message", this.makeChart);

  // process metadata, change page title
  var timestamp = this.metadata[0].split(" : ")[1];
  var branch = this.metadata[1].split(" : ")[1];
  var description = this.metadata[2].split(" : ")[1];
  var source = this.metadata[3].split(" : ")[1];
  var pageTitle = "TLS Canary : " + timestamp + " : " + branch + " : " + source + " : " + description;
  document.title = pageTitle;

  // add tab component
  this.tc = new TabContainer(this.masterDiv);
  this.tc.setTitle(pageTitle);
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

TLSCanary.prototype.makeViewObject = function (obj, view) {
  this.fieldList = [];
  this.viewObject = {};
  for (var i in obj) {
    this.viewObject[i] = {};
    for (var j in obj[i]) {
      this.fieldList.push( i + "." + j);
      this.viewObject[i][j]= false;
    }
  }
  for (var k=0;k<view.length;k++) {
    eval ("this.viewObject." + view[k] + " = true;");
  }
};

TLSCanary.prototype.updateView = function () {
  // apply current view object to view array
  var newViewArray = [];
  for (var i=0;i<this.fieldList.length;i++) {
    if (eval ("this.viewObject." + this.fieldList[i])) {
      newViewArray.push(this.fieldList[i]);
    }
  }
  this.currentView = newViewArray;
};

TLSCanary.prototype.onTabChange = function(arg) {
  this.hideFloater();
  this.currentTabIndex = arg;
  this.tabs[arg].action(arg);
};

TLSCanary.prototype.makeChart = function(arg) {
  var table = Utility.createElement("table", [{width:"100%"}]);
  var tr = Utility.createElement("tr");
  var td1 = Utility.createElement("td");
  var td2 = Utility.createElement("td");
  table.style.border = "none";
  td1.style.border = "none";
  td2.style.border = "none";

  var chartData = Data.getPieGraphData(this.tabs[arg].data, this.tabs[arg].field);
  var totalSites = this.tabs[arg].data.length;
  var totalUniqueErrors = chartData.length;
  var msg = this.tabs[arg].field + ": " + totalSites + " sites total, " + totalUniqueErrors + " unique values";
  var label = Utility.createElement("h1");
  var str = document.createTextNode(msg);
  label.appendChild(str);
  td2.appendChild(label);

  var myCanvas = Utility.createElement("canvas");
  myCanvas.width=400;
  myCanvas.height=400;

  td1.appendChild(myCanvas);
  var myDiv = Utility.createElement("div");
  Utility.appendChildren(tr, td1, td2);
  table.appendChild(tr);

  Utility.appendChildren (myDiv, table, Utility.createElement("p"));
  ctx2 = myCanvas.getContext("2d");
  this.tc.setContent (myDiv);
  var myPieChart = new Chart(ctx2).Pie(chartData, {animation:false});
};

TLSCanary.prototype.makeGrid = function(arg) {
  var currentTab = this.tabs[arg];
  this.grid = new URIGrid(currentTab.data, this.currentView, currentTab.field, currentTab.sortOrder);
  this.grid.addListener (this);
  this.tc.setContent(this.grid.html);
  this.tc.changeTabLabel(arg, "Grid : " + currentTab.data.length + " sites");
};

TLSCanary.prototype.makeList = function(arg) {
  var currentTab = this.tabs[arg];
  var text = this.makeTextFromView (currentTab.data, currentTab.view);
  var textArea = Utility.createElement("textarea", [{width:"100%"}, {height:"100%"}, {rows:"40"},{id:"raw_list"}]);
  textArea.innerHTML = text;
  textArea.setAttributeNode(document.createAttribute("readonly"));
  this.tc.setContent(textArea);
};

TLSCanary.prototype.makeFieldsUI = function(arg) {
  var myDiv = Utility.createElement("div", [{width:"700"}]);
  var myTable = Utility.createElement("table", [{width:"700"}]);
  var tableRow = Utility.createElement("tr");
  var leftColumn = Utility.createElement("td", [{width:"50%"}]);
  var rightColumn = Utility.createElement("td", [{width:"50%"}]);
  var fields = this.tabs[arg].data;
  for (var i=0;i<fields.length;i++) {
    var checkboxAttributes = [{type:"checkbox"}, {name:fields[i]}, {value:fields[i]}];
    if (eval("this.viewObject." + fields[i])) {
      checkboxAttributes.push({checked:"checked"});
    }

    var checkbox = Utility.createElement("input", checkboxAttributes);
    checkbox.onclick = this.onUpdateCheckbox.bind(this);
    var label = Utility.createElement("label");
    var str = document.createTextNode(fields[i]);
    label.appendChild(str);
    var myColumn;
    if (i < fields.length / 2) {
      myColumn = leftColumn;
    } else {
      myColumn = rightColumn;
    }
    Utility.appendChildren (myColumn, checkbox, label, Utility.createElement("br"));
  }
  Utility.appendChildren(tableRow, leftColumn, rightColumn);
  myTable.appendChild(tableRow);

  //var t = new Data();
  myDiv.appendChild(myTable);
  this.tc.setContent(myDiv);
};

TLSCanary.prototype.onUpdateCheckbox = function (arg) {
  var checked = false;
  if (arg.target.checked) {
    checked = true;
  }
  var name = arg.target.attributes[1].value;
  eval ("this.viewObject." + name + "=" + checked + ";");
  this.updateView();
};

TLSCanary.prototype.onColumnSelect = function (arg) {
  var currentTab = this.tabs[this.currentTabIndex];
  var newData;
  //
  // TODO: better way of determining which sort to apply
  //
  if (arg.field.indexOf("connectionSpeed") !== -1 ||
      arg.field.indexOf("rank") !== -1 ||
      arg.field.indexOf("chainLength") !== -1 ||
      arg.field.indexOf("errors") !== -1) {
    newData = Data.numericSortByField(currentTab.data, arg.field);
  } else if (arg.field.indexOf("validity") !== -1)
  {
    newData = Data.dateSortByField(currentTab.data, arg.field);
  } else {
    newData = Data.sortByField(currentTab.data, arg.field);
  }

  if (arg.field == currentTab.field) {
    currentTab.sortOrder = Number(!Boolean(currentTab.sortOrder));
    if (currentTab.sortOrder) {
      newData.reverse();
    }
  } else {
    currentTab.sortOrder = 0;
  }
  currentTab.field = arg.field;
  this.grid.setSelectedColumn(arg.field);
  this.grid.setSortOrder(currentTab.sortOrder);
  this.grid.redraw(newData, this.currentView);
  this.tc.setContent(this.grid.html);
  currentTab.data = newData;
};

TLSCanary.prototype.onPageSelect = function (arg) {
  var currentTab = this.tabs[this.currentTabIndex];
  this.grid.redraw(currentTab.data, this.currentView);
  this.tc.setContent(this.grid.html);
};

TLSCanary.prototype.onCertClick = function (arg) {
  //window.open("certs/"+arg+".der", "_blank");
};

TLSCanary.prototype.onGridSelect = function (arg) {
  var list = Utility.createElement("ul");

  if (arg.field == "site_info.uri") {
    var url = arg.value;
    window.open("https://"+url, "_blank");
    this.hideFloater();
    return;
  } else if (arg.field == "run") {
    var url = "runs/" + arg.value + "/index.htm";
    window.open(url, "_blank");
    return;
  }
  var item1 = Utility.createElement("li");
  var removeAttributes = [{id:"remove"}, {href:"#"}, {field_name:arg.field}, {value:arg.value}];
  var removeItem = Utility.createElement("a", removeAttributes);
  removeItem.onclick = this.onFilter.bind(this);
  item1.appendChild(removeItem);
  removeItem.appendChild(document.createTextNode("remove all"));

  var item2 = Utility.createElement("li");
  var filterAttributes = [{id:"filter"}, {href:"#"}, {field_name:arg.field}, {value:arg.value}];
  var filterItem = Utility.createElement("a", filterAttributes);
  filterItem.onclick = this.onFilter.bind(this);
  item2.appendChild(filterItem);
  filterItem.appendChild(document.createTextNode("show only"));
  Utility.appendChildren(list, item1, Utility.createElement("br"), item2);
  this.showFloater (list);
};

TLSCanary.prototype.showFloater = function (content) {
  this.floater.style.visibility = "visible";
  this.floater.style.position = "absolute";
  this.floater.style.left = (this.mouseX + 10) + "px";
  this.floater.style.top = (this.mouseY - 20) + "px";
  this.floater.innerHTML = "";
  this.floater.appendChild(content);
};

TLSCanary.prototype.onGridMouseOver = function (arg) {
  this.hideFloater();

  var id = arg.target.attributes[1].value;
  var msg;
  if (id === "delete") {
    msg = "delete column from view";
  } else if (id === "chart") {
    msg = "make pie chart";
  } else if (id === "list") {
    msg = "export copy of list";
  } else {
    return;
  }

  this.timeoutInterval = setTimeout (this.showTooltip.bind(this), 200, msg);
};

TLSCanary.prototype.showTooltip = function(msg) {
  var list = Utility.createElement("ul");
  var item2 = Utility.createElement("li");
  var linkItem = Utility.createElement("text");
  item2.appendChild(linkItem);
  linkItem.appendChild(document.createTextNode(msg));
  Utility.appendChildren(list, item2);
  this.showFloater (list);
  setTimeout (this.hideFloater.bind(this), 7000);
};

TLSCanary.prototype.clearInterval = function(arg) {
  clearInterval(arg);
};

TLSCanary.prototype.hideFloater = function() {
  this.floater.style.visibility = "hidden";
};

TLSCanary.prototype.onFilter = function(arg) {
  this.onGridMouseOver(arg);
  var remove = arg.target.attributes[0].value == "remove";
  var field = arg.target.attributes[2].value;
  var value = arg.target.attributes[3].value;
  var newData = Data.filterBy(this.tabs[this.currentTabIndex].data, field, value, remove);
  this.grid.redraw(newData, this.currentView);
  this.tc.setContent(this.grid.html);
  this.tabs[this.currentTabIndex].data = newData;
  this.tc.changeTabLabel(this.currentTabIndex, "Grid : " + this.tabs[this.currentTabIndex].data.length + " sites");
};

TLSCanary.prototype.onIconClick = function (e) {
  var d = this.tabs[this.currentTabIndex].data;
  if (e.value === "delete") {
    eval ("this.viewObject." + e.field + "=false;");
    this.updateView();
    this.grid.redraw(d, this.currentView);
    this.tc.setContent(this.grid.html);
  } else if (e.value == "chart") {
    this.addTab("New Chart : " + e.field + " : " + d.length, false, d, e.field, this.makeChart);
  } else if (e.value == "list") {
    this.addTab("List : " + d.length + " sites", false, d, e.field, this.makeList);
  }
};

TLSCanary.prototype.makeTextFromView= function (data, view) {
  var temp = "";
  for (var i=0;i<data.length;i++) {
    for (var j=0;j<view.length;j++) {
      temp += eval ("data["+i+"]." + view[j]) + "\t";
    }
    temp += "\n";
  }
  return temp;
};

TLSCanary.prototype.addTab = function (label, permanent, data, field, callback) {
  var newTab = new Tab({label:label});
  newTab.data = data.slice();
  newTab.field = field;
  newTab.permanent = permanent;
  newTab.sortOrder = 0;
  newTab.index = this.tabs.length-1;
  newTab.action = callback.bind(this);
  newTab.view = this.currentView.slice();

  try{
    this.tabs.push(newTab);
    this.tc.addTab(newTab);
  } catch (e) {
    // no tab container available
  }
};

TLSCanary.prototype.removeTab = function (index) {
  if (index <= this.currentTabIndex && index >= this.tabs.length-2) {
    this.currentTabIndex--;
  }
  this.tabs.splice (index, 1);
  this.tc.updateTabs (this.tabs, this.currentTabIndex);
  this.tc.changeTabSelection(this.currentTabIndex);
  this.onTabChange(this.currentTabIndex);
};
