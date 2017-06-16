function PageController(range, start, callback)
{
  PageController.END_GLYPH = String.fromCharCode(9193);
  PageController.START_GLYPH = String.fromCharCode(9194);
  PageController.FORWARD_GLYPH = String.fromCharCode(9658);
  PageController.BACK_GLYPH = String.fromCharCode(9668);

  this.limit = range;
  this.position = start;
  this.listener = callback;

  return this.init(range, start);
}

PageController.prototype.init = function(range, start_num) {
  var master_container = Utility.createElement("table");
  var table_id = document.createAttribute("id");
  table_id.value="page_controller";
  master_container.setAttributeNode(table_id);
  var tr = Utility.createElement("tr");
  var td1 = Utility.createElement("td");
  var td2 = Utility.createElement("td");

  var container1 = Utility.createElement("p", [{align:"left"}]);

  var export_button = Utility.createElement("button", [{type:"button"}]);
  var export_label = document.createTextNode("Export site list");
  export_button.appendChild(export_label);

  var restart_button = Utility.createElement("button", [{type:"button"}]);
  var restart_label = document.createTextNode("Start over");
  restart_button.appendChild(restart_label);

  Utility.appendChildren(container1, export_button, restart_button);
  //td1.appendChild(container1);

  var container2 = Utility.createElement("p", [{align:"right"}]);
  var id = document.createAttribute("id");
  container2.setAttributeNode(id);

  var start = Utility.createElement("a", [{id:"start"}]);
  start.href="#";
  start.onclick = this.onSelect.bind(this);

  var start_label = document.createTextNode(PageController.START_GLYPH);
  start.appendChild(start_label);

  var back = Utility.createElement("a", [{id:"back"}]);
  back.href = "#";
  back.onclick = this.onSelect.bind(this);

  var back_label = document.createTextNode(PageController.BACK_GLYPH);
  back.appendChild(back_label);

  var current = Utility.createElement("text", [{id:"current"}]);
  this.current_label = document.createTextNode(start_num);
  current.appendChild(this.current_label);

  var maximum = Utility.createElement("text", [{id:"maximum"}]);
  this.maximum_label = document.createTextNode("/ " + range);
  maximum.appendChild(this.maximum_label);

  var forward = Utility.createElement("a", [{id:"forward"}]);
  forward.href="#";
  forward.onclick = this.onSelect.bind(this);

  var forward_label = document.createTextNode(PageController.FORWARD_GLYPH);
  forward.appendChild(forward_label);

  var end = Utility.createElement("a", [{id:"end"}]);
  end.href="#";
  end.onclick = this.onSelect.bind(this);

  var end_label = document.createTextNode(PageController.END_GLYPH);
  end.appendChild(end_label);

  Utility.appendChildren(container2, start,back,current,maximum,forward,end);
  Utility.appendChildren(td2, container2);
  Utility.appendChildren(tr, td1, td2);
  master_container.appendChild(tr);
  return master_container;
};

PageController.prototype.onSelect = function (arg) {
  var target = arg.target.attributes[0].value;
  if (target === "forward") {
    if (this.position < this.limit) {
      this.position++;
      this.current_label.data = this.position;
    }
  } else if (target === "back") {
    if (this.position > 1) {
      this.position--;
      this.current_label.data = this.position;
    }
  } else if ( target === "start" ) {
    this.position=1;
    this.current_label.data = this.position;
  } else if ( target === "end" ) {
    this.position=this.limit;
    this.current_label.data = this.position;
  }

  this.listener(this.position);
};

PageController.prototype.setLimit = function (arg) {
  this.limit = arg;
};
