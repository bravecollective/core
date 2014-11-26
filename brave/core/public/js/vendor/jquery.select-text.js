$(function(){
        // Select Text jQuery Plugin
        (function(jQuery){
            jQuery.fn.selectText = function(){
                var doc = document
            , element = this[0]
            , range, selection
            ;
        if (doc.body.createTextRange) {
            range = document.body.createTextRange();
            range.moveToElementText(element);
            range.select();
        } else if (window.getSelection) {
            selection = window.getSelection();
            range = document.createRange();
            range.selectNodeContents(element);
            selection.removeAllRanges();
            selection.addRange(range);
        }
            };
        })( this.jQuery );
});
