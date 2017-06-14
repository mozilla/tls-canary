function TabContainer(div) {
  this.name = "TabContainer";
  this.displayArea = div;
  this.listeners = [];
  this.tabArray = [];
  this.currentTabIndex = 0;
  this.DELETE_GLYPH = String.fromCharCode(8864);

  this.addListener = function (callback) {
    this.listeners.push(callback);
  };
  this.removeListener = function (callback) {
    // TODO
    // this.listeners....(callback);
  };
  this.init();
}

TabContainer.prototype.init = function () {
  var header = Utility.createElement("div", [{id:"header"}]);
  this.tabs = Utility.createElement("div", [{id:"tabs"}]);
  this.contentArea = Utility.createElement("div", [{id:"content"}, {width:100}, {height:300}]);
  this.label = Utility.createElement("h1", [{id:"label"}]);
  this.tabs.appendChild(this.label);
  this.displayArea.appendChild(Utility.appendChildren (header, this.tabs, this.contentArea));
  //this.setDefault();
};

TabContainer.prototype.setDefault = function() {
  var defaultTabs = [{label:"foo"}, {label:"bar"}];
  this.createTabs (defaultTabs);
  this.drawTabs();
  this.changeTabSelection(0);
  this.setContent("");
  this.setTitle("THIS IS A TITLE");
};

TabContainer.prototype.createTabs = function(tabArray) {
  for (var i=0;i<tabArray.length;i++) {
    var newTab = new Tab(tabArray[i]);
    newTab.label = tabArray[i].label;
    newTab.permanent = tabArray[i].permanent;
    this.tabArray.push(newTab);
  }
};

TabContainer.prototype.drawTabs = function() {
  this.tabList = Utility.createElement("ul");
  var numTabs = this.tabArray.length;
  for (var i=0;i<numTabs;i++) {
    var newTab = this.tabArray[i];
    var newListItem = Utility.createElement("li", [{id:"not_selected"}]);
    newTab.background = newListItem;
    var newAnchor = Utility.createElement("a", [{href:"#"},{id:i},{meta:"val_"+i}]);
    newAnchor.onclick = this.onTabChange.bind(this);

    var newLabel = document.createTextNode(newTab.label);
    newAnchor.appendChild(newLabel);

    var deleteBox = Utility.createElement("a");
    deleteBox.onclick = this.removeTab.bind(this, i);
    var deleteIcon = Utility.createElement("label");
    var text = document.createTextNode(this.DELETE_GLYPH);
    deleteIcon.appendChild(text);
    deleteBox.appendChild(deleteIcon);
    newListItem.appendChild(newAnchor);

    if (!newTab.permanent) {
      newListItem.appendChild(deleteBox);
    }
    this.tabList.appendChild(newListItem);
  }
  this.tabs.appendChild(this.tabList);
};

TabContainer.prototype.updateTabs = function(tabArray, index) {
  try {
    this.tabs.removeChild(this.tabList);
  } catch (e) {
  }
  this.tabArray = [];
  this.createTabs(tabArray);
  this.drawTabs();
};

TabContainer.prototype.addTab = function(tab, index) {
  this.tabs.removeChild(this.tabList);
  this.tabArray.push(new Tab(tab));
  this.drawTabs(this.tabArray);
  this.changeTabSelection(this.currentTabIndex);
};

TabContainer.prototype.removeTab = function(index) {
  this.onTabRemove(index);
};

TabContainer.prototype.changeTabLabel = function(index, label) {
  this.tabArray[index].label = label;
  this.updateTabs(this.tabArray);
  this.changeTabSelection(this.currentTabIndex);
};

TabContainer.prototype.setTitle = function(str) {
  // first remove node
  // this.label.removeChild ( ??? )
  // then add it again
  var labelText = document.createTextNode(str);
  this.label.appendChild(labelText);
};

TabContainer.prototype.setContent = function (arg) {
  this.contentArea.innerHTML = "";
  if (arg instanceof Node) {
    this.contentArea.appendChild(arg);
  } else {
    this.contentArea.innerHTML = arg.toString();
  }
};

TabContainer.prototype.onTabChange = function (arg) {
  var tabID = Number(arg.target.attributes[1].value);
  if (this.currentTabIndex == tabID) return;

  this.changeTabSelection(tabID);

  if (this.listeners.length > 0) {
    for (var i=0; i<this.listeners.length; i++) {
      this.listeners[i].onChange(tabID);
    }
  } else {
    this.setContent("");
  }
};

TabContainer.prototype.onTabRemove = function (arg) {
  for (var i=0; i<this.listeners.length; i++) {
    this.listeners[i].onRemove(arg);
  }
};

TabContainer.prototype.changeTabSelection = function (index) {
  if (index >= this.tabArray.length) {
    index = this.tabArray.length - 1;
  }
  try {
    this.tabArray[this.currentTabIndex].background.id="not_selected";
  } catch (e){
  }

  this.tabArray[index].background.id="selected";
  this.currentTabIndex = index;
};

function Tab(arg) {
  this.label = arg.label;
}
