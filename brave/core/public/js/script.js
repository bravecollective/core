// This file contians the globally applied JavaScript (generally jQuery) functions.

// Console.* Polyfill
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

$(function(){

    // Retina-ize the EVE images.
    if ( window.devicePixelRatio >= 2 ) {
        console.log("retina");
        
        $('img[src*="//image.eveonline.com/"]').each(function(index, element) {
            var self = $(element),
                current = self.attr('src'),
                size = current.match(/_(\d+)\.\w{3,4}/);

            if ( ! size ) return;
            size = parseInt(size[1]);

            self.attr('src', self.attr('src').replace(/(.+_)(\d+)(\.\w{3,4})$/, "$1" + (size*2) + "$3"));
        });
    }
                                                                                                                                    
    // Add associative array seriailzation.
    $.fn.serializeAssoc = function() {
        var o = {};
        var a = this.serializeArray();
        $.each(a, function() {
            if (o[this.name] !== undefined) {
                if (!o[this.name].push) {
                    o[this.name] = [o[this.name]];
                }
                o[this.name].push(this.value || '');
            } else {
                o[this.name] = this.value || '';
            }
        });
        return o;
    };
    
    // Allow links to open modal dialogs pulled from server-side resources.
    // Also dynamically fires a callback for the relevant popup, if data-trigger is set.
    $('body').on('click', 'a[rel=modal]', function(e){
        var self = $(this);
        
        // Prevent the click from registering.
        e.preventDefault();
        
        // Remove any existing modal content.
        $('#modal').remove();
        
        // Request the page.
        $.ajax({url: self.attr('href'), dataType: 'html', success: function(data, status, jqXHR) {
            // Construct the DOM for the dialog.
            $('<div></div>').html(data).children().attr('id', 'modal').addClass('modal hide fade').appendTo('body');

            // attach events
            if ( self.attr('data-trigger') )
            {
                $('#modal').on('shown', function(){
                    $(document).trigger('popup-' + self.attr('data-trigger'));
                });
            }

            // Display the dialog.
            $('#modal').modal('show');
        }});
    });

    // Prevent access of disabled elements.
    $('body').on('click', '.disabled', function(e) {
        e.preventDefault();
    });

    // Disable moving-to-top for pure hash links.
    $(document).on('click', 'a[href="#"][data-top!=true]', function(e){ e.preventDefault(); });
    
    // Relative Times
    $('time.relative').timeago();
    
    // Tooltips
    $('[rel="tooltip"],[data-rel="tooltip"]').tooltip({delay: 200});

    // Popovers
    $('[rel="popover"],[data-rel="popover"]').popover();
    
    // A little CSS helper.
    // Note to other readers: we theorize this exists because the igb does not understand :first-child.
    $('tr:first-child').addClass('first');
    
    // Automatically destroy all modal dialogs.  Keep the DOM clean.
    $('body').on('hidden', '#modal', function(){ $('#modal').remove(); });

    // Hook CSRF token support into jQuery AJAX.
    $(document).ajaxSend(function(event, xhr, settings) {
        // Exit early if this is a foreign XHR request.
        var parser = document.createElement('a');
        parser.href = settings.url;
        if ( parser.protocol != window.location.protocol ||
             parser.host != window.location.host )
            return;
        
        var token = $.cookie('csrf');
        if ( ! token ) return;
        
        xhr.setRequestHeader('X-CSRF', token);
    });

    function ISODateString(d) {
        function pad(n){ return n < 10 ? '0' + n : n }

        return d.getUTCFullYear()+'-'
            + pad(d.getUTCMonth()+1)+'-'
            + pad(d.getUTCDate())+'T'
            + pad(d.getUTCHours())+':'
            + pad(d.getUTCMinutes())+':'
            + pad(d.getUTCSeconds())+'Z';
    }
    
    function confirm(title, content, success, callback) {
        if ( ! success.hasOwnProperty('label') )
            success = {label: success, kind: 'btn-primary'};

        var modal = $(
        '<div id="modal" class="modal hide fade">' +
            '<div class="modal-header">' +
                '<button type="button" class="close" data-dismiss="modal" aria-hidden="true">&times;</button>' +
                '<h3>' + title + '</h3>' +
            '</div>' +
            '<div class="modal-body">' + content + '</div>' +
            '<div class="modal-footer">' +
                '<a href="#" class="btn" data-dismiss="modal">Cancel</a>' +
                '<a href="#" class="success btn ' + success.kind + '">' + success.label + '</a>' +
            '</div>' +
        '</div>').appendTo('body');

        $('#modal .btn.success').on('click', function(e) {
            if ( callback() )
                return;

            e.preventDefault();
            $('#modal').modal('hide')
        });

        $('#modal').on('hidden', function() {
            $('#modal').remove();
        }).modal();
    }
    
    // Override the default confirmation dialog.
    window.confirm = confirm;
    
    // Display notices (errors, warning, informational, etc.)
    $.alert = function(level, title, message, target) {
        if ( target === undefined ) target = '.content .pad-wrapper';
        
        $('.alert').remove();
        $('<div class="alert alert-' + level + '"><button type="button" class="close" data-dismiss="alert">×</button><strong>' + title + ':</strong> ' + message + '</div>').insertBeore(target);
    };
    
    // Hook jQuery AJAX requests and report errors back to us.
    // In development mode an X-Debug-URL may be present; we open that URL in a new window if available.
    $(document).ajaxError(function(e, xhr, settings, error) {
        // Exit early if this is a foreign XHR request.
        if ( /^http(s)?:.*/.test(settings.url) )
            return;
        
        // Ignore timeouts and cancelled requests.
        if ( xhr.status < 405 )
            return;
        
        // Don't bother reporting errors to the error reporter.
        if ( /\/meta\/error$/.test(settings.url) )
            return;
        
        var debug = xhr.getResponseHeader('X-Debug-URL');
        if ( debug ) {
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
        // $.post("url", {});
    }
    
    
    // Handle generic modal AJAX-submitted forms.
    $(document).off('popup-genericform').on('popup-genericform', function(){
        $('#modal .validate').validated();
        
        $('#modal form').off('submit').submit(function(e){
            var self = $(this);
            $.post(self.attr('action'), self.serialize(), function(data){
                if ( data && data.success ) {
                    window.location = data.hasOwnProperty('location') ? data.location : window.location;
                    $('#modal').modal('hide');
                }
            });
            e.preventDefault();
            return false;
        });

        $('#set-save').off().on('click', function(e){
            $('#modal form').submit();
            e.preventDefault();
            return false;
        });

    });
    
});
