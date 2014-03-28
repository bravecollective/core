// Date object additions.
Date.prototype.getISO() {
    var pad = function(n){ return n < 10 ? '0' + n : n }

    return this.getUTCFullYear() + '-'
        + pad(this.getUTCMonth() + 1) + '-'
        + pad(this.getUTCDate()) + 'T'
        + pad(this.getUTCHours()) + ':'
        + pad(this.getUTCMinutes()) + ':'
        + pad(this.getUTCSeconds()) + 'Z';
}

Date.prototype.getSimple() {
    var pad = function(n){ return n < 10 ? '0' + n : n }

    return this.getUTCFullYear() + '/'
        + pad(this.getUTCMonth() + 1) + '/'
        + pad(this.getUTCDate()) + ' '
        + pad(this.getUTCHours()) + ':'
        + pad(this.getUTCMinutes()) + ':'
        + pad(this.getUTCSeconds());
}


// console.* polyfill
(function() {
    var method;
    var noop = function () {};
    var methods = [
        'assert', 'clear', 'count', 'debug', 'dir', 'dirxml', 'error',
        'exception', 'group', 'groupCollapsed', 'groupEnd', 'info', 'log',
        'markTimeline', 'profile', 'profileEnd', 'table', 'time', 'timeEnd',
        'timeStamp', 'trace', 'warn'
    ];
    var length = methods.length;
    var console = (window.console = window.console || {});

    while (length--) {
        method = methods[length];

        // Only stub undefined methods.
        if (!console[method]) {
            console[method] = noop;
        }
    }
}());


// Retina-ize the EVE images.
$(function(){
    if ( window.devicePixelRatio >= 2 ) {
        $('img[src*="//image.eveonline.com/"]').each(function(index, element) {
            var self = $(element),
                current = self.attr('src'),
                size = current.match(/_(\d+)\.\w{3,4}/);

            if ( ! size ) return;
            size = parseInt(size[1]);

            self.attr('src', self.attr('src').replace(/(.+_)(\d+)(\.\w{3,4})$/, "$1" + (size*2) + "$3"));
        });
    }
});


// Mechanism for naturally delayed action after typing, e.g. auto-complete, password strength measurement, etc.
(function($){
    $.fn.changeDelay = function(callback, options) {
        if ( callback !== undefined ) {
            if ( $.isFunction(callback) ) this.on('commit', callback);
            else if ( options === undefined ) options = callback;
            else return;  // explode horribly?
        }

        var settings = $.extend({
            initial: 1000,  // initial delay value of one second
            highlight: false,  // when entering a field, select its contents
            minimum: 500, // minimum wait time
            threshold: 0,  // don't bother if the field has fewer than this many characters
            forceable: true  // ignore threshold on blur and when pressing enter
        }, options);

        function init(element, self) {
            var timeout,
                lastChange = 0,
                delay = settings.initial,
                value = self.val();

            function handler(ignore_threshold) {
                if ( ignore_threshold === undefined ) ignore_threshold = false;

                lastChange = 0;
                var nvalue = self.val();

                if ( ( !ignore_threshold && nvalue.length < settings.threshold ) || nvalue == value ) return;

                self.trigger('commit', [nvalue]);
                value = nvalue;
            }

            function check(event) {
                clearTimeout(timeout);

                if ( event.keyCode == 13 && this.type.toUpperCase() == "TEXT" ) handler(settings.forceable);

                if ( lastChange === 0 ) {
                    lastChange = Date.now();
                    delay = settings.initial;
                    timeout = setTimeout(handler, delay);
                    return;
                }

                var t = Date.now();
                delay = (delay + (t - lastChange) * 2) / 2;
                lastChange = t;
                timeout = setTimeout(handler, Math.max(settings.minimum, delay * 2))
            }

            self.on('keyup', check);
            self.on('blur', function(){ handler(settings.forceable) })
        }

        // Handle the highlighting feature.
        if ( settings.highlight ) this.on('focus.selection', function() { this.select(); });

        return this.each(function() { init(this, $(this)); });
    }
})(jQuery);


// Hook CSRF token support into jQuery AJAX.
$(function(){
    $(document).ajaxSend(function(event, xhr, settings) {
        // Exit early if this is a foreign XHR request.
        if ( /^http(s)?:.*/.test(settings.url) )
            return;
        
        var token = $.cookie('csrf');
        if ( ! token ) return;
        
        xhr.setRequestHeader('X-CSRF', token);
    });
});


// Flash notificaitons.
(function($) {
    $.Flash = function(element, timeout){
        var self = this;
        
        this.element = $(element);
        this.timeout = timeout;
        
        this.element.on('click.notice', '.notice', this.hide);
        this.element.on('mouseenter.notice', '.notice', this.disable);
        this.element.on('mouseleave.notice', '.notice', this.enable);
    };
    
    $.Flash.prototype.message = function(klass, label, message, href) {
        var notice = $('<div class="notice ' + klass + '"><dl class="dl-horizontal container">' +
                '<dt>' + label + '</dt><dd>' + message + '</dd>' +
                '</dl></div>');
        
        notice.data('flash', this);
        if ( href !=== undefined ) notice.data('target', href);
        
        this.enable.call(notice);
        this.show.call(notice);
    };
    
    $.Flash.prototype.show = function() {
        $.flash.element.append(this);
    }
    
    $.Flash.prototype.hide = function(element) {
        this.remove();
        if ( this.data('timeout') ) clearTimeout(this.data('timeout'));
    };
    
    $.Flash.prototype.enable = function() {
        if ( this.hasClass('error') | this.hasClass('failure') ) return;
        
        var flash = this.data('flash');
        
        if ( this.data('timeout') ) clearTimeout(this.data('timeout'));
        this.data('timeout', setTimeout($.proxy(flash.hide, this), flash.timeout));
    }
    
    $.Flash.prototype.disable = function() {
        if ( this.data('timeout') ) clearTimeout(this.data('timeout'));
    }
    
    $.Flash.prototype.subtle = function(label, message, href) { this.message('subtle', label, message, href); };
    $.Flash.prototype.error = function(label, message, href) { this.message('error', label, message, href); };
    $.Flash.prototype.failure = function(label, message, href) { this.message('failure', label, message, href); };
    $.Flash.prototype.fail = function(label, message, href) { this.message('failure', label, message, href); };
    $.Flash.prototype.warning = function(label, message, href) { this.message('warning', label, message, href); };
    $.Flash.prototype.warn = function(label, message, href) { this.message('warning', label, message, href); };
    $.Flash.prototype.information = function(label, message, href) { this.message('information', label, message, href); };
    $.Flash.prototype.info = function(label, message, href) { this.message('information', label, message, href); };
    $.Flash.prototype.success = function(label, message, href) { this.message('success', label, message, href); };
})(jQuery);


// Hook jQuery AJAX requests and report errors back to us.
// In development mode an X-Debug-URL may be present; we open that URL in a new window if available.
$(function(){
    $(document).ajaxError(function(e, xhr, settings, error) {
        // Exit early if this is a foreign XHR request.
        if ( /^http(s)?:.*/.test(settings.url) ) return;
        
        // Ignore timeouts and cancelled requests.
        if ( xhr.status < 405 ) return;
        
        // Don't bother reporting errors to the error reporter.
        if ( /\/meta\/error$/.test(settings.url) ) return;
        
        if ( xhr.getResponseHeader('X-Debug-URL') ) {
            
            // TODO: Display an error message with link to debug page for the XHR.
            // settings.url is the requested URL, debug is the traceback URL.
        } else {
            // TODO: XHR POST
            // xhr.status,  xhr.responseText || xhr.statusText, settings.type, settings.url
        }
    });
    
    window.onerror = function(message, url, line) {
        // Ignore funky errors.
        if ( url === '' || line < 1 ) return;
        
        // Report the problem.
        $.post("url", {});
    }
});


// Generic field validation.
(function($){
    $.fn.validated = function(callback) {
        this.each(function(){
            var self = $(this),
                group = self.parents('.control-group'),
                original = self.val(),
                settings = {
                    required: self.prop('required'),
                    regex: self.attr('pattern'),  // http://html5pattern.com
                    url: self.attr('data-validate'),  // URL for validation.
                    key: self.attr('data-validate-key'),  // Key to submit for validation to the URL.  Defaults to 'value'.
                    check: self.attr('data-validate-check')  // Key in the result representing the boolean value.  True is success.
                }
    
            self.changeDelay(function(){
                var value = self.val();
    
                // Clear old validation state.
                group.removeClass('success error');
                self.nextAll('.help-inline,.help').remove();
    
                function err(msg) {
                    group.addClass('error');
                    self.parent().append('<span class="help text-error">' + msg + '</span>');
                }
    
                // Exit early if the value isn't actually different.
                if ( value === original ) return;
    
                // Ensure a required field has data.
                if ( settings.required && ( !value || value.length === 0 ) )
                    return err("A value for this field is mandatory.")
    
                if ( settings.regex ) {
                    var regex = new RegExp('^' + settings.regex + '$');
                    if ( !regex.test(value) )
                        return err("Input does not pass validation.");
                }
    
                if ( callback ) {
                    var result = callback(value);
                    if ( result ) return err(result);
                }
    
                if ( settings.url ) {
                    var data = {};
                    data[settings.key || 'value'] = value;
    
                    $.getJSON(settings.url, data, function(data){
                        if ( !data[settings.check || 'success'] )
                            return err(data.message || "Input does not pass validation.");
    
                        group.addClass('success');
                    });
    
                    return;
                }
    
                group.addClass('success');
            });
        })
    };
})(jQuery);
