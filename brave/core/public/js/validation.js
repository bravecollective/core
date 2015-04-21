$.fn.validated = function(callback){
    this.each(function(){
        var self = $(this),
            group = self.parents('.control-group'),
            original = self.val(),
            settings = {
                required: self.prop('required'),
                regex: self.attr('pattern'),  // http://html5pattern.com
                url: self.attr('datavalidate'),  // URL for validation.
                key: self.attr('datavalidatekey'),  // Key to submit for validation to the URL.  Defaults to 'value'.
                check: self.attr('datavalidatecheck')  // Key in the result representing the boolean value.  True is success.
            }
        
        self.changeDelay(function(){
            self.trigger('initialChangeDelay');
            var value = self.val();
            
            // Clear old validation state.
            self.removeClass('success error regex validation callback required');
            group.removeClass('success error regex validation callback required');
//            self.nextAll('.help-inline,.help').remove();
            
            function err(msg, type) {
                self.addClass('error');
                group.addClass('error');
                
                self.addClass(type);
                group.addClass(type);
                
                self.attr("errMsg", msg);
                
                self.trigger('validation');
//                self.parent().append('<span class="help-inline">' + msg + '</span>');
            }
            
            // Ensure a required field has data.
            if ( settings.required && ( !value || value.length === 0 ) )
                return err("Required.", "required");
            
            // Exit early if the value isn't actually different.
            if ( value === original ) return;
            
            if ( settings.regex ) {
                var regex = new RegExp('^' + settings.regex + '$');
                if ( !regex.test(value) )
                    return err("Invalid regex.", "regex");
            }
            
            if ( callback ) {
                var result = callback(value);
                if ( result ) return err(result, "callback");
            }
            
            if ( settings.url ) {
                var data = {};
                data[settings.key || 'value'] = value;
                
                $.post(settings.url, data, function(data){
                    if ( !data[settings.check || 'success'] )
                        return err(data.message || "Invalid validation.", "validation");
                    
                    self.addClass('success');
                    group.addClass('success');
                }, "json");
                
                self.trigger('validation');
                return;
            }
            
            self.addClass('success');
            group.addClass('success');
            self.trigger('validation');
        });
    })
};
