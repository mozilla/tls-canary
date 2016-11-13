function Utility() {}

Utility.createElement = function ( element, attributeArray) {
  var node = document.createElement(element);
  if (attributeArray !== undefined) {
    for (var i=0;i<attributeArray.length;i++) {
      for (var attribute in attributeArray[i]) {
        var a = document.createAttribute(attribute);
        a.value = attributeArray[i][attribute];
        node.setAttributeNode(a);
      }
    }
  }
  return node;
};

Utility.appendChildren = function(nodes) {
  var parentNode = arguments[0];
  for (var i=1;i<arguments.length;i++) {
    parentNode.appendChild(arguments[i]);
  }
  return parentNode;
};

function decodeEntities(s){
  var str, temp= document.createElement('p');
  temp.innerHTML= s;
  str= temp.textContent || temp.innerText;
  temp=null;
  return str;
}

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
