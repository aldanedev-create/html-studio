const surpriseButton = document.querySelector("#surprise");
const page = document.querySelector(".demo-page");
const message = document.querySelector("#message");
const colors = ["#fff1c9", "#e8dcff", "#d7f8ee", "#ffdbea"];
let colorIndex = 0;

surpriseButton?.addEventListener("click", () => {
  colorIndex = (colorIndex + 1) % colors.length;
  if (page) page.style.setProperty("--surprise-color", colors[colorIndex]);
  if (message) message.textContent = "Surprise! You changed the page with JavaScript.";
});
