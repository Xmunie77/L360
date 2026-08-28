import React from "react";
import ReactDOM from "react-dom/client";
import "./theme.css";
import { App } from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// Registers the app-shell service worker (see public/sw.js) so the app is
// installable and can reload while briefly offline. Never caches /api/
// calls — booking/billing data always comes from the network.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // Non-fatal — the app works fine without it, just not installable.
    });
  });
}
