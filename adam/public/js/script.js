$(function(){
	
	// Handle drop-down menus.
	$('.dropdown-toggle').dropdown();
	
	// Prevent clicking on disabled things.
	$('body').delegate('.disabled', 'click', false);
	
	// Handle tab switching.
	$('body').delegate('dl.tabbed > dt:not(.disabled)', 'click', function(e){
		$(this).addClass('active').siblings().removeClass('active');
		return false;
	});
	
});
