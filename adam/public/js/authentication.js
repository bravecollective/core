$(function(){
	
	// Handle checking of available usernames.
	$('#sign-up-username').changeDelay(function(){
		if ( $(this).val() === '' || $(this).val().length < 4 ) {
			$('#sign-up-username-check').removeClass('icon-ok icon-green icon-muted').addClass('icon-remove icon-red');
			return;
		}
		
		$.getJSON('/account/api/available', {name: $(this).val()}, function(data){
			console.log(data);
			if ( !data.success ) {
				$('#sign-up-username-check').removeClass('icon-ok icon-green icon-red').addClass('icon-remove icon-muted');
			} else {
				if ( data.available ) {
					$('#sign-up-username-check').removeClass('icon-remove icon-muted icon-red').addClass('icon-ok icon-green');
				} else {
					$('#sign-up-username-check').removeClass('icon-ok icon-muted icon-green').addClass('icon-remove icon-red');
				}
			}
		});
	});
	
	// Handle validating that both passwords match.
	$('#pw1,#pw2').changeDelay(function(){
		var first = $('#pw1').val(), last = $('#pw2').val();
		
		if ( first === '' || last === '' ) {
			$('#sign-up-pw-check').removeClass('icon-green icon-red').addClass('icon-muted');
		} else if ( first != last ) {
			$('#sign-up-pw-check').removeClass('icon-ok icon-green icon-muted').addClass('icon-remove icon-red');
		} else {
			$('#sign-up-pw-check').removeClass('icon-remove icon-muted icon-red').addClass('icon-ok icon-green');
		}
	});
	
	// Handle automatically loading character information.
	$('#sign-up-apik,#sign-up-apiv').changeDelay(function(){
		var first = $('#sign-up-apik').val(), last = $('#sign-up-apiv').val();
		
		if ( first === '' || last == '' ) {
			$('#api-ok').removeClass('icon-green icon-red').addClass('icon-muted');
		} else {
			$('#api-ok').removeClass('icon-muted icon-red').addClass('icon-green');
		}
		
	});

});
