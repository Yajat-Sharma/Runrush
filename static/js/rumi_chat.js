/**
 * Rumi AI - Personal Running Companion
 * Frontend Controller for RunRush
 */

(function () {
  let isSending = false;
  let lastUserMessage = "";

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    const input = document.querySelector('input[name="csrf_token"]');
    if (input && input.value) return input.value;
    if (window.userData && window.userData.csrf_token) return window.userData.csrf_token;
    return "";
  }

  function escapeHtml(text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Safe, lightweight markdown renderer for assistant responses.
   * Handles bold, italics, bullet lists, numbered lists, and paragraphs.
   */
  function renderMarkdown(text) {
    if (!text) return "";
    const escaped = escapeHtml(text);
    const lines = escaped.split("\n");
    let html = "";
    let inList = false;
    let listType = "ul";

    for (let i = 0; i < lines.length; i++) {
      let line = lines[i].trim();

      // Bold: **text** -> <strong>text</strong>
      line = line.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
      // Italic: *text* -> <em>text</em>
      line = line.replace(/(^|[^*])\*([^*]+?)\*([^*]|$)/g, "$1<em>$2</em>$3");

      // Check unordered list item: "- " or "* "
      const ulMatch = line.match(/^[-*]\s+(.*)$/);
      // Check ordered list item: "1. "
      const olMatch = line.match(/^(\d+)\.\s+(.*)$/);

      if (ulMatch) {
        if (!inList || listType !== "ul") {
          if (inList) html += `</${listType}>`;
          html += "<ul>";
          inList = true;
          listType = "ul";
        }
        html += `<li>${ulMatch[1]}</li>`;
      } else if (olMatch) {
        if (!inList || listType !== "ol") {
          if (inList) html += `</${listType}>`;
          html += "<ol>";
          inList = true;
          listType = "ol";
        }
        html += `<li>${olMatch[2]}</li>`;
      } else {
        if (inList) {
          html += `</${listType}>`;
          inList = false;
        }
        if (line.length > 0) {
          html += `<p>${line}</p>`;
        }
      }
    }
    if (inList) {
      html += `</${listType}>`;
    }
    return html;
  }

  function scrollToBottom() {
    const container = document.getElementById("rumiMessagesContainer");
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }

  function appendUserBubble(text) {
    const list = document.getElementById("rumiMessagesList");
    if (!list) return;

    // Hide welcome card once a message is posted
    const welcome = document.getElementById("rumiWelcomeCard");
    if (welcome) welcome.style.display = "none";

    const msgEl = document.createElement("div");
    msgEl.className = "rumi-msg rumi-msg-user";
    msgEl.innerHTML = `<div class="rumi-bubble">${escapeHtml(text)}</div>`;
    list.appendChild(msgEl);
    scrollToBottom();
  }

  function appendAssistantBubble(text) {
    const list = document.getElementById("rumiMessagesList");
    if (!list) return;

    const msgEl = document.createElement("div");
    msgEl.className = "rumi-msg rumi-msg-assistant";
    msgEl.innerHTML = `
      <div class="rumi-avatar-mini">⚡</div>
      <div class="rumi-bubble">${renderMarkdown(text)}</div>
    `;
    list.appendChild(msgEl);
    scrollToBottom();
  }

  function setTyping(active) {
    const indicator = document.getElementById("rumiTypingIndicator");
    const sendBtn = document.getElementById("rumiSendBtn");
    const input = document.getElementById("rumiInput");

    if (indicator) {
      indicator.style.display = active ? "flex" : "none";
    }
    if (sendBtn) {
      sendBtn.disabled = active;
    }
    if (input) {
      input.disabled = active;
    }
    if (active) scrollToBottom();
  }

  function showError(msg) {
    const banner = document.getElementById("rumiErrorBanner");
    const textEl = document.getElementById("rumiErrorText");
    if (banner && textEl) {
      textEl.textContent = msg || "Something went wrong. Please try again.";
      banner.style.display = "flex";
      scrollToBottom();
    }
  }

  function hideError() {
    const banner = document.getElementById("rumiErrorBanner");
    if (banner) {
      banner.style.display = "none";
    }
  }

  window.openRumiChat = function () {
    const modalEl = document.getElementById("rumiChatModal");
    if (!modalEl) return;
    if (typeof bootstrap !== "undefined") {
      const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
      modal.show();
    } else {
      modalEl.classList.add("show");
      modalEl.style.display = "block";
    }

    setTimeout(function () {
      const input = document.getElementById("rumiInput");
      if (input) input.focus();
      scrollToBottom();
    }, 150);
  };

  window.closeRumiChat = function () {
    const modalEl = document.getElementById("rumiChatModal");
    if (!modalEl) return;
    if (typeof bootstrap !== "undefined") {
      const modal = bootstrap.Modal.getInstance(modalEl);
      if (modal) modal.hide();
    } else {
      modalEl.classList.remove("show");
      modalEl.style.display = "none";
    }
  };

  window.autoResizeRumiInput = function (textarea) {
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 90) + "px";
  };

  window.handleRumiInputKey = function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      const form = document.getElementById("rumiChatForm");
      if (form) {
        form.dispatchEvent(new Event("submit", { cancelable: true }));
      }
    }
  };

  window.askRumiSuggested = function (chipBtn) {
    const text = chipBtn.textContent.trim();
    if (!text) return;
    const input = document.getElementById("rumiInput");
    if (input) {
      input.value = text;
      autoResizeRumiInput(input);
    }
    const form = document.getElementById("rumiChatForm");
    if (form) {
      form.dispatchEvent(new Event("submit", { cancelable: true }));
    }
  };

  window.retryLastRumiMessage = function () {
    if (!lastUserMessage) return;
    hideError();
    sendMessage(lastUserMessage);
  };

  function sendMessage(text) {
    if (isSending || !text) return;

    lastUserMessage = text;
    hideError();
    isSending = true;
    setTyping(true);

    fetch("/api/rumi/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify({ message: text }),
    })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Failed to get a response from Rumi.");
        }
        return data;
      })
      .then((data) => {
        setTyping(false);
        isSending = false;
        if (data && data.reply) {
          appendAssistantBubble(data.reply);
        } else {
          showError("Rumi didn't return an answer. Please try again.");
        }
        const input = document.getElementById("rumiInput");
        if (input) input.focus();
      })
      .catch((err) => {
        setTyping(false);
        isSending = false;
        showError(err.message || "Could not connect to Rumi.");
      });
  }

  window.submitRumiChat = function (event) {
    if (event) event.preventDefault();
    const input = document.getElementById("rumiInput");
    if (!input) return;

    const text = input.value.trim();
    if (!text || isSending) return;

    appendUserBubble(text);
    input.value = "";
    autoResizeRumiInput(input);

    sendMessage(text);
  };

  
  window.RR_ACTIONS = window.RR_ACTIONS || {};
  window.RR_ACTIONS.openRumiChat = function() { if (window.openRumiChat) window.openRumiChat(); };
  window.RR_ACTIONS.closeRumiChat = function() { if (window.closeRumiChat) window.closeRumiChat(); };
  window.RR_ACTIONS.clearRumiChat = function() { if (window.clearRumiChat) window.clearRumiChat(); };
  window.RR_ACTIONS.askRumiSuggested = function(e) { if (window.askRumiSuggested) window.askRumiSuggested(this); };
  window.RR_ACTIONS.retryLastRumiMessage = function() { if (window.retryLastRumiMessage) window.retryLastRumiMessage(); };
  window.RR_ACTIONS.submitRumiChat = function(e) { if (window.submitRumiChat) window.submitRumiChat(e); };
  window.RR_ACTIONS.handleRumiInputKey = function(e) { if (window.handleRumiInputKey) window.handleRumiInputKey(e); };
  window.RR_ACTIONS.autoResizeRumiInput = function(e) { if (window.autoResizeRumiInput) window.autoResizeRumiInput(this); };

  window.clearRumiChat = function () {
    if (isSending) return;
    hideError();

    fetch("/api/rumi/clear", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
    })
      .then((res) => res.json())
      .then(() => {
        const list = document.getElementById("rumiMessagesList");
        if (list) {
          list.innerHTML = "";
          // Recreate welcome card
          const welcome = document.createElement("div");
          welcome.className = "rumi-welcome-card";
          welcome.id = "rumiWelcomeCard";
          welcome.innerHTML = `
            <div class="rumi-welcome-icon">🏃‍♂️✨</div>
            <h6 class="rumi-welcome-heading">Hey there!</h6>
            <p class="rumi-welcome-text">
              I'm <strong>Rumi</strong>, your personal running companion. Ask me about your runs, pace, progress, goals, or anything running-related.
            </p>
            <div class="rumi-starter-prompt">Suggested questions:</div>
            <div class="rumi-starters-grid">
              <button type="button" class="rumi-starter-chip" onclick="askRumiSuggested(this)">How many kilometres did I run last month?</button>
              <button type="button" class="rumi-starter-chip" onclick="askRumiSuggested(this)">What's my average pace?</button>
              <button type="button" class="rumi-starter-chip" onclick="askRumiSuggested(this)">What's my longest run?</button>
              <button type="button" class="rumi-starter-chip" onclick="askRumiSuggested(this)">Am I improving?</button>
              <button type="button" class="rumi-starter-chip" onclick="askRumiSuggested(this)">How am I doing with my weekly goal?</button>
            </div>
          `;
          list.appendChild(welcome);
        }
      })
      .catch((err) => {
        console.error("Failed to clear chat:", err);
      });
  };
})();
