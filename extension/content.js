
(async function () {
  if (window.__replayOSInstalled) return;

  let settings;

  try {
    settings = await chrome.runtime.sendMessage({
      type: "GET_SESSION"
    });
  } catch (error) {
    console.warn(
      "ReplayOS could not initialize. Refresh the page after reloading the extension."
    );
    return;
  }

  if (!settings?.recording || !settings.sessionId) return;

  window.__replayOSInstalled = true;

  function sendEvent(eventType, eventData) {
    try {
      const messagePromise = chrome.runtime.sendMessage({
        type: "RECORD_EVENT",
        event_type: eventType,
        event_data: {
          ...eventData,
          url: location.href,
          browserTime: new Date().toISOString()
        }
      });

      if (messagePromise && typeof messagePromise.catch === "function") {
        messagePromise.catch(() => {});
      }
    } catch (error) {
      if (error.message !== "Extension context invalidated.") {
        console.warn("ReplayOS could not send an event:", error.message);
      }
    }
  }

  window.addEventListener("message", event => {
    if (event.source !== window) return;

    const data = event.data;

    if (data?.source === "replayos-page-error") {
      sendEvent("javascript_error", {
        message: String(data.message || "Unknown JavaScript error").slice(0, 1000),
        sourceFile: String(data.sourceFile || "").slice(0, 500),
        line: data.line || null,
        column: data.column || null,
        errorName: String(data.errorName || "Error").slice(0, 100)
      });

      return;
    }

    if (data?.source === "replayos-page-network") {
      if (!["http_error", "network_error"].includes(data.eventType)) return;

      sendEvent(data.eventType, {
        method: String(data.method || "GET").slice(0, 20),
        requestUrl: String(data.requestUrl || "").slice(0, 1000),
        status: data.status || null,
        statusText: String(data.statusText || "").slice(0, 200),
        failureType: String(data.failureType || "").slice(0, 50),
        message: String(data.message || "").slice(0, 500)
      });
    }
  });

  sendEvent("navigation", {
    title: document.title
  });

  document.addEventListener("click", event => {
    const target = event.target;

    if (!(target instanceof Element)) return;

    const element = target.closest(
      "a, button, [role='button'], input[type='button'], input[type='submit']"
    );

    if (!element) return;

    sendEvent("click", {
      elementTag: element.tagName.toLowerCase(),
      elementText: (element.innerText || element.value || "")
        .trim()
        .slice(0, 80),
      elementId: element.id || null
    });
  }, true);

  window.addEventListener("unhandledrejection", event => {
    let reason;

    if (event.reason instanceof Error) {
      reason = `${event.reason.name}: ${event.reason.message}`;
    } else if (
      ["string", "number", "boolean"].includes(typeof event.reason)
    ) {
      reason = String(event.reason);
    } else {
      reason = "Promise rejected with a non-primitive value";
    }

    sendEvent("unhandled_promise_rejection", {
      message: reason.slice(0, 1000)
    });
  });
})();
