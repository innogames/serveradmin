function IP(value)
{
    if (typeof(value) == 'string') {
        var ip_int = 0;
        var segments = value.split('.');
        for(var i = 0; i < segments.length; i++) {
            ip_int = ip_int << 8;
            ip_int |= parseInt(segments[i], 10);
        }
        this.value = ip_int
    } else {
        this.value = value
    }

    if (this.value < 0) {
        // hack to have this value as "unsigned" int in javascript
        this.value += -2 * (1 << 31);
    }
}

IP.prototype.as_ip = function() {
    var ip = [0, 0, 0, 0];
    ip_int = this.value;
    for (var i = 0; i < 4; i++) {
        ip[i] = (ip_int & 0xff) + '';
        ip_int = ip_int >> 8
    }
    return ip[3] + '.' + ip[2] + '.' + ip[1] + '.' + ip[0];
}

IP.prototype.as_int = function() {
    return this.value;
}

// Array Remove - By John Resig (MIT Licensed)
Array.prototype.remove = function(from, to) {
  var rest = this.slice((to || from) + 1 || this.length);
  this.length = from < 0 ? this.length + from : from;
  return this.push.apply(this, rest);
};

jQuery(document).ajaxSend(function(event, xhr, settings) {
    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie != '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = jQuery.trim(cookies[i]);
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) == (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    function sameOrigin(url) {
        // url could be relative or scheme relative or absolute
        var host = document.location.host; // host + port
        var protocol = document.location.protocol;
        var sr_origin = '//' + host;
        var origin = protocol + sr_origin;
        // Allow absolute or scheme relative URLs to same origin
        return (url == origin || url.slice(0, origin.length + 1) == origin + '/') ||
            (url == sr_origin || url.slice(0, sr_origin.length + 1) == sr_origin + '/') ||
            // or any other URL that isn't scheme relative or absolute i.e relative.
            !(/^(\/\/|http:|https:).*/.test(url));
    }
    function safeMethod(method) {
        return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
    }

    if (!safeMethod(settings.type) && sameOrigin(settings.url)) {
        xhr.setRequestHeader("X-CSRFToken", getCookie('csrftoken'));
    }
});

function show_spinner() {
    $('#spinner').show();
}

function hide_spinner() {
    $('#spinner').hide();
}

escapehtml = (function() {
    var escape_map = { '"': '&quot;', '&': '&amp;', '<': '&lt;', '>': '&gt;' };
    return function(text) {
        return text.replace(/[\"&<>]/g, function (m) { return escape_map[m]; });
    }
})();
