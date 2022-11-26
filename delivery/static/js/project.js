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

function makeStatusModal(title, content) {
  return `
  <div class="modal" tabindex="-1" role="dialog" id="progress-modal">
    <div class="modal-content">
      <div class="modal-header">
        <div class="modal-title">${title}</div>
      </div>
      <div class="modal-body">
        ${content}
      </div>
    </div>
  </div>`;
}

window.addEventListener("load", () => {
  const showLoadingSpinner = () => {
    django.jQuery.magnificPopup.open({
      modal: true,
      items: {
        src: '<div class="loader">',
        type: "inline",
      },
    });
    return django.jQuery.magnificPopup.instance;
  };

  django.jQuery(".results .onfleet-button.order").click(function (evt) {
    evt.preventDefault();
    const spinner = showLoadingSpinner();
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
        spinner.close();

        const modalContent = makeStatusModal(
          "Success",
          "Order synced to OnFleet succesfully."
        );
        django.jQuery.magnificPopup.open({
          items: [
            {
              src: modalContent,
              type: "inline",
            },
          ],
        });
      },
      error: function (jqXHR, textStatus, errorThrown) {
        spinner.close();

        const modalContent = makeStatusModal(
          "Sync Failed",
          "<b>" + errorThrown + ":</b> " + jqXHR.responseText || "Unknown Error"
        );
        django.jQuery.magnificPopup.open({
          items: [
            {
              src: modalContent,
              type: "inline",
            },
          ],
        });
      },
    });
  });

  django.jQuery(".onfleet-button.shift").click(function (evt) {
    evt.preventDefault();
    const spinner = showLoadingSpinner();
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
        spinner.close();
        const modalContent = makeStatusModal(
          "Success",
          "Order list synced to OnFleet succesfully."
        );
        django.jQuery.magnificPopup.open({
          items: [
            {
              src: modalContent,
              type: "inline",
            },
          ],
        });
      },
      error: function (jqXHR, textStatus, errorThrown) {
        spinner.close();

        const modalContent = makeStatusModal(
          "Sync Failed",
          "<b>" + errorThrown + ":</b> " + jqXHR.responseText || "Unknown Error"
        );
        django.jQuery.magnificPopup.open({
          items: [
            {
              src: modalContent,
              type: "inline",
            },
          ],
        });
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
