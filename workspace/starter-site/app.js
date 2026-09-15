const helloButton = document.querySelector("#hello");
const message = document.querySelector("#message");
let clicks = 0;

helloButton?.addEventListener("click", () => {
  clicks += 1;
  message.textContent = clicks === 1 ? "It works! JavaScript heard your click." : `You clicked it ${clicks} times. Nice!`;
});
