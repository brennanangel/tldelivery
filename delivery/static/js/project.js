/* Project specific Javascript goes here. */
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (var i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      // Does this cookie string begin with the name we want?
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

const csrftoken = getCookie("csrftoken");

window.addEventListener("load", () => {
  django.jQuery(".results .onfleet-button.order").click(function (evt) {
    evt.preventDefault();
    const modal = django.jQuery("#progress-modal");
    modal.find(".modal-title").text("Sending order to OnFleet...");
    modal.find(".modal-body").html('<div class="loader"></div>');
    modal.modal("show");
    const id = django.jQuery(this).attr("data-id");
    django.jQuery.ajax("/delivery/deliveries/" + id + "/onfleet", {
      method: "POST",
      xhrFields: {
        withCredentials: true,
      },
      headers: {
        "X-CSRFToken": csrftoken,
      },
      success: function (data) {
        modal.find(".modal-title").text("Success");
        modal.find(".modal-body").text("Order synced to OnFleet succesfully.");
        // setTimeout(function() { django.jQuery('#progress-modal').modal('hide'); }, 3000);
      },
      error: function (jqXHR, textStatus, errorThrown) {
        modal.find(".modal-title").text("Sync Failed");
        modal
          .find(".modal-body")
          .html(
            "<b>" + errorThrown + ":</b> " + jqXHR.responseText ||
              "Unknown Error"
          );
        // setTimeout(function() { django.jQuery('#progress-modal').modal('hide'); }, 3000);
      },
    });
  });

  django.jQuery(".onfleet-button.shift").click(function (evt) {
    evt.preventDefault();
    const modal = django.jQuery("#progress-modal");
    modal.find(".modal-title").text("Sending orders to OnFleet...");
    modal.find(".modal-body").html('<div class="loader"></div>');
    modal.modal("show");
    const id = django.jQuery(this).attr("data-id");
    django.jQuery.ajax("/delivery/shift/" + id + "/onfleet", {
      method: "POST",
      xhrFields: {
        withCredentials: true,
      },
      headers: {
        "X-CSRFToken": csrftoken,
      },
      success: function (data) {
        modal.find(".modal-title").text("Success");
        modal
          .find(".modal-body")
          .text("Order list synced to OnFleet succesfully.");
        // setTimeout(function() { django.jQuery('#progress-modal').modal('hide'); }, 3000);
      },
      error: function (jqXHR, textStatus, errorThrown) {
        modal.find(".modal-title").text("Sync Failed");
        modal
          .find(".modal-body")
          .html(
            "<b>" + errorThrown + ":</b> " + jqXHR.responseText ||
              "Unknown Error"
          );
        // setTimeout(function() { django.jQuery('#progress-modal').modal('hide'); }, 3000);
      },
    });
  });

  django.jQuery(".apply-date-filter").click(function (evt) {
    evt.preventDefault();
    const searchParams = new URLSearchParams(window.location.search);
    searchParams.set("date", django.jQuery(evt.target).siblings("input").val());
    window.location.search = searchParams.toString();
  });
});
