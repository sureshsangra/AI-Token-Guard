// Background service worker for Token Guard Extension
// Relays messages from HTTPS web pages (ChatGPT, Claude, Gemini) to localhost:8088 without Mixed Content blocking

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "LOG_EVENT") {
    fetch("http://localhost:8088/api/extension/log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request.payload)
    })
      .then((res) => res.json())
      .then((data) => {
        console.log("Logged to Token Guard dashboard:", data);
        sendResponse({ success: true, data });
      })
      .catch((err) => {
        console.warn("Could not reach Token Guard at localhost:8088:", err);
        sendResponse({ success: false, error: err.toString() });
      });
    return true; // Keep channel open for async fetch response
  }
});
