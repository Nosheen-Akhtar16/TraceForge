
const API = "http://127.0.0.1:8000";

const projectInput = document.getElementById("projectId");
const sessionInput = document.getElementById("sessionId");
const status = document.getElementById("status");

// Restore the saved state when the popup opens.
chrome.storage.local.get(
  ["projectId", "sessionId", "recording"],
  data => {
    projectInput.value = data.projectId || "";
    sessionInput.value = data.sessionId || "";

    status.textContent = data.recording
      ? "Recording is active."
      : "Recording stopped.";
  }
);

document.getElementById("start").addEventListener("click", async () => {
  const projectId = projectInput.value.trim();
  const sessionId = sessionInput.value.trim();

  if (!projectId || !sessionId) {
    status.textContent = "Enter both IDs first.";
    return;
  }

  try {
    status.textContent = "Checking project and session...";

    const response = await fetch(
      `${API}/projects/${encodeURIComponent(projectId)}/sessions`
    );

    if (!response.ok) {
      throw new Error("Could not find project. Check the Project ID.");
    }

    const data = await response.json();

    const belongsToProject = data.sessions.some(
      session => session.id === sessionId
    );

    if (!belongsToProject) {
      throw new Error("This session does not belong to that project.");
    }

    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true
    });

    if (!tab?.id || !tab.url?.startsWith("http")) {
      throw new Error("Open a normal HTTP or HTTPS website first.");
    }

    await chrome.storage.local.set({
      projectId,
      sessionId,
      recording: true
    });

    // Install the content script in the active tab.
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["content.js"]
    });

    // Install page-level error and network instrumentation.
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      world: "MAIN",
      func: () => {
        if (window.__replayOSMainInstrumentationInstalled) return;

        window.__replayOSMainInstrumentationInstalled = true;

        function safeURL(rawURL) {
          try {
            const parsed = new URL(rawURL, location.href);

            // Do not record query parameters or URL fragments.
            return parsed.origin + parsed.pathname;
          } catch {
            return "";
          }
        }

        function postPageError(details) {
          window.postMessage(
            {
              source: "replayos-page-error",
              ...details
            },
            location.origin
          );
        }

        function postNetworkEvent(details) {
          window.postMessage(
            {
              source: "replayos-page-network",
              ...details
            },
            location.origin
          );
        }

        // Capture uncaught JavaScript errors.
        window.addEventListener("error", event => {
          if (!event.message) return;

          postPageError({
            message: String(event.message).slice(0, 1000),
            sourceFile: String(event.filename || "").slice(0, 500),
            line: event.lineno || null,
            column: event.colno || null,
            errorName: event.error?.name || "Error"
          });
        });

        // Capture unhandled Promise rejections in the page.
        window.addEventListener("unhandledrejection", event => {
          const reason = event.reason;

          const message = reason instanceof Error
            ? `${reason.name}: ${reason.message}`
            : typeof reason === "string"
              ? reason
              : "Unhandled Promise rejection";

          postPageError({
            message: String(message).slice(0, 1000),
            sourceFile: "",
            line: null,
            column: null,
            errorName: "UnhandledPromiseRejection"
          });
        });

        // Intercept fetch requests without changing their normal result.
        const originalFetch = window.fetch;

        window.fetch = function (...args) {
          const input = args[0];
          const options = args[1] || {};

          const rawURL =
            typeof input === "string"
              ? input
              : input instanceof URL
                ? input.href
                : input?.url || "";

          const method = String(
            options.method || input?.method || "GET"
          ).toUpperCase();

          const requestUrl = safeURL(rawURL);

          return originalFetch.apply(this, args).then(
            response => {
              if (!response.ok) {
                postNetworkEvent({
                  eventType: "http_error",
                  method,
                  requestUrl,
                  status: response.status,
                  statusText: response.statusText || "",
                  failureType: "http_response",
                  message: `HTTP ${response.status}`
                });
              }

              return response;
            },
            error => {
              postNetworkEvent({
                eventType: "network_error",
                method,
                requestUrl,
                status: null,
                statusText: "",
                failureType: "fetch_failed",
                message: String(error?.message || "Fetch failed").slice(0, 500)
              });

              throw error;
            }
          );
        };

        // Track XMLHttpRequest metadata.
        const xhrPrototype = XMLHttpRequest.prototype;
        const originalOpen = xhrPrototype.open;
        const originalSend = xhrPrototype.send;

        xhrPrototype.open = function (method, url, ...rest) {
          this.__replayOSRequest = {
            method: String(method || "GET").toUpperCase(),
            requestUrl: safeURL(String(url))
          };

          return originalOpen.call(this, method, url, ...rest);
        };

        xhrPrototype.send = function (...args) {
          const xhr = this;
          const request = xhr.__replayOSRequest || {
            method: "GET",
            requestUrl: ""
          };

          let failureType = "";

          xhr.addEventListener("error", () => {
            failureType = "xhr_network_error";
          }, { once: true });

          xhr.addEventListener("timeout", () => {
            failureType = "xhr_timeout";
          }, { once: true });

          xhr.addEventListener("abort", () => {
            failureType = "xhr_aborted";
          }, { once: true });

          xhr.addEventListener("loadend", () => {
            if (xhr.status >= 400) {
              postNetworkEvent({
                eventType: "http_error",
                ...request,
                status: xhr.status,
                statusText: xhr.statusText || "",
                failureType: "http_response",
                message: `HTTP ${xhr.status}`
              });
            } else if (xhr.status === 0 && failureType) {
              postNetworkEvent({
                eventType: "network_error",
                ...request,
                status: null,
                statusText: "",
                failureType,
                message: failureType
              });
            }
          }, { once: true });

          return originalSend.apply(xhr, args);
        };
      }
    });

    status.textContent = "Recording is active on this tab.";
  } catch (error) {
    status.textContent = `Error: ${error.message}`;
  }
});

document.getElementById("stop").addEventListener("click", async () => {
  await chrome.storage.local.set({ recording: false });
  status.textContent = "Recording stopped.";
});
