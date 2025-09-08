document.addEventListener("keypress", (event) => {
  if (event.key == "e") {
    document.querySelector("[data-edit-link]").click();
  }
});
