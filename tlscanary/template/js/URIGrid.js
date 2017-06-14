function URIGrid(uriList, view, selectedColumn, sortOrder, removeIcons) {
  URIGrid.SORT_ASCENDING = 0;
  URIGrid.SORT_DESCENDING = 1;
  URIGrid.ASCENDING_GLYPH = String.fromCharCode(9650);
  URIGrid.DESCENDING_GLYPH = String.fromCharCode(9660);
  URIGrid.DELETE_GLYPH = String.fromCharCode(8864);
  URIGrid.GRAPH_GLYPH = String.fromCharCode(9680);
  URIGrid.SPACE_GLYPH = String.fromCharCode(8192);
  URIGrid.PADLOCK = decodeEntities(" &#128274;");
  URIGrid.DOCUMENT_GLYPH = String.fromCharCode(9032);
  this.glyphs = [URIGrid.ASCENDING_GLYPH, URIGrid.DESCENDING_GLYPH];
  this.name = "URIGrid";
  this.pageSize = 25;
  this.currentPage = 1;
  this.pageController;
  this.sortOrder = sortOrder;
  this.selectedColumn = selectedColumn;
  this.listeners = [];
  this.data = uriList;
  this.obj = this;
  this.removeIcons = removeIcons;
  this.html = this.getHTMLFromList(uriList,view,this.pageSize);
}

URIGrid.prototype.overrideColumnIcons = function() {
  URIGrid.DELETE_GLYPH = "";
  URIGrid.GRAPH_GLYPH = "";
  URIGrid.SPACE_GLYPH = "";
};

URIGrid.prototype.addListener = function (callback) {
  this.listeners.push(callback);
};

URIGrid.prototype.redraw = function (uriList, view) {
  this.html = this.getHTMLFromList(uriList,view,this.pageSize);
};

URIGrid.prototype.getHTMLFromList = function (uriList, view, pageSize) {
  var tempList = [];
  var div = Utility.createElement("div");
  var table = Utility.createElement("table", [{id:"grid"}]);
  var header = this.createColumnHeaderFields(uriList[0], view);
  table.appendChild(header);
  //for (var i=0;i<uriList.length;i++)
  var begin_index = (this.currentPage-1)*this.pageSize;
  var end_index = (this.currentPage*this.pageSize)-1;
  var range = Math.ceil(uriList.length/this.pageSize);
  if (this.currentPage == range) {
    end_index = begin_index + (uriList.length-begin_index);
  }

  for (var i=begin_index;i<end_index;i++) {
    var tr = Utility.createElement("tr");
    var id = document.createAttribute("id");
    id.value="field";
    tr.setAttributeNode(id);
    var td;

    for (var j=0;j<view.length;j++) {
      for (var k=0;k<view.length;k++) {
        td = this.createFieldsFromRow(uriList[i], view, j);
      }
      tr.appendChild(td);
    }
    table.appendChild(tr);
  }
  this.pageController = new PageController(range,this.currentPage,this.onPageSelect.bind(this));
  div.appendChild( this.pageController );

  div.appendChild(table);
  return div;
};

URIGrid.prototype.onPageSelect = function (arg) {
  this.currentPage=arg;

  for (var i=0;i<this.listeners.length;i++) {
    this.listeners[i].onPageSelect(arg);
  }
};

URIGrid.prototype.createFieldsFromRow = function(row,view,index) {
  var o = row;
  for (var i=0;i<view.length;i++) {
    var td = Utility.createElement("td");
    var a = Utility.createElement("a");
    a.obj = this;
    a.onclick = this.onClick;
    a.onmouseover = this.onMouseOver.bind(this);

    var id = document.createAttribute("id");
    id.value=view[index];
    a.setAttributeNode(id);

    var label = document.createTextNode(eval ("o." + view[index]) );
    a.appendChild(label);
    td.appendChild(a);

    var hasCert;
    try {
      hasCert = ( eval ("o.cert_info.isEV") !== "" );
    } catch (e) {
      hasCert = false;
    }
    if (index === 0 && hasCert) {
      var cert_uri = eval ("o.site_info.uri");
      var padlock = Utility.createElement("a", [{id:"padlock"}, {uri:cert_uri}, {href:"certs/"+cert_uri+".der"}]);
      padlock.onclick = this.onCertClick.bind(this, cert_uri);
      var p_label = document.createTextNode (URIGrid.PADLOCK);
      padlock.appendChild(p_label);
      td.appendChild(padlock);
    }

  }
  return td;
};

URIGrid.prototype.createColumnHeaderFields = function(row, view) {
  var o = row;
  var tr = Utility.createElement("tr");
  var id = document.createAttribute("id");
  id.value="column_header";
  tr.setAttributeNode(id);

  for (var i=0;i<view.length;i++) {
    var td= Utility.createElement("td");
    var a = Utility.createElement("a");
    a.href = "#";
    a.obj = this;
    a.onclick = this.onColumnSelect;
    var id = document.createAttribute("id");
    id.value = view[i];
    a.setAttributeNode(id);
    var label = document.createTextNode(view[i]);
    a.appendChild(label);
    td.appendChild(a);

    var delete_icon = Utility.createElement("a");
    delete_icon.href="#";
    delete_icon.onclick = this.onIconClick.bind(this);
    delete_icon.onmouseover = this.onMouseOver.bind(this);
    var delete_id = document.createAttribute("id");
    delete_id.value = "delete";
    delete_icon.setAttributeNode(delete_id);

    var delete_field = document.createAttribute("field");
    delete_field.value=view[i];
    delete_icon.setAttributeNode(delete_field);

    var chart_icon = Utility.createElement("a");
    chart_icon.href="#";
    chart_icon.onclick = this.onIconClick.bind(this);
    chart_icon.onmouseover = this.onMouseOver.bind(this);

    var chart_id = document.createAttribute("id");
    chart_id.value = "chart";
    chart_icon.setAttributeNode(chart_id);
    var chart_field = document.createAttribute("field");
    chart_field.value=view[i];
    chart_icon.setAttributeNode(chart_field);

    var raw_list_icon = Utility.createElement("a");
    raw_list_icon.href="#";
    raw_list_icon.onclick = this.onIconClick.bind(this);
    raw_list_icon.onmouseover = this.onMouseOver.bind(this);

    var raw_list_id = document.createAttribute("id");
    raw_list_id.value = "list";
    raw_list_icon.setAttributeNode(raw_list_id);
    var raw_list_field = document.createAttribute("field");
    raw_list_field.value=view[i];
    raw_list_icon.setAttributeNode(raw_list_field);

    var glyph_text;
    var delete_icon_text;
    var chart_icon_text;
    var raw_list_icon_text;

    if (view[i] === this.selectedColumn) {
      glyph_text = document.createTextNode(URIGrid.SPACE_GLYPH + this.glyphs[this.sortOrder] + URIGrid.SPACE_GLYPH);
      delete_icon_text = document.createTextNode(URIGrid.DELETE_GLYPH);
      chart_icon_text = document.createTextNode(URIGrid.GRAPH_GLYPH);
      raw_list_icon_text = document.createTextNode(URIGrid.DOCUMENT_GLYPH);
      delete_icon.appendChild(delete_icon_text);
      chart_icon.appendChild(chart_icon_text);
      raw_list_icon.appendChild(raw_list_icon_text);

      td.appendChild(glyph_text);
      if (!this.removeIcons) {
        td.appendChild(delete_icon);
        td.appendChild(chart_icon);
        td.appendChild(raw_list_icon);
      }
    }
    tr.appendChild(td);
  }
  return tr;
};

URIGrid.prototype.setSelectedColumn = function (field) {
  this.selectedColumn = field;
};

URIGrid.prototype.setSortOrder = function (order) {
  this.sortOrder = order;
};

URIGrid.prototype.onColumnSelect = function (e) {
  // for now
  var o = {};
  o.target = e.target;
  o.field = e.target.attributes[1].value;
  o.value = e.target.firstChild.wholeText;
  for (var i=0;i<e.target.obj.listeners.length;i++) {
    e.target.obj.listeners[i].onColumnSelect(o);
  }
};

URIGrid.prototype.onClick = function (e) {
  var o = {};
  o.target = e.target;
  o.field = e.target.attributes[0].value;
  o.value = e.target.firstChild.wholeText;

  for (var i=0;i<e.target.obj.listeners.length;i++)
  {
    e.target.obj.listeners[i].onGridSelect(o);
  }
};

URIGrid.prototype.onCertClick = function(arg) {
  for (var i=0;i<this.listeners.length;i++) {
    this.listeners[i].onCertClick(arg);
  }
};

URIGrid.prototype.onIconClick = function(e) {
  var o = {};
  o.target = e.target;
  o.field = e.target.attributes[2].value;
  o.value = e.target.attributes[1].value;

  for (var i=0;i<this.listeners.length;i++) {
    this.listeners[i].onIconClick(o);
  }
};

URIGrid.prototype.onMouseOver = function (e) {
  for (var i=0;i<this.listeners.length;i++) {
    this.listeners[i].onGridMouseOver(e);
  }
};
