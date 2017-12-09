
var type_map = {};
var visible_columns = {};
var final_data = {};
var transform_rules;

function test(arg)
{
	alert("Hello world " + arg);
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

function transform_log(json_data)
{
	var hosts = [];
	var str = "";
	for (var i=0;i<json_data.data.length;i++)
	{
		var host = {};
		for (var j=0;j<transform_rules.length;j++)
		{
			var prop = find_prop(json_data.data[i], transform_rules[j].prop, "");
			host[transform_rules[j].name] = prop;
		}
		hosts.push (host);
	}
	final_data.data = hosts;
	return hosts;

}
function save_field_types (data)
{
	for (var i=0;i<data.length;i++)
	{
		type_map[data[i].name] = data[i].type;
		visible_columns[data[i].name] = data[i].default;
	}
}

function load_log(uri)
{
	var xhr = new XMLHttpRequest();
	xhr.onload = function(arg) {
		json_data =  JSON.parse(xhr.responseText)[0];
		final_data.meta = json_data.meta;
		transform_log(json_data);
	}       
	xhr.open('GET', uri, true);
	xhr.send();  
}
    
function load_transform()
{
	var xhr = new XMLHttpRequest();
	xhr.onload = function(arg) {
		transform_rules =  JSON.parse(xhr.responseText);
		save_field_types(transform_rules);
	}       
	xhr.open('GET', "transform.json", true);
	xhr.send(); 
}
// first make explicit call to load_transform
// then load_log
// transformed log is available as final_data
