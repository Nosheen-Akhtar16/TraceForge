
const API = "http://127.0.0.1:8000";

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "GET_SESSION") {
    chrome.storage.local.get(["projectId", "sessionId", "recording"], data => {
      sendResponse(data);
    });
    return true;
  }

  
  if (message.type === "RECORD_EVENT") {
    chrome.storage.local.get(
      ["sessionId", "recording"],
      async data => {
        if (!data.recording || !data.sessionId) {
          sendResponse({
            ok: false,
            error: "Recording is not active"
          });
          return;
        }

        if (
          !message.event_type ||
          typeof message.event_data !== "object" ||
          message.event_data === null
        ) {
          sendResponse({
            ok: false,
            error: "Invalid event payload"
          });
          return;
        }

        try {
          const response = await fetch(
            `${API}/sessions/${encodeURIComponent(data.sessionId)}/events`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                event_type: message.event_type,
                event_data: message.event_data
              })
            }
          );

          const result = await response.json();

          if (!response.ok) {
            throw new Error(result.detail || `HTTP ${response.status}`);
          }

          sendResponse({ ok: true, event: result });
        } catch (error) {
          sendResponse({
            ok: false,
            error: error.message
          });
        }
      }
    );

    return true;
  }

});
function updateBadge(recording) {
  chrome.action.setBadgeText({
    text: recording ? "REC" : ""
  });

  chrome.action.setBadgeBackgroundColor({
    color: "#E53935"
  });
}


chrome.storage.local.get(["recording"], data => {
  updateBadge(Boolean(data.recording));
});

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName === "local" && changes.recording) {
    updateBadge(Boolean(changes.recording.newValue));
  }
});
