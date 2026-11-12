// Token Guard Content Script for ChatGPT, Claude.ai, and Gemini Web
(function () {
  console.log("🛡️ [Token Guard] Content script loaded on:", window.location.hostname);

  let totalSessionTokensSaved = 0;

  function estimateTokens(text) {
    if (!text) return 0;
    const words = text.trim().split(/\s+/).filter(Boolean).length;
    const chars = text.length;
    return Math.max(1, Math.round((words * 1.3 + chars / 4) / 2));
  }

  function prunePromptText(text) {
    if (!text || text.length < 5) return text;

    let pruned = text.replace(/\r\n/g, "\n");
    pruned = pruned.replace(/\n{3,}/g, "\n\n");
    pruned = pruned.replace(/[ \t]{2,}/g, " ");

    const fluffPatterns = [
      /\b(as an ai language model|as an ai assistant),?\s*/gi,
      /\b(please note that|it is important to note that|keep in mind that)\s*/gi,
      /\b(feel free to (ask|reach out|let me know))\b/gi,
      /\b(without further ado|needless to say),?\s*/gi
    ];
    for (const p of fluffPatterns) {
      pruned = pruned.replace(p, "");
    }

    pruned = pruned.replace(/(\n)[ \t]*[-*_]{3,}[ \t]*(\n)/g, "$1---$2");
    return pruned.trim();
  }

  function sendLogToBackground(payload) {
    try {
      chrome.runtime.sendMessage({ type: "LOG_EVENT", payload: payload }, (res) => {
        if (chrome.runtime.lastError) {
          console.warn("[Token Guard] Extension background error:", chrome.runtime.lastError.message);
        } else {
          console.log("[Token Guard] Successfully logged to dashboard:", res);
        }
      });
    } catch (err) {
      console.warn("[Token Guard] Failed to message background worker:", err);
    }
  }

  function ensureWidget() {
    let widget = document.getElementById("token-guard-widget");
    if (!widget) {
      widget = document.createElement("div");
      widget.id = "token-guard-widget";
      widget.innerHTML = `
        <div style="display:flex; align-items:center; gap:8px;">
          <span style="font-size:14px;">🛡️</span>
          <span id="tg-widget-text" style="color:#00f0ff; font-weight:600;">Token Guard Active</span>
          <button id="tg-clean-btn" style="background:#00f0ff; color:#0b0f17; border:none; border-radius:4px; padding:3px 8px; font-size:10px; font-weight:bold; cursor:pointer; margin-left:4px;">⚡ Clean</button>
        </div>
      `;
      widget.style.position = "fixed";
      widget.style.bottom = "24px";
      widget.style.right = "24px";
      widget.style.zIndex = "999999999";
      widget.style.background = "#141b27";
      widget.style.color = "#e2e8f0";
      widget.style.border = "1px solid #00f0ff";
      widget.style.borderRadius = "20px";
      widget.style.padding = "7px 15px";
      widget.style.fontFamily = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
      widget.style.fontSize = "12px";
      widget.style.boxShadow = "0 6px 20px rgba(0,0,0,0.6)";
      widget.style.transition = "all 0.3s ease";
      document.body.appendChild(widget);

      const btn = document.getElementById("tg-clean-btn");
      if (btn) {
        btn.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          processOptimization(true);
        });
      }
    }
    return widget;
  }

  function flashWidget(message, color = "#00e676") {
    ensureWidget();
    const txt = document.getElementById("tg-widget-text");
    if (txt) {
      txt.textContent = message;
      txt.style.color = color;
      setTimeout(() => {
        txt.textContent = totalSessionTokensSaved > 0 
          ? `Token Guard: ${totalSessionTokensSaved} tokens saved` 
          : "Token Guard Active";
        txt.style.color = "#00f0ff";
      }, 4000);
    }
  }

  function findPromptInput() {
    // 1. ChatGPT
    const gpt = document.querySelector("#prompt-textarea") || document.querySelector('div[contenteditable="true"]#prompt-textarea');
    if (gpt) return gpt;

    // 2. Claude.ai
    const claude = document.querySelector(".ProseMirror") || document.querySelector('fieldset div[contenteditable="true"]');
    if (claude) return claude;

    // 3. Gemini
    const gemini = document.querySelector("rich-textarea div[contenteditable='true']") || document.querySelector(".ql-editor");
    if (gemini) return gemini;

    // 4. General fallbacks
    const activeEl = document.activeElement;
    if (activeEl && (activeEl.getAttribute("contenteditable") === "true" || activeEl.tagName === "TEXTAREA")) {
      return activeEl;
    }

    return document.querySelector('div[contenteditable="true"]') || document.querySelector("textarea");
  }

  function readInputText(el) {
    if (!el) return "";
    if (el.tagName === "TEXTAREA" || el.tagName === "INPUT") {
      return el.value;
    }
    return el.innerText || el.textContent || "";
  }

  function writeInputText(el, text) {
    if (!el) return;
    if (el.tagName === "TEXTAREA" || el.tagName === "INPUT") {
      el.value = text;
      el.dispatchEvent(new Event("input", { bubbles: true }));
    } else {
      el.innerText = text;
      el.dispatchEvent(new Event("input", { bubbles: true }));
    }
  }

  function processOptimization(isManual = false) {
    const el = findPromptInput();
    if (!el) {
      if (isManual) flashWidget("Prompt box not detected", "#ff5252");
      return;
    }

    const raw = readInputText(el);
    if (!raw || raw.trim().length === 0) {
      if (isManual) flashWidget("Type a prompt first", "#ff9800");
      return;
    }

    const origTokens = estimateTokens(raw);
    const pruned = prunePromptText(raw);
    const optTokens = estimateTokens(pruned);
    const saved = Math.max(0, origTokens - optTokens);
    const pct = origTokens > 0 ? Math.round((saved / origTokens) * 100) : 0;

    // If changes were made, update the input box
    if (saved > 0) {
      writeInputText(el, pruned);
      totalSessionTokensSaved += saved;
      flashWidget(`-${pct}% Saved (${saved} tokens)`, "#00e676");
    } else {
      if (isManual) {
        flashWidget("Prompt already compact!", "#00f0ff");
      }
    }

    // Determine platform name
    let host = window.location.hostname;
    let sourceName = "ChatGPT Web";
    if (host.includes("claude")) sourceName = "Claude.ai Web";
    if (host.includes("gemini") || host.includes("google")) sourceName = "Gemini Web";

    // ALWAYS log the interaction so user sees it in the dashboard!
    sendLogToBackground({
      source: sourceName,
      original_tokens: origTokens,
      optimized_tokens: optTokens,
      tokens_saved: saved,
      savings_percentage: pct,
      cache_status: saved > 0 ? "browser_prune" : "verified_compact"
    });
  }

  // Inject widget after page load
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => setTimeout(ensureWidget, 800));
  } else {
    setTimeout(ensureWidget, 800);
  }
  // Extra retry for dynamic SPAs
  setTimeout(ensureWidget, 2500);

  // Intercept Enter key
  document.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      processOptimization(false);
    }
  }, true);

  // Intercept Send button clicks
  document.addEventListener("click", function (e) {
    const btn = e.target.closest("button");
    if (!btn) return;
    const aria = (btn.getAttribute("aria-label") || "").toLowerCase();
    const testid = (btn.getAttribute("data-testid") || "").toLowerCase();
    const txt = (btn.innerText || "").toLowerCase();
    if (aria.includes("send") || testid.includes("send") || txt.includes("send") || aria.includes("submit")) {
      processOptimization(false);
    }
  }, true);

})();
