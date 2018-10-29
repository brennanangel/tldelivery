/* Project specific Javascript goes here. */
function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

var csrftoken = getCookie('csrftoken');

$('.results .onfleet-button.order').click(function(evt) {
    evt.preventDefault();
    var modal = $('#progress-modal');
    modal.find('.modal-title').text('Sending order to OnFleet...');
    modal.find('.modal-body').html('<div class="loader"></div>');
    modal.modal('show');
    var id = $(this).attr('data-id');
    $.ajax('/delivery/deliveries/' + id + '/onfleet', {
        method: 'POST',
        xhrFields: {
            withCredentials: true
        },
        headers: {
            "X-CSRFToken": csrftoken
        },
        success: function(data) {
            modal.find('.modal-title').text('Success');
            modal.find('.modal-body').text('Order synced to OnFleet succesfully.');
            // setTimeout(function() { $('#progress-modal').modal('hide'); }, 3000);
        },
        error: function(jqXHR, textStatus, errorThrown) {
            modal.find('.modal-title').text('Sync Failed');
            modal.find('.modal-body').html(
                '<b>' + errorThrown + ':</b> ' + jqXHR.responseText || 'Unknown Error'
            );
            // setTimeout(function() { $('#progress-modal').modal('hide'); }, 3000);
        }
    });
});

$('.onfleet-button.shift').click(function(evt) {
    evt.preventDefault();
    var modal = $('#progress-modal');
    modal.find('.modal-title').text('Sending orders to OnFleet...');
    modal.find('.modal-body').html('<div class="loader"></div>');
    modal.modal('show');
    var id = $(this).attr('data-id');
    $.ajax('/delivery/shift/' + id + '/onfleet', {
        method: 'POST',
        xhrFields: {
            withCredentials: true
        },
        headers: {
            "X-CSRFToken": csrftoken
        },
        success: function(data) {
            modal.find('.modal-title').text('Success');
            modal.find('.modal-body').text('Order list synced to OnFleet succesfully.');
            // setTimeout(function() { $('#progress-modal').modal('hide'); }, 3000);
        },
        error: function(jqXHR, textStatus, errorThrown) {
            modal.find('.modal-title').text('Sync Failed');
            modal.find('.modal-body').html(
                '<b>' + errorThrown + ':</b> ' + jqXHR.responseText || 'Unknown Error'
            );
            // setTimeout(function() { $('#progress-modal').modal('hide'); }, 3000);
        }
    });
});
