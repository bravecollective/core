// This file contians the globally applied JavaScript (generally jQuery) functions.

$(function(){

	// Allow links to open modal dialogs pulled from server-side resources.
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

			// Display the dialog.
			$('#modal').modal('show');
		}});
	});

	// Prevent access of disabled elements.
	$('body').on('click', '.disabled', function(e) {
		e.preventDefault();
	});

	// Hook CSRF token support into jQuery AJAX.
	
	// $(document).ajaxSend(function(event, xhr, settings) {
	// 	// Exit early if this is a foreign XHR request.
	// 	if ( /^http(s)?:.*/.test(settings.url) )
	// 		return;
	//
	// 	var token = $.cookie('csrf');
	// 	if ( ! token ) return;
	//
	// 	xhr.setRequestHeader('X-CSRF', token);
	// });

	// Disable moving-to-top for pure hash links.
	$(document).on('click', 'a[href="#"][data-top!=true]', function(e){
		e.preventDefault();
	});

	// Tooltips
	$('[rel="tooltip"],[data-rel="tooltip"]').tooltip({delay: 200});

	// Popovers
	$('[rel="popover"],[data-rel="popover"]').popover();

});