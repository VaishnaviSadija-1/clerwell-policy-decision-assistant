"use strict";

/**
 * CLERWELL Policy Decision Assistant — frontend logic.
 *
 * Talks to Python exclusively through window.pywebview.api (get_requests,
 * analyze). No result is ever hard-coded by request id — everything shown
 * here comes from what the bridge returns at runtime.
 */

(function () {
  /** @type {Array<Object>} */
  let allRequests = [];
  let selectedId = null;
  let searchTerm = "";
  let typeFilter = "all";
  let lastAnalyzedId = null; // used by the "Try again" retry button

  const el = {
    headerStatus: document.getElementById("header-status"),

    searchInput: document.getElementById("search-input"),
    filterChips: Array.from(document.querySelectorAll(".filter-chip")),
    requestList: document.getElementById("request-list"),
    listEmpty: document.getElementById("list-empty"),

    detailEmpty: document.getElementById("detail-empty"),
    detailContent: document.getElementById("detail-content"),
    detailId: document.getElementById("detail-id"),
    detailTypeBadge: document.getElementById("detail-type-badge"),
    detailRequester: document.getElementById("detail-requester"),
    detailSubmitted: document.getElementById("detail-submitted"),
    detailText: document.getElementById("detail-text"),
    detailMetadata: document.getElementById("detail-metadata"),
    analyzeBtn: document.getElementById("analyze-btn"),
    analyzeBtnSpinner: document.querySelector("#analyze-btn .spinner"),
    analyzeBtnLabel: document.querySelector("#analyze-btn .analyze-btn-label"),

    resultEmpty: document.getElementById("result-empty"),
    resultLoading: document.getElementById("result-loading"),
    resultError: document.getElementById("result-error"),
    resultErrorMessage: document.getElementById("result-error-message"),
    retryBtn: document.getElementById("retry-btn"),
    resultContent: document.getElementById("result-content"),
    decisionBadge: document.getElementById("decision-badge"),
    confidenceFill: document.getElementById("confidence-fill"),
    confidenceValue: document.getElementById("confidence-value"),
    resultSummary: document.getElementById("result-summary"),
    resultEvidence: document.getElementById("result-evidence"),
    resultMissing: document.getElementById("result-missing"),
    resultApproval: document.getElementById("result-approval"),
  };

  // ---------------------------------------------------------------
  // Small helpers
  // ---------------------------------------------------------------

  /** Escape untrusted text before it is ever placed in innerHTML. */
  function escapeHtml(value) {
    const s = value == null ? "" : String(value);
    return s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function truncate(text, maxLen) {
    const s = String(text || "");
    if (s.length <= maxLen) return s;
    return s.slice(0, maxLen).trimEnd() + "…";
  }

  function formatDecisionLabel(decision) {
    return String(decision || "").replace(/_/g, " ");
  }

  function formatSubmittedAt(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function setHeaderStatus(text) {
    el.headerStatus.textContent = text;
  }

  // ---------------------------------------------------------------
  // Request list rendering
  // ---------------------------------------------------------------

  function matchesFilters(req) {
    if (typeFilter !== "all" && req.requester_type !== typeFilter) {
      return false;
    }
    if (!searchTerm) return true;
    const haystack = `${req.request_text || ""} ${req.requester || ""}`.toLowerCase();
    return haystack.includes(searchTerm);
  }

  function renderList() {
    const filtered = allRequests.filter(matchesFilters);

    el.requestList.innerHTML = "";

    if (filtered.length === 0) {
      el.listEmpty.classList.remove("hidden");
      return;
    }
    el.listEmpty.classList.add("hidden");

    const frag = document.createDocumentFragment();
    for (const req of filtered) {
      frag.appendChild(buildRequestItem(req));
    }
    el.requestList.appendChild(frag);
  }

  function buildRequestItem(req) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "request-item";
    if (req.request_id === selectedId) {
      item.classList.add("is-selected");
    }
    item.setAttribute("role", "option");
    item.setAttribute("aria-selected", req.request_id === selectedId ? "true" : "false");
    item.dataset.requestId = req.request_id;

    const top = document.createElement("div");
    top.className = "request-item-top";

    const idSpan = document.createElement("span");
    idSpan.className = "request-id";
    idSpan.textContent = req.request_id;

    const typeBadge = document.createElement("span");
    typeBadge.className = "type-badge " + (req.requester_type === "employee" ? "employee" : "customer");
    typeBadge.textContent = req.requester_type || "";

    top.appendChild(idSpan);
    top.appendChild(typeBadge);

    const nameDiv = document.createElement("div");
    nameDiv.className = "request-name";
    nameDiv.textContent = req.requester || "";

    const previewDiv = document.createElement("div");
    previewDiv.className = "request-preview";
    previewDiv.textContent = truncate(req.request_text, 80);

    item.appendChild(top);
    item.appendChild(nameDiv);
    item.appendChild(previewDiv);

    item.addEventListener("click", () => selectRequest(req.request_id));

    return item;
  }

  // ---------------------------------------------------------------
  // Detail pane rendering
  // ---------------------------------------------------------------

  function selectRequest(requestId) {
    selectedId = requestId;
    renderList();
    renderDetail();
    resetResultPane();
  }

  function findRequest(requestId) {
    return allRequests.find((r) => r.request_id === requestId) || null;
  }

  function renderDetail() {
    const req = findRequest(selectedId);
    if (!req) {
      el.detailEmpty.classList.remove("hidden");
      el.detailContent.classList.add("hidden");
      return;
    }
    el.detailEmpty.classList.add("hidden");
    el.detailContent.classList.remove("hidden");

    el.detailId.textContent = req.request_id;
    el.detailTypeBadge.textContent = req.requester_type || "";
    el.detailTypeBadge.className = "type-badge " + (req.requester_type === "employee" ? "employee" : "customer");
    el.detailRequester.textContent = req.requester || "";
    el.detailSubmitted.textContent = formatSubmittedAt(req.submitted_at);
    el.detailText.textContent = req.request_text || "";

    el.detailMetadata.innerHTML = "";
    const metadata = req.metadata && typeof req.metadata === "object" ? req.metadata : {};
    const keys = Object.keys(metadata);
    if (keys.length === 0) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 2;
      cell.textContent = "No metadata.";
      row.appendChild(cell);
      el.detailMetadata.appendChild(row);
    } else {
      for (const key of keys) {
        const row = document.createElement("tr");
        const keyCell = document.createElement("td");
        keyCell.textContent = key;
        const valCell = document.createElement("td");
        const value = metadata[key];
        valCell.textContent = typeof value === "object" ? JSON.stringify(value) : String(value);
        row.appendChild(keyCell);
        row.appendChild(valCell);
        el.detailMetadata.appendChild(row);
      }
    }
  }

  // ---------------------------------------------------------------
  // Result pane state machine: empty / loading / error / success
  // ---------------------------------------------------------------

  function resetResultPane() {
    show(el.resultEmpty);
    hide(el.resultLoading, el.resultError, el.resultContent);
  }

  function showLoading() {
    show(el.resultLoading);
    hide(el.resultEmpty, el.resultError, el.resultContent);
  }

  function showError(message) {
    el.resultErrorMessage.textContent = message;
    show(el.resultError);
    hide(el.resultEmpty, el.resultLoading, el.resultContent);
  }

  function showResult(result) {
    renderResult(result);
    show(el.resultContent);
    hide(el.resultEmpty, el.resultLoading, el.resultError);
  }

  function show(node) {
    node.classList.remove("hidden");
  }
  function hide(...nodes) {
    for (const n of nodes) n.classList.add("hidden");
  }

  function renderResult(result) {
    const decision = result.decision || "";
    el.decisionBadge.textContent = formatDecisionLabel(decision);
    el.decisionBadge.className = "decision-badge " + decision;

    const confidence = typeof result.confidence === "number" ? result.confidence : null;
    if (confidence === null) {
      el.confidenceFill.style.width = "0%";
      el.confidenceValue.textContent = "—";
    } else {
      const pct = Math.round(Math.max(0, Math.min(1, confidence)) * 100);
      el.confidenceFill.style.width = pct + "%";
      el.confidenceValue.textContent = pct + "%";
    }

    el.resultSummary.textContent = result.summary || "";

    // Supporting evidence
    el.resultEvidence.innerHTML = "";
    const evidence = Array.isArray(result.supporting_evidence) ? result.supporting_evidence : [];
    if (evidence.length === 0) {
      const none = document.createElement("p");
      none.className = "none-state";
      none.textContent = "None.";
      el.resultEvidence.appendChild(none);
    } else {
      for (const item of evidence) {
        el.resultEvidence.appendChild(buildEvidenceItem(item));
      }
    }

    // Missing information
    el.resultMissing.innerHTML = "";
    const missing = Array.isArray(result.missing_information) ? result.missing_information : [];
    if (missing.length === 0) {
      const none = document.createElement("p");
      none.className = "none-state";
      none.textContent = "None.";
      el.resultMissing.appendChild(none);
    } else {
      const ul = document.createElement("ul");
      for (const m of missing) {
        const li = document.createElement("li");
        li.textContent = String(m);
        ul.appendChild(li);
      }
      el.resultMissing.appendChild(ul);
    }

    // Approval
    el.resultApproval.innerHTML = "";
    const approval = result.approval && typeof result.approval === "object" ? result.approval : {};
    const requiredRow = document.createElement("div");
    requiredRow.className = "approval-required-row";
    const flag = document.createElement("span");
    flag.className = "approval-flag " + (approval.required ? "yes" : "no");
    flag.textContent = approval.required ? "Approval required" : "No approval required";
    requiredRow.appendChild(flag);
    el.resultApproval.appendChild(requiredRow);

    const roles = Array.isArray(approval.approver_roles) ? approval.approver_roles : [];
    if (roles.length > 0) {
      const roleWrap = document.createElement("div");
      roleWrap.className = "role-chips";
      for (const role of roles) {
        const chip = document.createElement("span");
        chip.className = "role-chip";
        chip.textContent = String(role).replace(/_/g, " ");
        roleWrap.appendChild(chip);
      }
      el.resultApproval.appendChild(roleWrap);
    }

    if (approval.reason) {
      const reason = document.createElement("p");
      reason.className = "approval-reason";
      reason.textContent = approval.reason;
      el.resultApproval.appendChild(reason);
    }
  }

  function buildEvidenceItem(item) {
    const wrap = document.createElement("div");
    wrap.className = "evidence-item";

    const source = document.createElement("div");
    source.className = "evidence-source";
    const fileSpan = document.createElement("span");
    fileSpan.textContent = item.policy_file || "";
    const sep = document.createElement("span");
    sep.className = "sep";
    sep.textContent = "·";
    const sectionSpan = document.createElement("span");
    sectionSpan.textContent = item.section || "";
    source.appendChild(fileSpan);
    source.appendChild(sep);
    source.appendChild(sectionSpan);

    const passage = document.createElement("p");
    passage.className = "evidence-passage";
    passage.textContent = item.passage || "";

    wrap.appendChild(source);
    wrap.appendChild(passage);
    return wrap;
  }

  // ---------------------------------------------------------------
  // Analyze action
  // ---------------------------------------------------------------

  function setAnalyzing(isAnalyzing) {
    el.analyzeBtn.disabled = isAnalyzing;
    el.analyzeBtnSpinner.classList.toggle("hidden", !isAnalyzing);
    el.analyzeBtnLabel.textContent = isAnalyzing ? "Analyzing…" : "Analyze";
  }

  async function runAnalysis(requestId) {
    if (!requestId) return;
    lastAnalyzedId = requestId;
    setAnalyzing(true);
    showLoading();
    setHeaderStatus("Analyzing " + requestId + "…");

    try {
      const out = await window.pywebview.api.analyze(requestId);
      // Stale response guard: user may have selected another request meanwhile.
      if (requestId !== selectedId) {
        return;
      }
      if (out && out.ok) {
        showResult(out.result);
        setHeaderStatus("Analysis complete for " + requestId + ".");
      } else {
        const message = (out && out.error) || "Analysis failed for an unknown reason.";
        showError(message);
        setHeaderStatus("Analysis failed for " + requestId + ".");
      }
    } catch (err) {
      if (requestId === selectedId) {
        showError("Unexpected error while analyzing: " + (err && err.message ? err.message : String(err)));
        setHeaderStatus("Analysis failed for " + requestId + ".");
      }
    } finally {
      if (requestId === selectedId) {
        setAnalyzing(false);
      }
    }
  }

  // ---------------------------------------------------------------
  // Wiring
  // ---------------------------------------------------------------

  function wireEvents() {
    el.analyzeBtn.addEventListener("click", () => {
      if (selectedId) runAnalysis(selectedId);
    });

    el.retryBtn.addEventListener("click", () => {
      if (lastAnalyzedId) runAnalysis(lastAnalyzedId);
    });

    el.searchInput.addEventListener("input", (e) => {
      searchTerm = e.target.value.trim().toLowerCase();
      renderList();
    });

    for (const chip of el.filterChips) {
      chip.addEventListener("click", () => {
        typeFilter = chip.dataset.filter;
        for (const c of el.filterChips) c.classList.toggle("is-active", c === chip);
        renderList();
      });
    }
  }

  async function loadRequests() {
    setHeaderStatus("Loading requests…");
    try {
      allRequests = await window.pywebview.api.get_requests();
      renderList();
      setHeaderStatus(allRequests.length + " requests loaded.");
    } catch (err) {
      setHeaderStatus("Failed to load requests.");
      el.listEmpty.textContent = "Failed to load requests from the backend.";
      el.listEmpty.classList.remove("hidden");
    }
  }

  function init() {
    wireEvents();
    resetResultPane();
    loadRequests();
  }

  if (window.pywebview && window.pywebview.api) {
    // Bridge already ready (e.g. fast reload).
    init();
  } else {
    window.addEventListener("pywebviewready", init, { once: true });
  }
})();
