/* HireMatch - role-based frontend (candidate / company / admin) */
const App = (() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (v) => String(v ?? "").replace(/[&<>"]/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  let ME = null, PROFILE = null;

  async function api(url, opts = {}) {
    const r = await fetch(url, { credentials: "same-origin", ...opts });
    const ct = r.headers.get("content-type") || "";
    const data = ct.includes("json") ? await r.json() : await r.text();
    if (!r.ok) throw Object.assign(new Error(data.error || r.statusText),
      { data, status: r.status });
    return data;
  }

  /* ---------------- nav config per role ---------------- */
  const NAV = {
    candidate: [
      ["dashboard", "Dashboard", "◆"], ["jobs", "Browse Jobs", "▣"],
      ["matches", "My Matches", "▦"], ["applications", "My Applications", "▤"],
    ],
    company: [
      ["dashboard", "Dashboard", "◆"], ["myjobs", "My Jobs", "▣"],
      ["postjob", "Post a Job", "＋"], ["applications", "Applications", "▤"],
      ["analytics", "Analytics", "▦"],
    ],
    admin: [
      ["dashboard", "Dashboard", "◆"], ["candidates", "Candidates", "☺"],
      ["companies", "Companies", "⌂"], ["users", "All Users", "❑"],
      ["applications", "Applications", "▤"], ["analytics", "Analytics", "▦"],
      ["sql", "Database", "❰❱"], ["email", "Email", "✉"],
    ],
  };
  const TITLES = { dashboard: "Dashboard", jobs: "Browse Jobs", matches: "My Matches",
    applications: "Applications", myjobs: "My Jobs", postjob: "Post a Job",
    candidates: "Candidates", companies: "Companies", users: "All Users",
    analytics: "Analytics", sql: "Database Explorer", email: "Email Settings" };
  const SUBS = {
    dashboard: "A quick overview of your activity.",
    jobs: "Open positions ranked against your uploaded resume.",
    matches: "Every job scored against your resume.",
    applications: "Track the status of your applications.",
    myjobs: "Manage the roles you have published.",
    postjob: "Publish a role and let the matcher rank applicants.",
    candidates: "Every candidate account in the system.",
    companies: "Every company account in the system.",
    users: "All accounts across every role.",
    analytics: "Skill demand and recent platform activity.",
    sql: "Inspect tables, views and run read-only queries (admin only).",
    email: "Configure SMTP so shortlisted candidates get interview emails instantly.",
  };

  /* Which views each role is allowed to open (defence in depth — the
     backend also enforces this with @role_required). */
  const ACCESS = {
    candidate: ["dashboard", "jobs", "matches", "applications"],
    company:   ["dashboard", "myjobs", "postjob", "applications", "analytics"],
    admin:     ["dashboard", "candidates", "companies", "users",
                "applications", "analytics", "sql", "email"],
  };
  const can = (view) => !!ME && (ACCESS[ME.role] || []).includes(view);

  /* ---------------- modal ---------------- */
  function modal(title, html) {
    $("#modalTitle").textContent = title;
    $("#modalBody").innerHTML = html;
    $("#modal").classList.add("open");
  }
  const closeModal = () => $("#modal").classList.remove("open");

  /* ---------------- toasts ---------------- */
  const T_ICON = { success: "✓", error: "✕", warn: "⚠", info: "ⓘ" };
  const T_TITLE = { success: "Success", error: "Error", warn: "Heads up", info: "Notice" };
  function toast(msg, type = "info", title) {
    const host = $("#toasts");
    if (!host) { console.log("[toast]", type, msg); return; }
    while (host.children.length >= 4) host.firstChild.remove();
    const el = document.createElement("div");
    el.className = "toast " + type;
    el.innerHTML = `<span class="t-ico">${T_ICON[type] || T_ICON.info}</span>
      <div class="t-body"><div class="t-title">${esc(title || T_TITLE[type] || "Notice")}</div>
      <div class="t-msg">${esc(msg)}</div></div>
      <button class="t-x" aria-label="Dismiss">✕</button><span class="t-prog"></span>`;
    let remaining = 4000, start = Date.now(), timer;
    const kill = () => { clearTimeout(timer); el.classList.add("out");
      setTimeout(() => el.remove(), 280); };
    const schedule = () => { start = Date.now(); timer = setTimeout(kill, remaining); };
    el.querySelector(".t-x").onclick = kill;
    el.onmouseenter = () => { clearTimeout(timer); remaining -= Date.now() - start;
      el.classList.add("paused"); };
    el.onmouseleave = () => { el.classList.remove("paused"); schedule(); };
    host.appendChild(el);
    schedule();
    return el;
  }

  /* ---------------- notifications for API results ---------------- */
  function reportError(ex) {
    toast(ex && ex.message ? ex.message : "Something went wrong.", "error");
  }

  /* ================= AUTH ================= */
  function showAuth() {
    removeFab();
    closeModal();
    $("#app").style.display = "none";
    $("#authScreen").style.display = "grid";
  }
  function showApp() {
    $("#authScreen").style.display = "none";
    $("#app").style.display = "flex";
    const initials = (ME.full_name || "U").split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();
    $("#avatar").textContent = initials;
    $("#userName").textContent = ME.full_name;
    $("#userRole").textContent = ME.role === "company" && PROFILE && PROFILE.company_name
      ? PROFILE.company_name : ME.role;
    const nav = NAV[ME.role] || [];
    $("#navList").innerHTML = nav.map(([v, label, ico]) =>
      `<button class="nav-item" data-view="${v}"><span>${ico}</span> ${label}</button>`).join("");
    $$(".nav-item").forEach(b => b.addEventListener("click", () => go(b.dataset.view)));
    buildFab();
    go("dashboard");
  }
  const removeFab = () => $("#fab")?.remove();
  function buildFab() {
    removeFab();
    if (!ME || ME.role !== "candidate") return;
    const fab = document.createElement("button");
    fab.id = "fab"; fab.className = "fab"; fab.title = "Upload resume"; fab.textContent = "+";
    fab.onclick = openUpload;
    document.body.appendChild(fab);
  }

  async function doLogin(e) {
    e.preventDefault();
    const btn = $("#loginForm button[type=submit]"); btn.textContent = "Signing in…";
    try {
      const res = await api("/api/auth/login", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier: $("#loginId").value, password: $("#loginPw").value }) });
      ME = res.user; PROFILE = res.profile;
      clearAuthFields();
      showApp();
      toast("Welcome back, " + (ME.full_name || "there") + "!", "success");
    } catch (ex) { $("#loginErr").textContent = ex.message; reportError(ex); }
    finally { btn.textContent = "Sign in"; }
  }

  async function doRegister(e) {
    e.preventDefault();
    const role = $('input[name="role"]:checked').value;
    const body = {
      role, full_name: $("#regName").value, email: $("#regEmail").value,
      phone: $("#regPhone").value, password: $("#regPw").value,
      location: $("#regLoc").value, years_experience: $("#regYears").value,
      company_name: $("#regCompany").value, industry: $("#regIndustry").value,
      website: $("#regWebsite").value,
    };
    const btn = $("#regForm button[type=submit]"); btn.textContent = "Creating…";
    try {
      const res = await api("/api/auth/register", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      ME = res.user; PROFILE = res.profile;
      clearAuthFields();
      showApp();
      toast("Account created — welcome to HireMatch!", "success");
    } catch (ex) { $("#regErr").textContent = ex.message; reportError(ex); }
    finally { btn.textContent = "Create account"; }
  }

  async function logout() {
    try { await api("/api/auth/logout", { method: "POST" }); } catch { /* ignore */ }
    ME = null; PROFILE = null;
    clearAuthFields();
    $$(".auth-tab").forEach(x => x.classList.toggle("active", x.dataset.auth === "login"));
    $("#loginForm").style.display = "block";
    $("#regForm").style.display = "none";
    showAuth();
    toast("You've been signed out.", "info");
  }

  /* Wipe every auth field so switching users starts from a clean slate. */
  function clearAuthFields() {
    ["loginId", "loginPw", "regName", "regEmail", "regPhone", "regPw",
     "regLoc", "regYears", "regCompany", "regIndustry", "regWebsite"]
      .forEach(id => { const el = $("#" + id); if (el) el.value = ""; });
    const le = $("#loginErr"), re = $("#regErr");
    if (le) le.textContent = "";
    if (re) re.textContent = "";
    $$(".pw-toggle").forEach(b => {
      const inp = $("#" + b.dataset.pw);
      if (inp) inp.type = "password";
      b.textContent = "👁";
      b.setAttribute("aria-label", "Show password");
    });
  }

  /* ================= ROUTER ================= */
  async function go(view) {
    if (ME && !can(view)) return renderPerm(view);
    $$(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.view === view));
    $("#pageTitle").textContent = TITLES[view] || view;
    $("#pageSub").textContent = SUBS[view] || "";
    const host = $("#views");
    host.innerHTML = `<div class="panel"><div class="skel-line">
      <div class="skeleton" style="width:40%;height:18px;margin-bottom:14px"></div>
      <div class="skeleton" style="width:100%;margin-bottom:10px"></div>
      <div class="skeleton" style="width:85%;margin-bottom:10px"></div>
      <div class="skeleton" style="width:60%"></div></div></div>`;
    try {
      await (VIEWS[view] || VIEWS.dashboard)(host);
      animateStats();
    } catch (ex) {
      host.innerHTML = `<div class="perm"><div class="ico">⚠️</div>
        <h3>Couldn't load this page</h3><p>${esc(ex.message)}</p>
        <button class="btn" onclick="App.go('${esc(view)}')">Try again</button></div>`;
      toast(ex.message, "error");
    }
  }

  function renderPerm(view) {
    $$(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.view === view));
    $("#pageTitle").textContent = TITLES[view] || "Restricted";
    $("#pageSub").textContent = "";
    const isCandidateJob = view === "postjob" || view === "myjobs";
    $("#views").innerHTML = `<div class="perm">
      <div class="ico">🔒</div>
      <h3>Access restricted</h3>
      <p>Your account role is <b>${esc(ME.role)}</b>, which can't open
         <b>${esc(TITLES[view] || view)}</b>.
         ${isCandidateJob ? "Posting and managing jobs is available to <b>company</b> accounts only." :
           "This area is for a different role."}</p>
      <button class="btn" onclick="App.go('dashboard')">Back to dashboard</button></div>`;
    toast("You don't have access to " + (TITLES[view] || view) + ".", "warn");
  }

  function animateStats() {
    $$(".stat .val").forEach(el => {
      const raw = el.textContent.trim();
      const m = raw.match(/^([\d,]+)(%?)$/);
      if (!m) return;
      const target = parseInt(m[1].replace(/,/g, ""), 10);
      if (!isFinite(target) || target === 0) return;
      const suffix = m[2] || "", dur = 750, t0 = performance.now();
      const step = (t) => {
        const p = Math.min(1, (t - t0) / dur);
        const eased = 1 - Math.pow(1 - p, 3);
        el.textContent = Math.round(target * eased).toLocaleString() + suffix;
        if (p < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
  }

  const statCards = (arr) => `<div class="stats-grid">${arr.map(([l, v, a, ico]) =>
    `<div class="stat ${a ? "accent" : ""}">${ico ? `<div class="ico">${ico}</div>` : ""}
     <div class="val">${esc(v)}</div><div class="lbl">${esc(l)}</div></div>`).join("")}</div>`;

  /* ================= VIEWS ================= */
  const VIEWS = {};

  VIEWS.dashboard = async (h) => {
    const s = await api("/api/stats");
    if (s.role === "candidate") {
      h.innerHTML = statCards([["Open Jobs", s.open_jobs, 0, "▣"],
        ["My Matches", s.my_matches, 1, "▦"], ["Avg Match Score", (s.avg_score || 0) + "%", 1, "◎"],
        ["Applications", s.applications, 0, "▤"]])
        + `<div class="panel"><h3>Your Best Match</h3>${s.best.length ?
          `<div class="rank-row" style="cursor:default">
             <div class="rank-no">★</div>
             <div><div class="rank-name">${esc(s.best[0].job)}</div>
                  <div class="rank-sub">${esc(s.best[0].company || "")}</div></div>
             <div class="rank-bar"><i style="width:${s.best[0].score}%"></i></div>
             <div class="score-pill">${s.best[0].score}%
               <div class="rec ${esc(s.best[0].recommendation)}">${esc(s.best[0].recommendation)}</div></div>
           </div>` : `<div class="empty">Upload a resume (the + button) to see matches.</div>`}</div>`;
    } else if (s.role === "company") {
      h.innerHTML = statCards([["My Jobs", s.jobs, 0, "▣"], ["Applicants", s.applicants, 1, "▤"],
        ["Avg Match Score", (s.avg_score || 0) + "%", 1, "◎"], ["Candidate Pool", s.total_candidates, 0, "☺"]])
        + `<div class="panel"><h3>Quick actions</h3>
             <button class="btn" onclick="App.go('postjob')">Post a Job</button>
             <button class="btn ghost" style="margin-left:8px" onclick="App.go('myjobs')">View My Jobs</button></div>`;
    } else {
      h.innerHTML = statCards([["Candidates", s.candidates, 0, "☺"], ["Companies", s.companies, 0, "⌂"],
        ["Resumes", s.resumes, 0, "▧"], ["Job Postings", s.jobs, 0, "▣"],
        ["Matches Scored", s.matches, 1, "▦"], ["Applications", s.applications, 0, "▤"],
        ["Skills", s.skills, 0, "✦"], ["Avg Score", (s.avg_score || 0) + "%", 1, "◎"]])
        + `<div class="panel"><h3>Top Match Right Now</h3>${s.best_match ?
          `<div class="rank-row" style="cursor:default">
             <div class="rank-no">★</div>
             <div><div class="rank-name">${esc(s.best_match.candidate)} → ${esc(s.best_match.job_title)}</div>
                  <div class="rank-sub">${esc(s.best_match.company || "")}</div></div>
             <div class="rank-bar"><i style="width:${s.best_match.final_score}%"></i></div>
             <div class="score-pill">${esc(s.best_match.final_score)}%
               <div class="rec ${esc(s.best_match.recommendation)}">${esc(s.best_match.recommendation)}</div></div>
           </div>` : `<div class="empty">No matches yet.</div>`}</div>`;
    }
  };

  /* ---- candidate: browse jobs ---- */
  VIEWS.jobs = async (h) => {
    h.innerHTML = `<div class="panel"><div class="panel-head">
        <h3>Open Positions</h3>
        <input id="jobSearch" class="input" style="max-width:300px" placeholder="Search title, company, keyword…" />
      </div><div id="jobsList" class="cards"><div class="empty">Loading…</div></div></div>`;
    const load = async (q = "") => {
      const jobs = await api("/api/jobs" + (q ? "?q=" + encodeURIComponent(q) : ""));
      $("#jobsList").innerHTML = jobs.length ? jobs.map(j => `
        <div class="card">
          <div class="title">${esc(j.title)} ${j.verified ? '<span class="tag">✓ verified</span>' : ""}</div>
          <div class="line"><span>Company</span><b>${esc(j.company_name || j.company || "—")}</b></div>
          <div class="line"><span>Location</span><b>${esc(j.location || "—")}</b></div>
          <div class="line"><span>Min experience</span><b>${j.min_experience} yrs</b></div>
          <div class="line"><span>Skills</span><b>${j.skill_count}</b></div>
          ${j.my_score != null ? `<div class="line"><span>Your match</span>
             <b style="color:var(--brand)">${j.my_score}% • ${esc(j.my_rec)}</b></div>` : ""}
          <div class="actions">
            ${j.applied ? `<span class="badge-status submitted">Applied</span>` :
              `<button class="btn small" data-apply="${j.job_id}">Apply</button>`}
            <button class="btn ghost small" data-job="${j.job_id}">View</button>
          </div>
        </div>`).join("") : `<div class="empty">No jobs found.</div>`;
      $$("[data-apply]", $("#jobsList")).forEach(b => b.onclick = () => applyJob(b.dataset.apply));
      $$("[data-job]", $("#jobsList")).forEach(b => b.onclick = () => jobDetail(b.dataset.job));
    };
    load();
    let t; $("#jobSearch").addEventListener("input", e => { clearTimeout(t);
      t = setTimeout(() => load(e.target.value), 250); });
  };

  async function jobDetail(id) {
    const d = await api("/api/job/" + id);
    const j = d.job;
    modal(j.title, `
      <div class="muted" style="margin-bottom:6px">${esc(j.company_name || j.company || "")} • ${esc(j.location || "")} • ${j.min_experience} yrs • ${esc(j.employment_type || "")}</div>
      ${d.my_match ? `<div class="score-grid">
         <div class="score-box"><div class="n">${d.my_match.final_score}%</div><div class="t">Your Match</div></div>
         <div class="score-box"><div class="n">${d.my_match.skill_score}</div><div class="t">Skills</div></div>
         <div class="score-box"><div class="n">${d.my_match.tfidf_score}</div><div class="t">TF-IDF</div></div>
         <div class="score-box"><div class="n">${d.my_match.embedding_score ?? "—"}</div><div class="t">Embedding</div></div>
       </div>` : ""}
      <div class="sec-title">Required skills</div>
      <div class="chip-wrap">${d.skills.map(s =>
        `<span class="chip ${s.is_required ? "match" : ""}">${esc(s.name)}</span>`).join("")}</div>
      <div class="sec-title">Description</div>
      <p class="muted" style="white-space:pre-wrap">${esc(j.description)}</p>
      <div class="form-actions">${ME.role === "candidate" ?
        `<button class="btn" onclick="App._applyFromModal(${id})">Apply now</button>` : ""}</div>`);
  }

  async function applyJob(id) {
    try { await api("/api/apply", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: Number(id) }) });
      closeModal(); toast("Application submitted successfully.", "success"); go("jobs"); }
    catch (ex) { reportError(ex); }
  }

  VIEWS.matches = async (h) => {
    const rows = await api("/api/my/matches");
    h.innerHTML = `<div class="panel"><h3>Jobs ranked by your resume</h3>
      ${rows.length ? rows.map((r, i) => `
        <div class="rank-row" data-m="${r.match_id}">
          <div class="rank-no">${i + 1}</div>
          <div><div class="rank-name">${esc(r.job_title)}</div>
               <div class="rank-sub">${esc(r.company || "")} • ${esc(r.location || "")}</div></div>
          <div class="rank-bar"><i style="width:${r.final_score}%"></i></div>
          <div class="score-pill">${r.final_score}%
            <div class="rec ${esc(r.recommendation)}">${esc(r.recommendation)}</div></div>
        </div>`).join("") : `<div class="empty">No matches yet — upload a resume with the + button.</div>`}
    </div>`;
    $$("[data-m]", h).forEach(el => el.onclick = () => openMatch(el.dataset.m));
  };

  VIEWS.applications = async (h) => {
    const isCompany = ME.role === "company";
    const url = isCompany ? "/api/company/applications" : "/api/my/applications";
    const rows = await api(url);
    h.innerHTML = `<div class="panel"><h3>Applications</h3>${rows.length ?
      `<div class="sql-result"><table class="data"><thead><tr>
        <th>Job</th>${isCompany ? "<th>Candidate</th>" : "<th>Company</th>"}
        <th>Match</th><th>Status</th><th>Applied</th>${isCompany ? "<th>Decision</th>" : ""}</tr></thead><tbody>
        ${rows.map(r => `<tr><td>${esc(r.job_title)}</td>
          <td>${esc(isCompany ? r.candidate : (r.company || "—"))}</td>
          <td>${r.match_score != null ? r.match_score + "%" : "—"}</td>
          <td><span class="badge-status ${esc(r.status)}">${esc(r.status)}</span></td>
          <td>${esc(r.applied_at)}</td>
          ${isCompany ? `<td><div style="display:flex;gap:7px;flex-wrap:wrap">
            <button class="btn ok small" data-dec="shortlisted" data-app="${r.application_id}">Accept</button>
            <button class="btn danger small" data-dec="rejected" data-app="${r.application_id}">Reject</button></div></td>` : ""}
        </tr>`).join("")}
      </tbody></table></div>` : `<div class="empty">No applications yet.</div>`}</div>`;
    $$("[data-dec]", h).forEach(b => b.onclick = () => setStatus(b.dataset.app, b.dataset.dec));
  };

  async function setStatus(appId, status) {
    try {
      const res = await api("/api/company/applications/" + appId, { method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }) });
      if (status === "shortlisted") notifyShortlist(res.email);
      else if (status === "rejected") toast("Application marked as rejected.", "info");
      else toast("Application status updated.", "success");
      go("applications");
    } catch (ex) { reportError(ex); }
  }

  function notifyShortlist(email) {
    if (!email) return;
    if (!email.recipient) { toast("Shortlisted — but the candidate has no email on file, so no invitation could be sent.", "warn"); return; }
    if (email.status === "sent") toast("Interview invitation emailed to " + email.recipient + ".", "success");
    else if (email.status === "dev") toast("Invitation for " + email.recipient +
      " was saved to the email log (configure SMTP in config.py to send real mail).", "warn");
    else toast("Shortlisted, but the invitation email failed: " + (email.detail || "unknown error"), "error");
  }

  /* ---- company: my jobs + applicants ---- */
  VIEWS.myjobs = async (h) => {
    const jobs = await api("/api/company/jobs");
    h.innerHTML = `<div class="panel"><div class="panel-head"><h3>My Job Postings</h3>
      <button class="btn" onclick="App.go('postjob')">＋ Post a Job</button></div>
      <div class="cards">${jobs.length ? jobs.map(j => `
        <div class="card">
          <div class="title">${esc(j.title)}</div>
          <div class="line"><span>Location</span><b>${esc(j.location || "—")}</b></div>
          <div class="line"><span>Applicants</span><b>${j.applicants}</b></div>
          <div class="line"><span>Avg match</span><b>${j.avg_score || 0}%</b></div>
          <div class="actions">
            <button class="btn small" data-app="${j.job_id}">View candidates</button>
            <button class="btn danger small" data-del="${j.job_id}">Delete</button>
          </div>
        </div>`).join("") : `<div class="empty">No jobs yet — post your first one.</div>`}</div></div>`;
    $$("[data-app]", h).forEach(b => b.onclick = () => applicants(b.dataset.app));
    $$("[data-del]", h).forEach(b => b.onclick = async () => {
      if (!confirm("Delete this job posting?")) return;
      await api("/api/company/jobs/" + b.dataset.del, { method: "DELETE" }); go("myjobs");
    });
  };

  async function applicants(jobId) {
    const d = await api(`/api/company/jobs/${jobId}/applicants`);
    const rows = d.applicants;
    modal("Candidates for " + d.job.title, rows.length ? rows.map((r, i) => `
      <div class="rank-row" data-m="${r.match_id}" style="grid-template-columns:48px 1fr 116px;cursor:default">
        <div class="rank-no">${i + 1}</div>
        <div><div class="rank-name">${esc(r.candidate)}
             ${r.application_id ? `<span class="badge-status ${esc(r.application_status)}" style="margin-left:8px">${esc(r.application_status)}</span>` : ""}</div>
             <div class="rank-sub">${esc(r.resume_title || "")} • ${r.years_experience} yrs •
             ${esc(r.location || "")}</div>
             ${r.application_id ? `<div style="margin-top:8px;display:flex;gap:7px">
               <button class="btn ok small" data-dec="shortlisted" data-app="${r.application_id}">Accept</button>
               <button class="btn danger small" data-dec="rejected" data-app="${r.application_id}">Reject</button></div>`
               : `<div class="muted tiny" style="margin-top:6px">hasn't applied — just ranked</div>`}</div>
        <div class="score-pill">${r.final_score}%
          <div class="rec ${esc(r.recommendation)}">${esc(r.recommendation)}</div></div>
      </div>`).join("") : `<div class="empty">No candidates scored for this job yet.</div>`);
    $$("[data-dec]", $("#modalBody")).forEach(b => b.onclick = async (ev) => {
      ev.stopPropagation();
      try {
        const res = await api("/api/company/applications/" + b.dataset.app, { method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: b.dataset.dec }) });
        if (b.dataset.dec === "shortlisted") notifyShortlist(res.email);
        else if (b.dataset.dec === "rejected") toast("Application marked as rejected.", "info");
        applicants(jobId);
      } catch (ex) { reportError(ex); }
    });
    $$("[data-m]", $("#modalBody")).forEach(el => el.onclick = () => openMatch(el.dataset.m));
  }

  VIEWS.postjob = async (h) => {
    if (!can("postjob")) return renderPerm("postjob");
    h.innerHTML = `<div class="panel"><h3>Post a New Job</h3>
      <div class="form-grid">
        <input id="j_title" class="input" placeholder="Job title *" />
        <input id="j_loc" class="input" placeholder="Location" />
        <input id="j_exp" class="input" type="number" min="0" step="0.5" placeholder="Min experience (yrs)" />
        <input id="j_sal" class="input" placeholder="Salary (optional)" />
        <input id="j_type" class="input" placeholder="Employment type (Full-time)" />
        <input id="j_skills" class="input" placeholder="Skills, comma separated (optional — auto-detected)" />
      </div>
      <textarea id="j_desc" class="input textarea" rows="8" placeholder="Job description *"></textarea>
      <div class="form-actions"><button id="btnPost" class="btn">Publish job</button>
        <span id="postMsg" class="muted"></span></div></div>`;
    $("#btnPost").onclick = async () => {
      const body = { title: $("#j_title").value, location: $("#j_loc").value,
        min_experience: $("#j_exp").value, salary: $("#j_sal").value,
        employment_type: $("#j_type").value, skills: $("#j_skills").value,
        description: $("#j_desc").value };
      const msg = $("#postMsg"); msg.textContent = "Publishing…";
      try { const r = await api("/api/company/jobs", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        msg.textContent = `✓ Published (id ${r.job_id}) with ${r.skills.length} skills.`;
        toast(`Job published with ${r.skills.length} detected skills.`, "success");
        setTimeout(() => go("myjobs"), 900);
      } catch (ex) { msg.textContent = ex.message; reportError(ex); }
    };
  };

  /* ---- admin ---- */
  VIEWS.candidates = async (h) => {
    const rows = await api("/api/admin/candidates");
    h.innerHTML = `<div class="panel"><div class="panel-head">
      <h3>All Candidates (<span data-count>${rows.length}</span>)</h3>
      <input class="input" data-search style="max-width:300px" placeholder="Search name, email, location…" />
      </div>
      <div class="sql-result"><table class="data"><thead><tr>
        <th>Name</th><th>Email</th><th>Phone</th><th>Location</th><th>Exp</th>
        <th>Resumes</th><th>Apps</th><th>Active</th><th>Actions</th></tr></thead><tbody>
        ${rows.map(c => `<tr>
          <td>${esc(c.full_name)}</td><td>${esc(c.email || "—")}</td><td>${esc(c.phone || "—")}</td>
          <td>${esc(c.location || "—")}</td><td>${c.years_experience}</td>
          <td>${c.resume_count}</td><td>${c.applications}</td>
          <td>${c.is_active ? "✅" : "⛔"}</td>
          <td><button class="btn ghost small" data-tog="${c.user_id}">${c.is_active ? "Disable" : "Enable"}</button>
              <button class="btn danger small" data-del="${c.user_id}">Delete</button></td>
        </tr>`).join("")}</tbody></table></div></div>`;
    wireAdmin(h, "candidates");
  };

  VIEWS.companies = async (h) => {
    const rows = await api("/api/admin/companies");
    h.innerHTML = `<div class="panel"><div class="panel-head">
      <h3>All Companies (<span data-count>${rows.length}</span>)</h3>
      <input class="input" data-search style="max-width:300px" placeholder="Search company, HR, industry…" />
      </div>
      <div class="sql-result"><table class="data"><thead><tr>
        <th>Company</th><th>HR / Contact</th><th>Industry</th><th>Login email</th>
        <th>Phone</th><th>Jobs</th><th>Verified</th><th>Active</th><th>Actions</th></tr></thead><tbody>
        ${rows.map(c => `<tr>
          <td>${esc(c.company_name)}</td><td>${esc(c.hr_name || "—")}</td>
          <td>${esc(c.industry || "—")}</td>
          <td>${esc(c.login_email || "—")}</td><td>${esc(c.phone || "—")}</td>
          <td>${c.job_count}</td>
          <td>${c.verified ? "✅" : "—"}</td><td>${c.is_active ? "✅" : "⛔"}</td>
          <td><button class="btn ok small" data-ver="${c.company_id}">${c.verified ? "Unverify" : "Verify"}</button>
              <button class="btn ghost small" data-tog="${c.user_id}">${c.is_active ? "Disable" : "Enable"}</button>
              <button class="btn danger small" data-del="${c.user_id}">Delete</button></td>
        </tr>`).join("")}</tbody></table></div></div>`;
    $$("[data-ver]", h).forEach(b => b.onclick = async () => {
      await api("/api/admin/companies/" + b.dataset.ver + "/verify", { method: "POST" }); go("companies"); });
    wireAdmin(h, "companies");
  };

  VIEWS.users = async (h) => {
    const rows = await api("/api/admin/users");
    h.innerHTML = `<div class="panel"><div class="panel-head">
      <h3>All Users (<span data-count>${rows.length}</span>)</h3>
      <input class="input" data-search style="max-width:300px" placeholder="Search name, role, email…" />
      </div>
      <div class="sql-result"><table class="data"><thead><tr>
        <th>Name</th><th>Role</th><th>Email</th><th>Phone</th><th>Active</th>
        <th>Joined</th><th>Actions</th></tr></thead><tbody>
        ${rows.map(u => `<tr>
          <td>${esc(u.full_name)}</td><td><span class="tag">${esc(u.role)}</span></td>
          <td>${esc(u.email || "—")}</td><td>${esc(u.phone || "—")}</td>
          <td>${u.is_active ? "✅" : "⛔"}</td><td>${esc(u.created_at)}</td>
          <td>${u.role === "admin" ? "<span class='muted'>protected</span>" :
            `<button class="btn ghost small" data-tog="${u.user_id}">${u.is_active ? "Disable" : "Enable"}</button>
             <button class="btn danger small" data-del="${u.user_id}">Delete</button>`}</td>
        </tr>`).join("")}</tbody></table></div></div>`;
    wireAdmin(h, "users");
  };

  function wireAdmin(h, view) {
    $$("[data-tog]", h).forEach(b => b.onclick = async () => {
      await api(`/api/admin/users/${b.dataset.tog}/toggle`, { method: "POST" });
      toast("User status updated.", "success"); go(view);
    });
    $$("[data-del]", h).forEach(b => b.onclick = async () => {
      if (!confirm("Delete this user and all their data?")) return;
      await api("/api/admin/users/" + b.dataset.del, { method: "DELETE" });
      toast("User deleted.", "info"); go(view);
    });
    wireSearch(h);
  }

  function wireSearch(root) {
    const inp = root.querySelector("[data-search]");
    const table = root.querySelector("table.data");
    if (!inp || !table || !table.tBodies.length) return;
    inp.addEventListener("input", () => {
      const q = inp.value.trim().toLowerCase();
      let shown = 0;
      [...table.tBodies[0].rows].forEach(tr => {
        const hit = !q || tr.textContent.toLowerCase().includes(q);
        tr.style.display = hit ? "" : "none";
        if (hit) shown++;
      });
      const c = root.querySelector("[data-count]");
      if (c) c.textContent = shown;
    });
  }

  /* ---- analytics + sql (shared) ---- */
  VIEWS.analytics = async (h) => {
    const rows = await api("/api/skill_demand");
    const max = Math.max(1, ...rows.map(r => r.jobs_requiring + r.resumes_with_skill));
    const act = await api("/api/activity");
    h.innerHTML = `<div class="panel"><h3>Most In-Demand Skills</h3>
        <div class="bars">${rows.slice(0, 18).map(r => {
          const total = r.jobs_requiring + r.resumes_with_skill;
          return `<div class="bar-row"><div class="bar-label">${esc(r.skill)}</div>
            <div class="bar-track"><div class="bar-fill" style="width:${(total / max * 100).toFixed(0)}%"></div></div>
            <div class="bar-val">${r.jobs_requiring}j / ${r.resumes_with_skill}r</div></div>`;
        }).join("")}</div></div>
      <div class="panel"><h3>Recent Activity</h3>
        <ul class="activity">${act.map(a => `<li><b>${esc(a.event_type)}</b> — ${esc(a.message)}
          <span class="muted">${esc(a.created_at)}${a.actor ? " • " + esc(a.actor) : ""}</span></li>`).join("")
          || '<li class="empty">none</li>'}</ul></div>`;
  };

  VIEWS.sql = async (h) => {
    const data = await api("/api/tables");
    h.innerHTML = `<div class="panel"><h3>Database Explorer</h3>
        <p class="muted">Tables and views. Click any object to preview its rows.</p>
        <div class="chips">${data.tables.map(x =>
          `<div class="tbl-chip" data-tbl="${esc(x.name)}"><div class="n">${esc(x.name)}</div>
           <div class="r">${x.rows} rows • ${x.columns.length} cols</div></div>`).join("")}
          ${data.views.map(x => `<div class="tbl-chip view" data-tbl="${esc(x)}">
           <div class="n">${esc(x)}</div><div class="r">view</div></div>`).join("")}</div></div>
      <div class="panel"><div class="panel-head"><h3>Run a read-only SQL query</h3>
        <button id="btnSql" class="btn small">▶ Execute</button></div>
        <textarea id="sqlInput" class="input textarea code" rows="4">SELECT * FROM v_match_summary LIMIT 10;</textarea>
        <div id="sqlResult" class="sql-result hidden"></div></div>`;
    $$("[data-tbl]", h).forEach(b => b.onclick = () => {
      $("#sqlInput").value = `SELECT * FROM ${b.dataset.tbl} LIMIT 20;`; runSql(); });
    $("#btnSql").onclick = runSql;
  };

  VIEWS.email = async (h) => {
    const s = await api("/api/admin/mail-settings");
    const badge = s.configured
      ? '<span class="tag green">● live — emails are being sent</span>'
      : '<span class="tag" style="background:var(--warn-bg);color:var(--warn)">● not configured yet</span>';
    h.innerHTML = `<div class="panel"><div class="panel-head">
        <h3>Email (SMTP) settings ${badge}</h3>
        <span class="muted tiny">Used to email candidates a professional interview invitation the moment a company shortlists them.</span></div>
      <div class="form-grid">
        <div><label class="fld-lbl">SMTP host</label><input id="m_host" class="input" placeholder="smtp.gmail.com" /></div>
        <div><label class="fld-lbl">Port</label><input id="m_port" class="input" type="number" placeholder="587" /></div>
        <div><label class="fld-lbl">Username (email address)</label><input id="m_user" class="input" placeholder="you@gmail.com" /></div>
        <div><label class="fld-lbl">Password / App password</label>
          <div class="pw-wrap"><input id="m_pass" class="input" type="password" placeholder="leave blank to keep the saved one" />
            <button type="button" class="pw-toggle" data-pw="m_pass" aria-label="Show password">👁</button></div></div>
        <div><label class="fld-lbl">Send-from address (optional)</label><input id="m_from" class="input" placeholder="blank = username" /></div>
        <div><label class="fld-lbl">Sender name</label><input id="m_fromName" class="input" placeholder="HireMatch Recruitment" /></div>
      </div>
      <div class="form-actions">
        <button id="btnSaveMail" class="btn">Save settings</button>
        <button id="btnTestMail" class="btn ghost">Send test email…</button>
        <span id="mailMsg" class="muted"></span>
      </div></div>
      <div class="panel" style="background:var(--warn-bg);border:1px solid #f3d9a4">
        <b style="color:var(--warn)">Gmail guide</b>
        <p class="muted" style="margin:6px 0 0;line-height:1.6">Use host <code>smtp.gmail.com</code>, port <code>587</code>,
        your full Gmail address, and an <b>App password</b> (Google Account → Security → 2‑Step Verification →
        App passwords — not your normal Gmail password). Click <b>Save</b>, then <b>Send test email</b>.</p></div>`;
    $("#m_host").value = s.host; $("#m_port").value = s.port;
    $("#m_user").value = s.user; $("#m_from").value = s.from || "";
    $("#m_fromName").value = s.from_name;
    $("#btnSaveMail").onclick = async () => {
      const msg = $("#mailMsg"); msg.textContent = "Saving…";
      try {
        await api("/api/admin/mail-settings", { method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ host: $("#m_host").value, port: $("#m_port").value,
            user: $("#m_user").value, password: $("#m_pass").value,
            from: $("#m_from").value, from_name: $("#m_fromName").value }) });
        msg.textContent = "✓ Saved."; $("#m_pass").value = "";
        toast("Email settings saved.", "success"); go("email");
      } catch (ex) { msg.textContent = ex.message; reportError(ex); }
    };
    $("#btnTestMail").onclick = async () => {
      const dst = prompt("Send a test email to:", $("#m_user").value || "you@example.com");
      if (!dst) return;
      const msg = $("#mailMsg"); msg.textContent = "Sending…";
      try {
        await api("/api/admin/mail-settings/test", { method: "POST",
          headers: { "Content-Type": "application/json" }, body: JSON.stringify({ to: dst }) });
        msg.textContent = "✓ Test email sent."; toast("Test email sent to " + dst + ".", "success");
      } catch (ex) { msg.textContent = ex.message; reportError(ex); }
    };
  };

  async function runSql() {
    const out = $("#sqlResult"); out.classList.remove("hidden");
    out.innerHTML = `<div class="empty">Running…</div>`;
    try {
      const res = await api("/api/sql", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: $("#sqlInput").value }) });
      if (!res.rows.length) { out.innerHTML = `<div class="empty">Query returned 0 rows.</div>`; return; }
      out.innerHTML = `<table class="data"><thead><tr>${res.columns.map(c => `<th>${esc(c)}</th>`).join("")}
        </tr></thead><tbody>${res.rows.map(r => `<tr>${res.columns.map(c => `<td>${esc(r[c])}</td>`).join("")}</tr>`).join("")}
        </tbody></table>`;
    } catch (ex) { out.innerHTML = `<div class="err">${esc(ex.message)}</div>`; }
  }

  /* ---- '+ upload' modal (candidate) ---- */
  function openUpload() {
    modal("Upload your resume", `
      <div class="dropzone" id="dz">
        <div class="big">⬆</div>
        <div><b>Click to choose a file</b> or drag &amp; drop</div>
        <div class="muted tiny">.txt, .pdf, .md, .csv — up to 8 MB</div>
        <input type="file" id="fileInput" accept=".txt,.pdf,.md,.csv" hidden />
      </div>
      <div class="sec-title">…or paste the resume text</div>
      <textarea id="upText" class="input textarea" rows="7" placeholder="Paste resume content here…"></textarea>
      <div class="form-grid two" style="margin-top:12px">
        <input id="upTitle" class="input" placeholder="Resume title (e.g. ML Engineer)" />
        <input id="upYears" class="input" type="number" min="0" step="0.5" placeholder="Years of experience" />
      </div>
      <div class="form-actions"><button id="btnUpload" class="btn">Analyse resume</button>
        <span id="upMsg" class="muted"></span></div>`);
    const dz = $("#dz"), fi = $("#fileInput");
    dz.onclick = () => fi.click();
    dz.ondragover = e => { e.preventDefault(); dz.classList.add("drag"); };
    dz.ondragleave = () => dz.classList.remove("drag");
    dz.ondrop = e => { e.preventDefault(); dz.classList.remove("drag");
      fi.files = e.dataTransfer.files; dz.querySelector("b").textContent = e.dataTransfer.files[0].name; };
    fi.onchange = () => { if (fi.files[0]) dz.querySelector("b").textContent = fi.files[0].name; };
    $("#btnUpload").onclick = submitUpload;
  }

  async function submitUpload() {
    const msg = $("#upMsg"); msg.textContent = "Analysing…";
    const fi = $("#fileInput");
    try {
      let res;
      if (fi.files[0]) {
        const fd = new FormData();
        fd.append("file", fi.files[0]);
        fd.append("title", $("#upTitle").value || fi.files[0].name);
        fd.append("years_experience", $("#upYears").value);
        res = await api("/api/resume", { method: "POST", body: fd });
      } else {
        res = await api("/api/resume", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: $("#upText").value, title: $("#upTitle").value,
            years_experience: $("#upYears").value }) });
      }
      msg.textContent = `✓ Analysed! ${res.skills_found} skills found, ${res.words} words.`;
      setTimeout(() => { closeModal(); go("matches"); }, 1100);
    } catch (ex) { msg.textContent = ex.message; }
  }

  /* ---- match detail ---- */
  async function openMatch(id) {
    const d = await api("/api/match/" + id);
    const s = d.summary;
    modal(`${s.candidate} → ${s.job_title}`, `
      <div class="score-grid">
        ${[["Final", s.final_score], ["Skills", s.skill_score], ["TF-IDF (NLP)", s.tfidf_score],
           ["Embedding (AI)", s.embedding_score ?? "—"]].map(([t, n]) =>
          `<div class="score-box"><div class="n">${esc(n)}</div><div class="t">${esc(t)}</div></div>`).join("")}
      </div>
      <div class="sec-title" style="color:#16a34a">✓ Matched skills (${d.matched.length})</div>
      <div class="chip-wrap">${d.matched.map(m => `<span class="chip match">${esc(m)}</span>`).join("") || '<span class="muted">none</span>'}</div>
      <div class="sec-title" style="color:#dc2626">✗ Missing skills (${d.missing.length})</div>
      <div class="chip-wrap">${d.missing.map(m => `<span class="chip miss">${esc(m)}</span>`).join("") || '<span class="muted">none — perfect match!</span>'}</div>
      ${d.resume_text ? `<div class="sec-title">Resume text</div>
        <div class="sql-result" style="max-height:200px"><pre style="margin:0;padding:14px;white-space:pre-wrap;font-size:12px;color:var(--muted)">${esc(d.resume_text)}</pre></div>` : ""}`);
  }

  /* ================= INIT ================= */
  function bindAuth() {
    $$(".auth-tab").forEach(b => b.onclick = () => {
      $$(".auth-tab").forEach(x => x.classList.toggle("active", x === b));
      $("#loginForm").style.display = b.dataset.auth === "login" ? "block" : "none";
      $("#regForm").style.display = b.dataset.auth === "register" ? "block" : "none";
      $("#loginErr").textContent = ""; $("#regErr").textContent = "";
    });
    document.addEventListener("click", (e) => {
      const b = e.target.closest(".pw-toggle");
      if (!b) return;
      const inp = $("#" + b.dataset.pw);
      if (!inp) return;
      const show = inp.type === "password";
      inp.type = show ? "text" : "password";
      b.textContent = show ? "🙈" : "👁";
    });
    const syncRole = () => {
      const isCompany = $('input[name="role"]:checked').value === "company";
      $("#companyFields").style.display = isCompany ? "block" : "none";
      $("#candidateFields").style.display = isCompany ? "none" : "block";
      $("#nameLabel").textContent = isCompany ? "HR / Contact name *" : "Full name *";
      $("#regName").placeholder = isCompany ? "HR contact person name" : "Your name";
    };
    $$('input[name="role"]').forEach(r => r.onchange = syncRole);
    syncRole();
    $$(".demo-chip").forEach(b => b.onclick = () => {
      $$(".auth-tab").forEach(x => x.classList.toggle("active", x.dataset.auth === "login"));
      $("#loginForm").style.display = "block";
      $("#regForm").style.display = "none";
      $("#loginId").value = b.dataset.demo;
      $("#loginPw").value = "password123";
      $("#loginId").focus();
    });
    $("#loginForm").addEventListener("submit", doLogin);
    $("#regForm").addEventListener("submit", doRegister);
    $("#btnLogout").onclick = logout;
    $("#modal").addEventListener("click", e => { if (e.target.id === "modal") closeModal(); });
    document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });
  }

  async function init() {
    bindAuth();
    try {
      const me = await api("/api/me");
      if (me.user) { ME = me.user; PROFILE = me.profile; showApp(); }
      else showAuth();
    } catch { showAuth(); }
  }
  document.addEventListener("DOMContentLoaded", init);

  return { go, closeModal, openMatch, toast, preview: null,
           _applyFromModal: (id) => applyJob(id) };
})();
window.App = App;
