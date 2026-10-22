// path: ui/panel.js
// Frontend logic for Private Personal Assistant (Text Chat, Memory, PDF/CSV Table Exports & Morning Brief)

const API = "";
let pendingConfirmation = null;
let chatHistory = [];

// DOM elements
let chatEl, form, input, modelSelect, modelBadge, costCounter;
let confirmationEl, confirmText, confirmYes, confirmNo;
let memoriesPanel, memoriesList, morningBriefBtn;

function getElements() {
    chatEl = document.getElementById("chat");
    form = document.getElementById("chat-form");
    input = document.getElementById("input");
    modelSelect = document.getElementById("model-select");
    modelBadge = document.getElementById("model-badge");
    costCounter = document.getElementById("cost-counter");
    confirmationEl = document.getElementById("confirmation");
    confirmText = document.getElementById("confirm-text");
    confirmYes = document.getElementById("confirm-yes");
    confirmNo = document.getElementById("confirm-no");
    memoriesPanel = document.getElementById("memories-panel");
    memoriesList = document.getElementById("memories-list");
    morningBriefBtn = document.getElementById("morning-brief-btn");
}

// Escape HTML
function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

// Format message content: parses markdown (tables, lists, bold) for assistant/system
function formatContent(role, content) {
    if (!content) return "";
    if (role === "assistant" || role === "system") {
        if (window.marked && typeof window.marked.parse === "function") {
            try {
                return window.marked.parse(content);
            } catch (err) {
                console.warn("Markdown parse error, falling back to text:", err);
                return escapeHtml(content);
            }
        }
    }
    return escapeHtml(content);
}

// Export clean, high-resolution PDF document from table or data
async function downloadTablePdf(table, button) {
    const span = button ? button.querySelector("span") : null;
    const originalText = span ? span.textContent : "";
    if (span) span.textContent = "Generating PDF...";
    if (button) button.disabled = true;

    try {
        const now = new Date();
        const dateStr = now.toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" });
        const timeStr = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

        // Build clean, light-mode high-contrast export container optimized for A4 document
        const exportContainer = document.createElement("div");
        exportContainer.className = "pdf-export-container";
        exportContainer.style.background = "#ffffff";
        exportContainer.style.color = "#111111";
        exportContainer.style.padding = "24px 28px";
        exportContainer.style.fontFamily = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";
        exportContainer.style.width = "720px";
        exportContainer.style.margin = "0 auto";

        const headerHtml = `
            <div style="border-bottom: 2px solid #76b900; padding-bottom: 12px; margin-bottom: 18px; display: flex; justify-content: space-between; align-items: flex-end;">
                <div>
                    <h2 style="margin: 0; font-size: 20px; color: #171a21; font-weight: 700;">Private Personal Assistant</h2>
                    <p style="margin: 4px 0 0 0; font-size: 13px; color: #555;">Schedule &amp; Timetable Document</p>
                </div>
                <div style="text-align: right; font-size: 11px; color: #666; font-family: monospace;">
                    <div>${dateStr}</div>
                    <div>${timeStr}</div>
                </div>
            </div>
        `;

        const clonedTable = table.cloneNode(true);
        clonedTable.style.width = "100%";
        clonedTable.style.borderCollapse = "collapse";
        clonedTable.style.marginTop = "8px";
        clonedTable.style.fontSize = "13px";
        clonedTable.style.color = "#111111";

        clonedTable.querySelectorAll("th").forEach(th => {
            th.style.background = "#f4f6f8";
            th.style.color = "#0f1115";
            th.style.fontWeight = "600";
            th.style.padding = "10px 12px";
            th.style.border = "1px solid #d0d7de";
            th.style.textAlign = "left";
        });

        clonedTable.querySelectorAll("td").forEach(td => {
            td.style.padding = "9px 12px";
            td.style.border = "1px solid #d0d7de";
            td.style.textAlign = "left";
        });

        clonedTable.querySelectorAll("tr").forEach((tr, i) => {
            if (i % 2 === 0 && i !== 0) {
                tr.style.background = "#fafbfc";
            }
        });

        const footerHtml = `
            <div style="margin-top: 22px; border-top: 1px solid #e1e4e8; padding-top: 10px; font-size: 11px; color: #888; display: flex; justify-content: space-between;">
                <span>Verified Private Local Memory Document</span>
                <span>Page 1 of 1</span>
            </div>
        `;

        exportContainer.innerHTML = headerHtml;
        exportContainer.appendChild(clonedTable);
        exportContainer.insertAdjacentHTML("beforeend", footerHtml);

        // Position offscreen temporarily
        exportContainer.style.position = "fixed";
        exportContainer.style.left = "-9999px";
        exportContainer.style.top = "0";
        document.body.appendChild(exportContainer);

        const filename = `timetable_${now.getFullYear()}${(now.getMonth()+1).toString().padStart(2,'0')}${now.getDate().toString().padStart(2,'0')}.pdf`;

        if (window.html2pdf) {
            const opt = {
                margin: [10, 10, 10, 10],
                filename: filename,
                image: { type: "jpeg", quality: 0.98 },
                html2canvas: { scale: 2, useCORS: true, logging: false },
                jsPDF: { unit: "mm", format: "a4", orientation: "portrait" }
            };

            await window.html2pdf().set(opt).from(exportContainer).save();
            document.body.removeChild(exportContainer);

            if (span) {
                span.textContent = "✓ PDF Saved!";
                button.classList.add("success");
                setTimeout(() => {
                    span.textContent = originalText;
                    button.classList.remove("success");
                }, 2000);
            }
        } else {
            // Fallback: Invisible iframe native print-to-pdf dialog
            const iframe = document.createElement("iframe");
            iframe.style.position = "fixed";
            iframe.style.right = "0";
            iframe.style.bottom = "0";
            iframe.style.width = "0";
            iframe.style.height = "0";
            iframe.style.border = "0";
            document.body.appendChild(iframe);

            const doc = iframe.contentWindow.document;
            doc.open();
            doc.write(`
                <!DOCTYPE html>
                <html>
                <head>
                    <title>${filename}</title>
                    <style>
                        body { margin: 0; padding: 20px; font-family: system-ui, -apple-system, sans-serif; }
                        @media print { body { padding: 0; } }
                    </style>
                </head>
                <body>${exportContainer.innerHTML}</body>
                </html>
            `);
            doc.close();
            document.body.removeChild(exportContainer);

            setTimeout(() => {
                iframe.contentWindow.focus();
                iframe.contentWindow.print();
                setTimeout(() => document.body.removeChild(iframe), 1500);
            }, 300);
        }
    } catch (err) {
        console.error("PDF generation error:", err);
        alert(`Could not generate PDF: ${err.message}`);
    } finally {
        if (button) button.disabled = false;
        if (span && !button.classList.contains("success")) {
            span.textContent = originalText;
        }
    }
}

// Attach 1-Click Copy, Download CSV, and Download PDF actions to every rendered table
function attachTableActions(container) {
    if (!container) return;
    const tables = container.querySelectorAll("table");
    tables.forEach((table) => {
        if (table.parentElement.classList.contains("table-wrapper")) return;

        const wrapper = document.createElement("div");
        wrapper.className = "table-wrapper";

        const actions = document.createElement("div");
        actions.className = "table-actions";

        const copyBtn = document.createElement("button");
        copyBtn.className = "table-btn copy-btn";
        copyBtn.type = "button";
        copyBtn.title = "Copy table to clipboard (paste into Excel, Sheets, or Notion)";
        copyBtn.innerHTML = `
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </svg>
            <span>Copy Table</span>
        `;

        const csvBtn = document.createElement("button");
        csvBtn.className = "table-btn csv-btn";
        csvBtn.type = "button";
        csvBtn.title = "Download table as .CSV spreadsheet";
        csvBtn.innerHTML = `
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            <span>Download CSV</span>
        `;

        const pdfBtn = document.createElement("button");
        pdfBtn.className = "table-btn pdf-btn";
        pdfBtn.type = "button";
        pdfBtn.title = "Download formatted table as PDF document";
        pdfBtn.innerHTML = `
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
            <span>Download PDF</span>
        `;

        actions.appendChild(copyBtn);
        actions.appendChild(csvBtn);
        actions.appendChild(pdfBtn);

        table.parentNode.insertBefore(wrapper, table);
        wrapper.appendChild(actions);
        wrapper.appendChild(table);

        // Copy handler (TSV format for direct paste into Excel / Sheets / Notion)
        copyBtn.addEventListener("click", async () => {
            try {
                const rows = Array.from(table.querySelectorAll("tr"));
                const tsv = rows.map(r => {
                    const cells = Array.from(r.querySelectorAll("th, td"));
                    return cells.map(c => c.textContent.trim().replace(/\t/g, " ")).join("\t");
                }).join("\n");

                await navigator.clipboard.writeText(tsv);
                const span = copyBtn.querySelector("span");
                const originalText = span.textContent;
                span.textContent = "✓ Copied!";
                copyBtn.classList.add("success");
                setTimeout(() => {
                    span.textContent = originalText;
                    copyBtn.classList.remove("success");
                }, 2000);
            } catch (err) {
                console.warn("Failed to copy table:", err);
            }
        });

        // Download CSV handler
        csvBtn.addEventListener("click", () => {
            try {
                const rows = Array.from(table.querySelectorAll("tr"));
                const csvRows = rows.map(r => {
                    const cells = Array.from(r.querySelectorAll("th, td"));
                    return cells.map(c => {
                        let text = c.textContent.trim().replace(/"/g, '""');
                        return `"${text}"`;
                    }).join(",");
                });
                // UTF-8 BOM (\uFEFF) ensures Hindi/Devanagari characters open correctly in Excel
                const csvContent = "\uFEFF" + csvRows.join("\r\n");
                const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
                const url = URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.setAttribute("href", url);
                link.setAttribute("download", `timetable_${Date.now()}.csv`);
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(url);
            } catch (err) {
                console.warn("Failed to export CSV:", err);
            }
        });

        // Download PDF handler
        pdfBtn.addEventListener("click", () => downloadTablePdf(table, pdfBtn));
    });
}

// Add message to chat
function addMessage(role, content, meta = {}) {
    getElements();
    if (!chatEl) return;
    const div = document.createElement("div");
    div.className = `msg ${role}`;
    
    const modelBadgeHtml = meta.model 
        ? ` <span class="chip ${meta.model === 'nano' ? 'badge-nano' : 'badge-ultra'}">${meta.model}</span>`
        : '';
    
    let memoriesHtml = "";
    if (meta.memories && meta.memories.length > 0) {
        const chips = meta.memories
            .map(m => `<span class="chip">${escapeHtml((m.content || "").substring(0, 30))}</span>`)
            .join(" ");
        memoriesHtml = `<div class="meta memories-used">memories used: ${chips}</div>`;
    }

    const formattedBody = formatContent(role, content);
    div.innerHTML = `<div class="bubble">${formattedBody}${modelBadgeHtml}${memoriesHtml}</div>`;
    chatEl.appendChild(div);

    // Attach interactive PDF, CSV and Copy actions to any tables in this message
    attachTableActions(div);

    chatEl.scrollTop = chatEl.scrollHeight;
}

// Update model badge
function updateBadge(model) {
    getElements();
    if (modelBadge) {
        modelBadge.textContent = model;
        modelBadge.className = `chip ${model === 'nano' ? 'badge-nano' : 'badge-ultra'}`;
    }
}

// Show confirmation dialog
function showConfirmation(prompt, data) {
    getElements();
    pendingConfirmation = data;
    if (confirmText) confirmText.textContent = prompt;
    if (confirmationEl) confirmationEl.classList.remove("hidden");
}

// Handle confirmation
async function handleConfirmation(confirmed) {
    getElements();
    if (confirmationEl) confirmationEl.classList.add("hidden");
    if (!pendingConfirmation) return;

    const actionData = pendingConfirmation;
    pendingConfirmation = null;

    if (confirmed) {
        if (actionData.action_id) {
            try {
                const resp = await fetch(`${API}/actions/${actionData.action_id}/confirm`, { method: "POST" });
                if (!resp.ok) {
                    const err = await resp.json().catch(() => ({}));
                    throw new Error(err.detail || `HTTP ${resp.status}`);
                }
                const res = await resp.json();
                addMessage("assistant", `✓ **Action confirmed and executed:** ${res.summary}`);
            } catch (err) {
                addMessage("system", `Failed to execute action: ${err.message}`);
            }
        } else {
            addMessage("system", "Action confirmed.");
        }
    } else {
        if (actionData.action_id) {
            try {
                await fetch(`${API}/actions/${actionData.action_id}/cancel`, { method: "POST" });
            } catch (_) {}
        }
        addMessage("system", "Action cancelled.");
    }
}

// Send message
async function sendMessage(message, model) {
    getElements();
    if (!message || !message.trim()) return;

    // Dispatch chat-send event so listeners (e.g. voice TTS) can cancel current speech
    window.dispatchEvent(new CustomEvent("chat-send", { detail: { message } }));

    const selectedModel = model || modelSelect?.value || "nano";
    addMessage("user", message);

    // Keep history slice of recent turns to send to the server
    const historyPayload = chatHistory.slice(-10);

    // Append this user turn to ongoing in-memory chat history
    chatHistory.push({ role: "user", content: message });

    try {
        const resp = await fetch(`${API}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message,
                model: selectedModel,
                history: historyPayload
            }),
        });

        if (!resp.ok) {
            let errMsg = `Server returned ${resp.status}`;
            try {
                const errData = await resp.json();
                if (errData && errData.detail) {
                    errMsg = errData.detail;
                }
            } catch (_) {
                const errText = await resp.text();
                if (errText) errMsg = errText;
            }
            throw new Error(errMsg);
        }

        const data = await resp.json();

        // Record assistant response in chat history for future follow-up turns
        chatHistory.push({ role: "assistant", content: data.response });

        addMessage("assistant", data.response, {
            model: data.model_used,
            memories: data.memories_retrieved,
        });
        updateBadge(data.model_used);

        // Notify external handlers (e.g. voice TTS) of assistant response
        window.dispatchEvent(new CustomEvent("assistant-message", {
            detail: {
                response: data.response,
                model_used: data.model_used,
                memories_retrieved: data.memories_retrieved,
            }
        }));

        if (data.requires_confirmation) {
            showConfirmation(data.confirmation_prompt, data);
        }

        // Refresh memories panel if open
        if (memoriesPanel && !memoriesPanel.classList.contains("hidden")) {
            loadMemories();
        }

        // Refresh stats
        loadStats();
    } catch (err) {
        console.error("sendMessage error:", err);
        addMessage("system", `Error: ${err.message}`);
    }
}

// Generate Today's Morning Briefing on demand
async function triggerMorningBrief() {
    getElements();
    if (!morningBriefBtn) return;

    const originalText = morningBriefBtn.innerHTML;
    morningBriefBtn.disabled = true;
    morningBriefBtn.innerHTML = "☀️ Compiling Briefing...";

    try {
        const resp = await fetch(`${API}/morning-brief`, { method: "POST" });
        if (!resp.ok) {
            let errText = "Failed to generate briefing";
            try {
                const d = await resp.json();
                if (d && d.detail) errText = d.detail;
            } catch (_) {}
            throw new Error(errText);
        }

        const data = await resp.json();
        const briefContent = `### ☀️ Today's Executive Morning Briefing\n\n${data.brief}`;

        chatHistory.push({ role: "assistant", content: briefContent });
        addMessage("assistant", briefContent, { model: data.model_used || "nano" });

        // Trigger TTS read-aloud if enabled
        window.dispatchEvent(new CustomEvent("assistant-message", {
            detail: {
                response: data.brief,
                model_used: data.model_used || "nano"
            }
        }));
    } catch (err) {
        console.error("Morning brief error:", err);
        addMessage("system", `Could not generate morning brief: ${err.message}`);
    } finally {
        morningBriefBtn.disabled = false;
        morningBriefBtn.innerHTML = originalText;
    }
}

// Expose sendMessage globally for voice or other extensions
window.sendChatMessage = sendMessage;

// Load previous chat history from persistent storage on startup
async function loadInitialHistory() {
    getElements();
    if (!chatEl) return;
    try {
        const resp = await fetch(`${API}/memories?limit=20`);
        if (!resp.ok) return;
        const memories = await resp.json();
        if (!Array.isArray(memories) || memories.length === 0) return;

        // Memories are returned sorted DESC (newest first); reverse to chronological order
        const chronological = [...memories].reverse();
        for (const m of chronological) {
            const role = m.provenance === "user_said" ? "user" : "assistant";
            chatHistory.push({ role, content: m.content });
            addMessage(role, m.content);
        }
    } catch (err) {
        console.warn("Could not load initial chat history:", err);
    }
}

// Load memories into panel
async function loadMemories() {
    getElements();
    if (!memoriesList) return;
    try {
        const resp = await fetch(`${API}/memories?limit=20`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const memories = await resp.json();
        memoriesList.innerHTML = memories.map(m => `
            <div class="memory-item">
                <span class="provenance ${m.provenance}">${escapeHtml(m.provenance)}</span>
                <span class="content">${escapeHtml((m.content || "").substring(0, 100))}...</span>
                <button class="delete-btn" data-id="${m.id}">Delete</button>
            </div>
        `).join("");

        memoriesList.querySelectorAll(".delete-btn").forEach(btn => {
            btn.addEventListener("click", async () => {
                if (confirm("Hard delete this memory?")) {
                    await fetch(`${API}/memory/${btn.dataset.id}`, { method: "DELETE" });
                    loadMemories();
                    loadStats();
                }
            });
        });
    } catch (err) {
        memoriesList.innerHTML = `<div class="error">Error loading memories: ${escapeHtml(err.message)}</div>`;
    }
}

// Toggle memories panel
function toggleMemories() {
    getElements();
    if (memoriesPanel) {
        memoriesPanel.classList.toggle("hidden");
        if (!memoriesPanel.classList.contains("hidden")) {
            loadMemories();
        }
    }
}

// Load stats for header
async function loadStats() {
    getElements();
    try {
        const resp = await fetch(`${API}/stats`);
        if (!resp.ok) return;
        const data = await resp.json();
        if (costCounter) {
            const cost = data.estimated_cost_usd ?? (data.total_memories * 0.0005);
            costCounter.textContent = `$${cost.toFixed(4)}`;
        }
    } catch (err) {
        console.warn("Stats load failed:", err);
    }
}

// Setup event listeners
function setupEventListeners() {
    getElements();

    if (form) {
        form.addEventListener("submit", (e) => {
            e.preventDefault();
            const msg = input?.value.trim();
            if (!msg) return;
            if (input) input.value = "";
            sendMessage(msg, modelSelect?.value || "nano");
        });
    }

    if (modelSelect) {
        modelSelect.addEventListener("change", () => {
            updateBadge(modelSelect.value);
        });
    }

    if (morningBriefBtn) {
        morningBriefBtn.addEventListener("click", triggerMorningBrief);
    }

    if (costCounter) {
        costCounter.style.cursor = "pointer";
        costCounter.title = "Click to toggle Memories panel (or press Ctrl+M)";
        costCounter.addEventListener("click", toggleMemories);
    }

    if (confirmYes) confirmYes.addEventListener("click", () => handleConfirmation(true));
    if (confirmNo) confirmNo.addEventListener("click", () => handleConfirmation(false));
}

// Global keyboard shortcuts
document.addEventListener("keydown", (e) => {
    getElements();
    if (e.key === "Escape") {
        if (confirmationEl) confirmationEl.classList.add("hidden");
        pendingConfirmation = null;
    }
    if (e.ctrlKey && (e.key === "m" || e.key === "M")) {
        e.preventDefault();
        toggleMemories();
    }
});

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
    setupEventListeners();
    loadInitialHistory();
    loadStats();
});