import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Link, useNavigate, useParams, Navigate, useLocation } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import { BarChart3, Building2, Check, CheckCircle2, ChevronRight, Circle, CircleDot, ClipboardList, Copy, ExternalLink, FilePlus2, LayoutDashboard, ListTodo, LogOut, MapPin, Menu, MessageSquare, Plus, RefreshCw, Settings, Sparkles, Star, Trash2, Users, X } from "lucide-react";
import axios from "axios";
import "@/App.css";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const api = axios.create({ baseURL: API });
api.interceptors.request.use(c => { const t = localStorage.getItem("feedback_token"); if (t) c.headers.Authorization = `Bearer ${t}`; return c; });
const errorText = e => { const d = e?.response?.data?.detail; return Array.isArray(d) ? d.map(x => x.msg).join(" ") : d || "Something went wrong. Please try again."; };
const fmtDate = d => new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });

/* ===== Auth ===== */
function Auth({ onAuth }) {
  const nav = useNavigate();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const submit = async e => {
    e.preventDefault(); setError("");
    try {
      const r = await api.post(`/auth/${mode}`, form);
      localStorage.setItem("feedback_token", r.data.access_token);
      onAuth(r.data.user); nav("/dashboard");
    } catch (x) { setError(errorText(x)); }
  };
  return (
    <main className="auth-shell">
      <div className="auth-copy">
        <div className="brand-mark">F<span>•</span></div>
        <p className="eyebrow">Customer feedback, made useful</p>
        <h1>Hear the signal.<br/><em>Grow with confidence.</em></h1>
        <p className="auth-intro">A calmer way to collect honest feedback, understand every response, and keep customers close.</p>
        <div className="signal-row"><span><b>01</b> Create</span><span><b>02</b> Share</span><span><b>03</b> Understand</span></div>
      </div>
      <section className="auth-panel">
        <div className="auth-tabs">
          <button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")} data-testid="login-tab">Sign in</button>
          <button className={mode === "register" ? "active" : ""} onClick={() => setMode("register")} data-testid="register-tab">Create account</button>
        </div>
        <h2>{mode === "login" ? "Welcome back" : "Start collecting better feedback"}</h2>
        <p className="muted">{mode === "login" ? "Sign in to your feedback workspace." : "Set up your workspace in a few minutes."}</p>
        <form onSubmit={submit}>
          {mode === "register" && <label>Full name<input data-testid="register-name" required value={form.full_name} onChange={e => setForm({ ...form, full_name: e.target.value })} placeholder="Alex Morgan" /></label>}
          <label>Email address<input data-testid="auth-email" required type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} placeholder="you@company.com" /></label>
          <label>Password<input data-testid="auth-password" required type="password" minLength="8" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} placeholder="At least 8 characters" /></label>
          {error && <div className="error" data-testid="auth-error">{error}</div>}
          <button className="primary wide" data-testid="auth-submit">{mode === "login" ? "Sign in" : "Create account"}<ChevronRight size={17} /></button>
        </form>
      </section>
    </main>
  );
}

/* ===== Shell ===== */
function Shell({ user, children, onLogout }) {
  const loc = useLocation();
  const [mobile, setMobile] = useState(false);
  const nav = [
    ["/dashboard", "Overview", LayoutDashboard],
    ["/templates", "Templates", ClipboardList],
    ["/responses", "Responses", MessageSquare],
    ["/actions", "Actions", ListTodo],
    ["/analytics", "Analytics", BarChart3],
    ["/team", "Team", Users],
    ["/locations", "Locations", MapPin],
    ["/settings/business", "Business settings", Settings],
  ];
  return (
    <div className="app-shell">
      <aside className={mobile ? "sidebar open" : "sidebar"}>
        <div className="side-top">
          <Link to="/dashboard" className="brand"><span className="brand-mark small">F<span>•</span></span><span>feedback<span className="brand-dot">/</span>loop</span></Link>
          <button className="icon-btn mobile-close" onClick={() => setMobile(false)}><X size={18} /></button>
        </div>
        <div className="workspace-switch">
          <div className="workspace-avatar">{user?.full_name?.[0] || "A"}</div>
          <div><strong>{user?.full_name || "Workspace owner"}</strong><small>Owner workspace</small></div>
          <ChevronRight size={15} />
        </div>
        <nav>{nav.map(([href, label, Icon]) => <Link key={href} to={href} onClick={() => setMobile(false)} className={loc.pathname.startsWith(href) ? "nav-link selected" : "nav-link"} data-testid={`nav-${label.toLowerCase().replaceAll(" ", "-")}`}><Icon size={18} /><span>{label}</span></Link>)}</nav>
        <div className="side-bottom">
          <div className="help-note"><span className="help-dot"></span><div><b>Keep listening</b><small>Share your link to start collecting.</small></div></div>
          <button className="nav-link logout" onClick={onLogout} data-testid="logout-button"><LogOut size={18} /> Sign out</button>
        </div>
      </aside>
      <div className="main-area">
        <header className="topbar">
          <button className="icon-btn menu-btn" onClick={() => setMobile(true)}><Menu size={21} /></button>
          <div className="breadcrumbs">Workspace <span>/</span> {loc.pathname.includes("templates") ? "Templates" : loc.pathname.includes("responses") ? "Responses" : loc.pathname.includes("analytics") ? "Analytics" : loc.pathname.includes("team") ? "Team" : loc.pathname.includes("locations") ? "Locations" : loc.pathname.includes("settings") ? "Settings" : "Overview"}</div>
          <div className="top-actions"><span className="live-indicator"><i></i> Workspace live</span><div className="profile-chip"><span>{user?.full_name?.[0] || "A"}</span>{user?.full_name}</div></div>
        </header>
        <div className="content">{children}</div>
      </div>
    </div>
  );
}

/* ===== Shared bits ===== */
function PageTitle({ eyebrow, title, desc, action }) { return <div className="page-title"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="muted">{desc}</p></div>{action}</div>; }
function Empty({ icon: Icon, title, text, action, href }) { return <div className="empty"><div className="empty-icon"><Icon size={22} /></div><h3>{title}</h3><p>{text}</p>{href && <Link className="outline" to={href}><Plus size={16} />{action}</Link>}</div>; }
function Loading() { return <div className="loading"><div className="loader"></div>Loading your workspace…</div>; }
function Protected({ user, children }) { return user ? children : <Navigate to="/login" replace />; }
function SentimentBadge({ sentiment, size = "sm" }) {
  if (!sentiment || sentiment === "unknown") return null;
  const map = { positive: ["Positive", "pos"], neutral: ["Neutral", "neu"], negative: ["Needs attention", "neg"] };
  const [label, cls] = map[sentiment] || [sentiment, "neu"];
  return <span className={`sentiment-badge ${cls} ${size}`} data-testid={`sentiment-${sentiment}`}><Sparkles size={11} /> {label}</span>;
}
function RatingStars({ n }) { if (n == null) return <span className="stars">—</span>; const v = Math.min(5, Math.max(0, Number(n))); return <span className="stars">{"★".repeat(v)}{"☆".repeat(5 - v)}</span>; }
function responseRating(r) { const found = r.answers.find(a => typeof a.value === "number" && a.value >= 1 && a.value <= 5); return found ? Number(found.value) : null; }
function responseComment(r) { const found = r.answers.find(a => typeof a.value === "string" && a.value.length > 8); return found?.value || ""; }

function ResponseRow({ r, index, clickable }) {
  const nav = useNavigate();
  const rating = responseRating(r);
  const comment = responseComment(r);
  const sentiment = r.ai?.sentiment;
  return (
    <div className={`response-row ${clickable ? "clickable" : ""}`} onClick={() => clickable && nav(`/responses/${r.id}`)} data-testid={`response-row-${index}`}>
      <div className="response-avatar">{String.fromCharCode(65 + (index % 20))}</div>
      <div className="response-main">
        <strong>Anonymous customer</strong>
        <span>{fmtDate(r.submitted_at)}</span>
      </div>
      <div className="response-comment">{comment || "Rating submitted"}{sentiment && <SentimentBadge sentiment={sentiment} />}</div>
      <RatingStars n={rating} />
    </div>
  );
}

/* ===== Dashboard ===== */
function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.get("/dashboard/summary").then(r => setData(r.data)).finally(() => setLoading(false)); }, []);
  if (loading) return <Loading />;
  if (!data.workspace) return <Onboarding />;
  const cards = [
    ["Templates", data.templates, ClipboardList, "neutral"],
    ["Published", data.published, ExternalLink, "green"],
    ["Responses", data.responses, MessageSquare, "orange"],
    ["Average rating", data.average_rating ? `${data.average_rating}/5` : "—", Star, "yellow"],
  ];
  const sent = data.sentiment || { positive: 0, neutral: 0, negative: 0 };
  const totalSent = sent.positive + sent.neutral + sent.negative;
  return (
    <>
      <PageTitle eyebrow="Workspace overview" title="Good feedback starts here." desc="A clear view of what your customers are telling you." action={<Link className="primary" to="/templates/new" data-testid="dashboard-create-template"><Plus size={17} /> Create template</Link>} />
      <div className="metric-grid">{cards.map(([t, v, I, c]) => <div className="metric" key={t} data-testid={`metric-${t.toLowerCase().replaceAll(" ", "-")}`}><div className={`metric-icon ${c}`}><I size={18} /></div><span>{t}</span><strong>{v}</strong><small>{t === "Responses" ? "from customer feedback" : "this workspace"}</small></div>)}</div>
      <div className="dashboard-grid">
        <section className="section-panel recent-panel">
          <div className="panel-head">
            <div><p className="eyebrow">Latest activity</p><h3>Recent responses</h3></div>
            <Link to="/responses" className="text-link">View all <ChevronRight size={15} /></Link>
          </div>
          {data.recent.length
            ? <div className="response-list">{data.recent.map((r, i) => <ResponseRow key={r.id} r={r} index={i} clickable />)}</div>
            : <Empty icon={MessageSquare} title="No customer responses yet" text="Publish a feedback page and share it with your customers to begin." action="Create a template" href="/templates/new" />}
        </section>
        <section className="section-panel sentiment-panel" data-testid="sentiment-panel">
          <div className="panel-head"><div><p className="eyebrow">AI signal</p><h3>Sentiment pulse</h3></div><Sparkles size={18} /></div>
          {totalSent === 0
            ? <p className="muted sentiment-empty">Written feedback is auto-analyzed to spot what's loved and what needs attention.</p>
            : <div className="sentiment-bars">
                {[["positive", "Positive", "#54a978"], ["neutral", "Neutral", "#c1cec8"], ["negative", "Needs attention", "#d87567"]].map(([k, label, color]) => <div key={k} className="sentiment-bar"><span>{label}</span><div className="track"><div style={{ width: `${(sent[k] / totalSent) * 100}%`, background: color }} /></div><b>{sent[k]}</b></div>)}
              </div>}
          <div className="focus-foot"><Sparkles size={13} /> Powered by Emergent LLM</div>
        </section>
      </div>
    </>
  );
}

/* ===== Onboarding ===== */
function Onboarding() {
  const [name, setName] = useState("");
  const [type, setType] = useState("Restaurant");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const submit = async e => {
    e.preventDefault(); setSaving(true); setError("");
    try { await api.post("/workspaces", { name, business_type: type }); window.location.assign("/dashboard"); }
    catch (x) { setError(errorText(x)); setSaving(false); }
  };
  return (
    <div className="onboarding">
      <div className="onboard-number">01 / 01</div>
      <p className="eyebrow">One quick setup</p>
      <h1>Create your business workspace.</h1>
      <p className="muted big">This is where your templates, responses, and customer insights will live.</p>
      <form onSubmit={submit} className="onboard-form">
        <label>Business name<input data-testid="workspace-name" required value={name} onChange={e => setName(e.target.value)} placeholder="ABC Restaurant" /></label>
        <label>Business type<select data-testid="workspace-type" value={type} onChange={e => setType(e.target.value)}><option>Restaurant</option><option>Retail</option><option>Professional services</option><option>Other</option></select></label>
        {error && <div className="error">{error}</div>}
        <button className="primary" disabled={saving} data-testid="workspace-submit">{saving ? "Creating workspace…" : "Create workspace"} <ChevronRight size={17} /></button>
      </form>
    </div>
  );
}

/* ===== Templates list ===== */
function Templates() {
  const [items, setItems] = useState([]);
  useEffect(() => { api.get("/templates").then(r => setItems(r.data)); }, []);
  return (
    <div className="templates-bg">
      <PageTitle eyebrow="Feedback library" title="Templates" desc="Create a focused way for customers to share what matters." action={<Link className="primary" to="/templates/new" data-testid="create-template-button"><Plus size={17} /> New template</Link>} />
      {items.length
        ? <div className="template-grid">{items.map(t => <TemplateCard key={t.id} t={t} />)}</div>
        : <div className="empty-large"><div className="empty-icon"><ClipboardList size={24} /></div><h3>You haven't created a feedback template yet.</h3><p>Start from a proven format or build your own questions.</p><Link className="primary" to="/templates/new" data-testid="empty-create-template"><Plus size={17} /> Create template</Link></div>}
    </div>
  );
}
function TemplateCard({ t }) {
  const nav = useNavigate();
  return (
    <article className="template-card" data-testid={`template-card-${t.id}`}>
      <div className="template-card-top">
        <span className={t.status === "PUBLISHED" ? "status published" : "status"}>{t.status === "PUBLISHED" ? <><span className="status-dot"></span> Live</> : "Draft"}</span>
        <button className="icon-btn" onClick={() => nav(`/templates/${t.id}/edit`)} data-testid={`edit-template-${t.id}`}><ChevronRight size={18} /></button>
      </div>
      <h3>{t.name}</h3>
      <p>{t.description || "A customer feedback form ready to shape."}</p>
      <div className="template-meta">
        <span><ClipboardList size={14} /> {t.questions.length} questions</span>
        {t.status === "PUBLISHED" && <Link to={`/f/${t.public_slug}`} target="_blank" className="text-link">Open page <ExternalLink size={13} /></Link>}
      </div>
    </article>
  );
}

/* ===== Template builder ===== */
function TemplateBuilder() {
  const { id } = useParams();
  const nav = useNavigate();
  const [presets, setPresets] = useState([]);
  const [locations, setLocations] = useState([]);
  const [form, setForm] = useState({ name: "", description: "", questions: [], location_id: null });
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api.get("/templates/presets").then(r => setPresets(r.data));
    api.get("/locations").then(r => setLocations(r.data));
    if (id) api.get(`/templates/${id}`).then(r => setForm(r.data));
  }, [id]);
  const addQuestion = (type = "rating") => setForm({ ...form, questions: [...form.questions, { question_text: type === "yesno" ? "Would you recommend us?" : "How was your overall experience?", question_type: type, required: true, description: "", options: type === "yesno" ? ["Yes", "No"] : [] }] });
  const save = async () => {
    try {
      const payload = { ...form, questions: form.questions.map(({ id: _ignore, ...q }) => q) };
      const r = id ? await api.patch(`/templates/${id}`, payload) : await api.post("/templates", payload);
      if (!id) nav(`/templates/${r.data.id}/edit`);
      setForm(r.data); return r.data;
    } catch (x) { setError(errorText(x)); return null; }
  };
  const publish = async () => { const saved = await save(); const target = saved?.id || form.id || id; if (!target) return; const r = await api.post(`/templates/${target}/publish`); nav(`/templates/${r.data.id}/publish`); };
  const choosePreset = async name => { const r = await api.post(`/templates/from-preset/${encodeURIComponent(name)}`); nav(`/templates/${r.data.id}/edit`); setForm(r.data); };
  const updateQuestion = (i, patch) => { const qs = [...form.questions]; qs[i] = { ...qs[i], ...patch }; setForm({ ...form, questions: qs }); };
  const removeQuestion = i => setForm({ ...form, questions: form.questions.filter((_, n) => n !== i) });
  return (
    <>
      <PageTitle eyebrow="Template builder" title={id ? "Shape the questions." : "What would you like to ask?"} desc="Keep it focused. The best forms are easy to finish and easy to act on." action={<div className="button-row"><button className="outline" onClick={save} data-testid="save-template-button">Save draft</button><button className="primary" onClick={publish} data-testid="publish-template-button">Publish <ExternalLink size={16} /></button></div>} />
      <div className="builder-layout">
        <aside className="builder-library">
          <p className="eyebrow">Start with a format</p>
          <button className="preset-scratch" onClick={() => addQuestion()} data-testid="start-from-scratch"><Plus size={18} /><span><b>Start from scratch</b><small>Build your own form</small></span></button>
          {presets.map(p => <button className="preset" key={p.name} onClick={() => choosePreset(p.name)} data-testid={`preset-${p.name.toLowerCase().replaceAll(" ", "-")}`}><span className="preset-mark">{p.name[0]}</span><span><b>{p.name}</b><small>{p.question_count} thoughtful questions</small></span><ChevronRight size={15} /></button>)}
          {locations.length > 0 && (
            <div className="location-pick">
              <p className="eyebrow">Attach location</p>
              <select value={form.location_id || ""} onChange={e => setForm({ ...form, location_id: e.target.value || null })} data-testid="template-location-select">
                <option value="">Any location</option>
                {locations.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
            </div>
          )}
        </aside>
        <section className="builder-canvas">
          <div className="builder-heading">
            <input className="title-input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Untitled feedback form" data-testid="template-name-input" />
            <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="Add a short description for customers..." data-testid="template-description-input" />
          </div>
          {form.questions.map((q, i) => (
            <div className={`question-editor ${selected === i ? "focused" : ""}`} key={q.id || i} onClick={() => setSelected(i)} data-testid={`question-editor-${i}`}>
              <div className="drag-handle">⠿</div>
              <div className="question-content">
                <div className="question-top">
                  <span className="question-number">{String(i + 1).padStart(2, "0")}</span>
                  <select value={q.question_type} onChange={e => updateQuestion(i, { question_type: e.target.value })} data-testid={`question-type-${i}`}>
                    <option value="rating">Star rating</option>
                    <option value="yesno">Yes / No</option>
                    <option value="shorttext">Short text</option>
                    <option value="longtext">Long text</option>
                  </select>
                  <button className="icon-btn danger" onClick={e => { e.stopPropagation(); removeQuestion(i); }} data-testid={`delete-question-${i}`}><Trash2 size={15} /></button>
                </div>
                <input value={q.question_text} onChange={e => updateQuestion(i, { question_text: e.target.value })} data-testid={`question-text-${i}`} />
                <div className="question-preview">{q.question_type === "rating" ? "☆ ☆ ☆ ☆ ☆" : q.question_type === "yesno" ? "Yes     No" : q.question_type === "longtext" ? "Your answer..." : "Short answer"}</div>
                <label className="required-toggle"><input type="checkbox" checked={q.required} onChange={e => updateQuestion(i, { required: e.target.checked })} /> Required</label>
              </div>
            </div>
          ))}
          <button className="add-question" onClick={() => addQuestion()} data-testid="add-question-button"><Plus size={18} /> Add question</button>
          {!form.questions.length && <div className="builder-empty"><ClipboardList size={28} /><p>Your questions will appear here</p><small>Choose a format or add your first question</small></div>}
          {error && <div className="error">{error}</div>}
        </section>
        <aside className="builder-preview">
          <div className="preview-label"><span>Live preview</span><span className="live-dot">●</span></div>
          <div className="phone-preview">
            <div className="phone-head"><div className="preview-logo">F</div><b>{form.name || "Your feedback form"}</b></div>
            <p>{form.description || "We'd love to hear about your experience."}</p>
            {form.questions.slice(0, 4).map((q, i) => <div className="preview-question" key={i}><b>{q.question_text || "Your question"}</b><span>{q.question_type === "rating" ? "☆ ☆ ☆ ☆ ☆" : q.question_type === "yesno" ? "Yes     No" : "Your answer..."}</span></div>)}
            <button className="preview-submit">Submit feedback</button>
          </div>
        </aside>
      </div>
    </>
  );
}

/* ===== Publish page ===== */
function PublishPage() {
  const { id } = useParams();
  const [t, setT] = useState(null);
  useEffect(() => { api.get(`/templates/${id}`).then(r => setT(r.data)); }, [id]);
  if (!t) return <Loading />;
  const url = `${window.location.origin}/f/${t.public_slug}`;
  return (
    <div className="publish-page">
      <div className="publish-check"><Check size={25} /></div>
      <p className="eyebrow">Published successfully</p>
      <h1>Your feedback page is live.</h1>
      <p className="muted big">Share this link wherever your customers meet you.</p>
      <div className="share-layout">
        <section className="share-card">
          <span className="eyebrow">Public link</span>
          <div className="url-box"><span data-testid="public-url-text">{url}</span><button className="icon-btn" onClick={() => navigator.clipboard.writeText(url)} data-testid="copy-public-link"><Copy size={16} /></button></div>
          <div className="button-row">
            <a className="primary" href={url} target="_blank" rel="noreferrer" data-testid="open-public-feedback"><ExternalLink size={16} /> Open page</a>
            <Link className="outline" to="/templates"><ClipboardList size={16} /> Back to templates</Link>
          </div>
        </section>
        <section className="qr-card">
          <QRCodeSVG value={url} size={156} bgColor="#ffffff" fgColor="#17352d" includeMargin data-testid="feedback-qr-code" />
          <span>Scan to open your form</span>
        </section>
      </div>
    </div>
  );
}

/* ===== Public feedback page ===== */
function PublicFeedback() {
  const { slug } = useParams();
  const [data, setData] = useState(null);
  const [answers, setAnswers] = useState({});
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { api.get(`/public/feedback/${slug}`).then(r => setData(r.data)).catch(() => setError("This feedback page is no longer available.")); }, [slug]);
  if (error && !data) return <div className="public-shell"><div className="thank-you"><X size={28} /><h1>{error}</h1></div></div>;
  if (!data) return <Loading />;
  const t = data.template;
  const set = (id, v) => setAnswers({ ...answers, [id]: v });
  const submit = async () => {
    try { await api.post(`/public/feedback/${slug}/responses`, { answers: Object.entries(answers).map(([question_id, value]) => ({ question_id, value })) }); setDone(true); }
    catch (x) { setError(errorText(x)); }
  };
  if (done) return (
    <div className="public-shell">
      <div className="public-brand">F<span>•</span> feedback loop</div>
      <div className="thank-you">
        <div className="publish-check"><Check size={27} /></div>
        <p className="eyebrow">Received with thanks</p>
        <h1>Your feedback has been submitted.</h1>
        <p>Thanks for helping {data.business?.name || "this business"} make the next experience even better.</p>
      </div>
    </div>
  );
  return (
    <div className="public-shell">
      <div className="public-brand">F<span>•</span> feedback loop</div>
      <main className="feedback-form">
        <div className="business-kicker">
          <div className="business-logo">{data.business?.name?.[0] || "B"}</div>
          <span>{data.business?.name}{data.location && <small className="loc-chip"> · {data.location.name}</small>}</span>
        </div>
        <p className="eyebrow">A few honest minutes</p>
        <h1>{t.name}</h1>
        <p className="public-description">{t.description || "We'd love to hear about your experience."}</p>
        <div className="public-questions">
          {t.questions.map((q, i) => (
            <div className="public-question" key={q.id}>
              <label><span>{i + 1}. </span>{q.question_text}{q.required && <sup>*</sup>}</label>
              {q.description && <small>{q.description}</small>}
              {q.question_type === "rating"
                ? <div className="rating-buttons">{[1, 2, 3, 4, 5].map(n => <button className={answers[q.id] === n ? "rating selected" : "rating"} onClick={() => set(q.id, n)} data-testid={`rating-${q.id}-${n}`} key={n}>{n}<Star size={16} fill={answers[q.id] === n ? "currentColor" : "none"} /></button>)}</div>
                : q.question_type === "yesno"
                  ? <div className="choice-buttons">{["Yes", "No"].map(v => <button className={answers[q.id] === v ? "choice selected" : "choice"} onClick={() => set(q.id, v)} data-testid={`choice-${q.id}-${v.toLowerCase()}`} key={v}>{v}{answers[q.id] === v && <Check size={15} />}</button>)}</div>
                  : q.question_type === "longtext"
                    ? <textarea value={answers[q.id] || ""} onChange={e => set(q.id, e.target.value)} placeholder="Share a little more, if you'd like..." data-testid={`answer-${q.id}`} />
                    : <input value={answers[q.id] || ""} onChange={e => set(q.id, e.target.value)} placeholder="Your answer" data-testid={`answer-${q.id}`} />}
            </div>
          ))}
        </div>
        {error && <div className="error" data-testid="feedback-error">{error}</div>}
        <button className="primary submit-feedback" onClick={submit} data-testid="submit-feedback">Submit feedback <ChevronRight size={17} /></button>
        <span className="privacy-note">Your response is anonymous and private.</span>
      </main>
    </div>
  );
}

/* ===== Responses list ===== */
function Responses() {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("all");
  useEffect(() => { api.get("/responses").then(r => setItems(r.data)); }, []);
  const filtered = filter === "all" ? items : items.filter(r => r.ai?.sentiment === filter);
  return (
    <>
      <PageTitle eyebrow="Customer voice" title="Responses" desc="Read every response in one calm, searchable place." action={
        <div className="filter-pills">
          {[["all", "All"], ["positive", "Positive"], ["neutral", "Neutral"], ["negative", "Attention"]].map(([k, l]) => <button key={k} className={filter === k ? "pill active" : "pill"} onClick={() => setFilter(k)} data-testid={`filter-${k}`}>{l}</button>)}
        </div>
      } />
      <section className="section-panel table-panel">
        {filtered.length
          ? <div className="response-table"><div className="table-head"><span>Response</span><span>Sentiment</span><span>Submitted</span><span>Rating</span></div>{filtered.map((r, i) => <ResponseRow key={r.id} r={r} index={i} clickable />)}</div>
          : <Empty icon={MessageSquare} title="No responses here yet." text={filter === "all" ? "Your first response will appear here after a customer completes your form." : "No responses match this filter yet."} action="Create a template" href="/templates/new" />}
      </section>
    </>
  );
}

/* ===== Response detail ===== */
function ResponseDetail() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [note, setNote] = useState("");
  const [notes, setNotes] = useState([]);
  const [noteError, setNoteError] = useState("");
  const load = () => api.get(`/responses/${id}`).then(r => { setData(r.data); setNotes(r.data.response.notes || []); });
  useEffect(() => { load(); }, [id]);
  if (!data) return <Loading />;
  const r = data.response; const t = data.template; const ai = r.ai || {};
  const qmap = Object.fromEntries((t?.questions || []).map(q => [q.id, q]));
  const reanalyze = async () => { setRefreshing(true); await api.post(`/responses/${id}/reanalyze`); setTimeout(() => { load(); setRefreshing(false); }, 2500); };
  const addNote = async e => {
    e.preventDefault(); setNoteError("");
    try { const r = await api.post(`/responses/${id}/notes`, { text: note }); setNotes([...notes, r.data]); setNote(""); }
    catch (x) { setNoteError(errorText(x)); }
  };
  const deleteNote = async nid => { if (window.confirm("Delete this note?")) { await api.delete(`/responses/${id}/notes/${nid}`); setNotes(notes.filter(n => n.id !== nid)); } };
  return (
    <>
      <PageTitle eyebrow="Customer response" title={t?.name || "Response"} desc={`Submitted ${new Date(r.submitted_at).toLocaleString()}${data.location ? ` · ${data.location.name}` : ""}`} action={<Link to="/responses" className="outline"><ChevronRight size={16} style={{ transform: "rotate(180deg)" }} /> All responses</Link>} />
      <div className="detail-layout">
        <section className="section-panel detail-panel">
          {r.answers.map((a, i) => {
            const q = qmap[a.question_id]; if (!q) return null;
            return (
              <div className="detail-answer" key={a.id} data-testid={`answer-${i}`}>
                <div className="detail-q"><span>{String(i + 1).padStart(2, "0")}</span><b>{q.question_text}</b></div>
                <div className="detail-a">
                  {q.question_type === "rating" ? <RatingStars n={a.value} />
                    : q.question_type === "yesno" ? <span className={a.value === "Yes" ? "pill pos" : "pill neu"}>{a.value}</span>
                      : <p className="detail-text">{a.value}</p>}
                </div>
              </div>
            );
          })}
          <div className="notes-section" data-testid="notes-section">
            <div className="panel-head"><div><p className="eyebrow">Team notes</p><h3>Private to your team</h3></div><MessageSquare size={16} /></div>
            <div className="notes-list">
              {notes.length ? notes.map(n => (
                <div className="note-row" key={n.id} data-testid={`note-${n.id}`}>
                  <div className="note-avatar">{n.user_name?.[0] || "T"}</div>
                  <div className="note-body"><strong>{n.user_name}</strong><small>{new Date(n.created_at).toLocaleString()}</small><p>{n.text}</p></div>
                  <button className="icon-btn danger" onClick={() => deleteNote(n.id)} data-testid={`delete-note-${n.id}`}><Trash2 size={13} /></button>
                </div>
              )) : <p className="muted notes-empty">No notes yet. Add a quick line so your team knows what you've done about this response.</p>}
            </div>
            <form onSubmit={addNote} className="note-form">
              <textarea value={note} onChange={e => setNote(e.target.value)} placeholder="e.g. Called the customer, offered a free dessert on their next visit." data-testid="note-input" />
              {noteError && <div className="error">{noteError}</div>}
              <button className="primary" disabled={!note.trim()} data-testid="add-note-button">Add note <ChevronRight size={14} /></button>
            </form>
          </div>
        </section>
        <aside className="section-panel ai-panel" data-testid="ai-panel">
          <div className="panel-head">
            <div><p className="eyebrow">AI insight</p><h3>What this says</h3></div>
            <button className="icon-btn" onClick={reanalyze} title="Re-analyze" data-testid="reanalyze-button"><RefreshCw size={15} className={refreshing ? "spinning" : ""} /></button>
          </div>
          {ai.sentiment && ai.sentiment !== "unknown"
            ? <>
                <SentimentBadge sentiment={ai.sentiment} size="lg" />
                {ai.summary && <p className="ai-summary">{ai.summary}</p>}
                {ai.topics?.length > 0 && <div className="ai-topics">{ai.topics.map(t => <span key={t} className="topic-chip">{t}</span>)}</div>}
                {ai.confidence > 0 && <small className="ai-confidence">Confidence {Math.round(ai.confidence * 100)}%</small>}
              </>
            : <p className="muted">{refreshing ? "Analyzing with AI..." : "No written feedback to analyze, or analysis pending."}</p>}
          <div className="focus-foot"><Sparkles size={13} /> Powered by Emergent LLM</div>
        </aside>
      </div>
    </>
  );
}

/* ===== Analytics ===== */
function Analytics() {
  const [d, setD] = useState(null);
  const [byLoc, setByLoc] = useState([]);
  const [locations, setLocations] = useState([]);
  const [filter, setFilter] = useState("");
  const load = (locId) => {
    const q = locId ? `?location_id=${locId}` : "";
    api.get(`/analytics${q}`).then(r => setD(r.data));
  };
  useEffect(() => {
    load("");
    api.get("/locations").then(r => setLocations(r.data));
    api.get("/analytics/by-location").then(r => setByLoc(r.data));
  }, []);
  useEffect(() => { load(filter); }, [filter]);
  if (!d) return <Loading />;
  const sent = d.sentiment || { positive: 0, neutral: 0, negative: 0 };
  const totalSent = sent.positive + sent.neutral + sent.negative;
  return (
    <>
      <PageTitle eyebrow="Understand the signal" title="Analytics" desc="Simple patterns from the feedback you've collected." action={
        locations.length > 0 && (
          <select className="loc-filter" value={filter} onChange={e => setFilter(e.target.value)} data-testid="analytics-location-filter">
            <option value="">All locations</option>
            {locations.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        )
      } />
      <div className="analytics-top">
        <div className="metric"><span>Total responses</span><strong>{d.total}</strong><small>{filter ? "this location" : "all time"}</small></div>
        <div className="metric"><span>Average rating</span><strong>{d.average || "—"}</strong><small>out of 5</small></div>
        <div className="metric"><span>5-star share</span><strong>{d.total ? Math.round(d.distribution[5] / d.total * 100) : 0}%</strong><small>of ratings</small></div>
      </div>
      <div className="analytics-grid">
        <section className="section-panel chart-panel">
          <div className="panel-head"><div><p className="eyebrow">Rating distribution</p><h3>How customers feel</h3></div></div>
          <div className="bars">
            {[5, 4, 3, 2, 1].map(n => <div className="bar-row" key={n}><span>{n} <Star size={13} fill="currentColor" /></span><div className="bar-track"><div className={`bar-fill rating-${n}`} style={{ width: `${d.total ? Math.max(4, d.distribution[n] / Math.max(...Object.values(d.distribution), 1) * 100) : 4}%` }}></div></div><b>{d.distribution[n]}</b></div>)}
          </div>
          {!d.total && <p className="muted chart-empty">Analytics will appear after customers submit feedback.</p>}
        </section>
        <section className="section-panel chart-panel ai-chart" data-testid="ai-chart">
          <div className="panel-head"><div><p className="eyebrow">AI sentiment</p><h3>What they said</h3></div><Sparkles size={18} /></div>
          {totalSent === 0
            ? <p className="muted chart-empty">Write-in feedback is auto-analyzed and summarized here.</p>
            : <>
                <div className="sentiment-bars">{[["positive", "Positive", "#54a978"], ["neutral", "Neutral", "#c1cec8"], ["negative", "Needs attention", "#d87567"]].map(([k, label, color]) => <div key={k} className="sentiment-bar"><span>{label}</span><div className="track"><div style={{ width: `${(sent[k] / totalSent) * 100}%`, background: color }} /></div><b>{sent[k]}</b></div>)}</div>
                {d.topics?.length > 0 && <div className="ai-topics big"><p className="eyebrow">Top topics</p><div>{d.topics.map(t => <span key={t.name} className="topic-chip">{t.name} <small>{t.count}</small></span>)}</div></div>}
              </>}
        </section>
      </div>
      {byLoc.length > 1 && (
        <section className="section-panel location-breakdown" data-testid="location-breakdown">
          <div className="panel-head"><div><p className="eyebrow">By location</p><h3>Where feedback is coming from</h3></div><MapPin size={18} /></div>
          <div className="loc-grid">
            {byLoc.map(b => (
              <div className="loc-stat" key={b.location_id || "none"} data-testid={`loc-stat-${b.location_id || "none"}`}>
                <div className="loc-stat-head"><MapPin size={14} /><strong>{b.location?.name || "Unassigned"}</strong></div>
                <div className="loc-stat-nums"><span><b>{b.total}</b><small>responses</small></span><span><b>{b.average || "—"}</b><small>avg rating</small></span></div>
                <div className="loc-stat-sent">
                  <span className="dot pos"></span>{b.sentiment.positive}
                  <span className="dot neu"></span>{b.sentiment.neutral}
                  <span className="dot neg"></span>{b.sentiment.negative}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </>
  );
}

/* ===== Team ===== */
function Team() {
  const [data, setData] = useState(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("editor");
  const [error, setError] = useState("");
  const [sentMsg, setSentMsg] = useState("");
  const load = () => api.get("/team/members").then(r => setData(r.data));
  useEffect(() => { load(); }, []);
  if (!data) return <Loading />;
  const canManage = data.role === "owner";
  const invite = async e => {
    e.preventDefault(); setError(""); setSentMsg("");
    try {
      const r = await api.post("/team/invites", { email, role });
      setEmail("");
      setSentMsg(r.data.email_sent ? `Invitation emailed to ${r.data.invite_email}` : `Invite link ready — share: ${window.location.origin}${r.data.link.startsWith("http") ? new URL(r.data.link).pathname : r.data.link}`);
      load();
    } catch (x) { setError(errorText(x)); }
  };
  const copyInvite = inv => { navigator.clipboard.writeText(`${window.location.origin}/invite/${inv.token}`); setSentMsg("Invite link copied"); };
  const changeRole = async (id, newRole) => { await api.patch(`/team/members/${id}`, { role: newRole }); load(); };
  const remove = async id => { if (window.confirm("Remove this member?")) { await api.delete(`/team/members/${id}`); load(); } };
  const revoke = async id => { if (window.confirm("Revoke this invitation?")) { await api.delete(`/team/members/${id}`); load(); } };
  return (
    <>
      <PageTitle eyebrow="Workspace" title="Team" desc="Invite teammates to help read and respond to customer feedback." />
      {canManage && (
        <section className="section-panel invite-panel" data-testid="invite-panel">
          <div className="panel-head"><div><p className="eyebrow">Invite someone</p><h3>Send an invitation</h3></div></div>
          <form onSubmit={invite} className="invite-form">
            <input type="email" required placeholder="colleague@company.com" value={email} onChange={e => setEmail(e.target.value)} data-testid="invite-email-input" />
            <select value={role} onChange={e => setRole(e.target.value)} data-testid="invite-role-select">
              <option value="editor">Editor — can build templates</option>
              <option value="viewer">Viewer — can only read</option>
            </select>
            <button className="primary" data-testid="send-invite-button">Send invitation <ChevronRight size={16} /></button>
          </form>
          {error && <div className="error">{error}</div>}
          {sentMsg && <div className="success-note" data-testid="invite-success">{sentMsg}</div>}
        </section>
      )}
      <section className="section-panel members-panel">
        <div className="panel-head"><div><p className="eyebrow">Who's here</p><h3>Members & invites</h3></div></div>
        <div className="member-list">
          {data.owner && (
            <div className="member-row" data-testid="owner-row">
              <div className="response-avatar">{data.owner.full_name?.[0] || "O"}</div>
              <div className="member-main"><strong>{data.owner.full_name}</strong><span>{data.owner.email}</span></div>
              <span className="role-chip owner">Owner</span>
              <span></span>
            </div>
          )}
          {data.members.map(m => (
            <div className="member-row" key={m.id} data-testid={`member-${m.id}`}>
              <div className="response-avatar">{m.user?.full_name?.[0] || m.invite_email[0].toUpperCase()}</div>
              <div className="member-main"><strong>{m.user?.full_name || m.invite_email}</strong><span>{m.user?.email || m.invite_email}</span></div>
              {canManage
                ? <select value={m.role} onChange={e => changeRole(m.id, e.target.value)} className="role-select" data-testid={`role-select-${m.id}`}><option value="editor">Editor</option><option value="viewer">Viewer</option></select>
                : <span className="role-chip">{m.role}</span>}
              {canManage && <button className="icon-btn danger" onClick={() => remove(m.id)} data-testid={`remove-member-${m.id}`}><Trash2 size={14} /></button>}
            </div>
          ))}
          {data.invites.map(inv => (
            <div className="member-row pending" key={inv.id} data-testid={`invite-${inv.id}`}>
              <div className="response-avatar">{inv.invite_email[0].toUpperCase()}</div>
              <div className="member-main"><strong>{inv.invite_email}</strong><span>Pending invitation</span></div>
              <span className="role-chip">{inv.role}</span>
              {canManage && <div className="button-row"><button className="icon-btn" onClick={() => copyInvite(inv)} title="Copy link" data-testid={`copy-invite-${inv.id}`}><Copy size={14} /></button><button className="icon-btn danger" onClick={() => revoke(inv.id)} data-testid={`revoke-invite-${inv.id}`}><Trash2 size={14} /></button></div>}
            </div>
          ))}
          {!data.members.length && !data.invites.length && <p className="muted members-empty">You haven't invited anyone yet. Add teammates above to share this workspace.</p>}
        </div>
      </section>
    </>
  );
}

/* ===== Invite accept ===== */
function InviteAccept() {
  const { token } = useParams();
  const nav = useNavigate();
  const [state, setState] = useState({ loading: true, invite: null, error: "", success: false });
  useEffect(() => { api.get(`/team/invites/${token}`).then(r => setState(s => ({ ...s, loading: false, invite: r.data }))).catch(e => setState(s => ({ ...s, loading: false, error: errorText(e) }))); }, [token]);
  const accept = async () => {
    const user = localStorage.getItem("feedback_token");
    if (!user) { nav(`/login?invite=${token}`); return; }
    try { await api.post(`/team/invites/${token}/accept`); setState(s => ({ ...s, success: true })); setTimeout(() => nav("/dashboard"), 1500); }
    catch (e) { setState(s => ({ ...s, error: errorText(e) })); }
  };
  if (state.loading) return <Loading />;
  if (state.error) return <div className="public-shell"><div className="thank-you"><X size={28} /><h1>{state.error}</h1><Link to="/login" className="outline" style={{ marginTop: 20 }}>Go to sign in</Link></div></div>;
  if (state.success) return <div className="public-shell"><div className="thank-you"><div className="publish-check"><Check size={27} /></div><h1>You're in.</h1><p>Opening your workspace…</p></div></div>;
  return (
    <div className="public-shell">
      <div className="public-brand">F<span>•</span> feedback loop</div>
      <main className="feedback-form invite-accept">
        <div className="business-kicker"><div className="business-logo">{state.invite.workspace?.name?.[0] || "W"}</div><span>{state.invite.workspace?.name}</span></div>
        <p className="eyebrow">Team invitation</p>
        <h1>Join {state.invite.workspace?.name}.</h1>
        <p className="public-description">You've been invited as a <b>{state.invite.invite?.role}</b>. Sign in with <b>{state.invite.invite?.email}</b> to accept.</p>
        <button className="primary submit-feedback" onClick={accept} data-testid="accept-invite-button">Accept invitation <ChevronRight size={17} /></button>
      </main>
    </div>
  );
}

/* ===== Locations ===== */
function Locations() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ name: "", address: "", city: "", phone: "" });
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");
  const load = () => api.get("/locations").then(r => setItems(r.data));
  useEffect(() => { load(); }, []);
  const submit = async e => {
    e.preventDefault(); setError("");
    try {
      if (editing) { await api.patch(`/locations/${editing}`, form); setEditing(null); }
      else { await api.post("/locations", form); }
      setForm({ name: "", address: "", city: "", phone: "" }); load();
    } catch (x) { setError(errorText(x)); }
  };
  const edit = l => { setEditing(l.id); setForm({ name: l.name, address: l.address, city: l.city, phone: l.phone }); };
  const remove = async id => { if (window.confirm("Delete this location?")) { await api.delete(`/locations/${id}`); load(); } };
  return (
    <>
      <PageTitle eyebrow="Workspace" title="Locations" desc="Attach templates to specific places so you can see where feedback is coming from." />
      <div className="locations-layout">
        <section className="section-panel location-form">
          <div className="panel-head"><div><p className="eyebrow">{editing ? "Edit location" : "Add a location"}</p><h3>{editing ? "Update details" : "A new place to listen"}</h3></div></div>
          <form onSubmit={submit}>
            <label>Location name<input required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Jubilee Hills Flagship" data-testid="location-name-input" /></label>
            <label>Address<input value={form.address} onChange={e => setForm({ ...form, address: e.target.value })} placeholder="Road No. 10" data-testid="location-address-input" /></label>
            <label>City<input value={form.city} onChange={e => setForm({ ...form, city: e.target.value })} placeholder="Hyderabad" data-testid="location-city-input" /></label>
            <label>Phone<input value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} placeholder="+91 90000 11111" data-testid="location-phone-input" /></label>
            {error && <div className="error">{error}</div>}
            <div className="button-row">
              <button className="primary" data-testid="location-submit-button">{editing ? "Save changes" : "Add location"} <ChevronRight size={16} /></button>
              {editing && <button type="button" className="outline" onClick={() => { setEditing(null); setForm({ name: "", address: "", city: "", phone: "" }); }}>Cancel</button>}
            </div>
          </form>
        </section>
        <section className="section-panel location-list">
          <div className="panel-head"><div><p className="eyebrow">Your places</p><h3>Locations</h3></div></div>
          {items.length ? items.map(l => (
            <div className="location-row" key={l.id} data-testid={`location-${l.id}`}>
              <div className="loc-icon"><MapPin size={16} /></div>
              <div className="loc-main"><strong>{l.name}</strong><span>{[l.address, l.city].filter(Boolean).join(", ") || "No address"}</span>{l.phone && <small>{l.phone}</small>}</div>
              <div className="button-row">
                <button className="icon-btn" onClick={() => edit(l)} data-testid={`edit-location-${l.id}`}><Settings size={14} /></button>
                <button className="icon-btn danger" onClick={() => remove(l.id)} data-testid={`delete-location-${l.id}`}><Trash2 size={14} /></button>
              </div>
            </div>
          )) : <p className="muted members-empty">No locations yet. Add one above to start attaching feedback forms to places.</p>}
        </section>
      </div>
    </>
  );
}

/* ===== Actions ===== */
function Actions() {
  const [items, setItems] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ title: "", description: "" });
  const [error, setError] = useState("");
  const load = () => api.get("/actions").then(r => setItems(r.data));
  useEffect(() => { load(); }, []);
  const columns = [
    ["open", "To do", Circle, "col-open"],
    ["in_progress", "In progress", CircleDot, "col-progress"],
    ["done", "Done", CheckCircle2, "col-done"],
  ];
  const move = async (id, status) => { await api.patch(`/actions/${id}`, { status }); load(); };
  const assignSelf = async id => { await api.post(`/actions/${id}/assign`); load(); };
  const remove = async id => { if (window.confirm("Delete this action?")) { await api.delete(`/actions/${id}`); load(); } };
  const create = async e => {
    e.preventDefault(); setError("");
    try { await api.post("/actions", form); setForm({ title: "", description: "" }); setShowAdd(false); load(); }
    catch (x) { setError(errorText(x)); }
  };
  return (
    <>
      <PageTitle eyebrow="One-tap actions" title="Actions" desc="Negative feedback becomes a card your team can pick up and resolve." action={<button className="primary" onClick={() => setShowAdd(!showAdd)} data-testid="toggle-add-action"><Plus size={17} /> {showAdd ? "Close" : "New action"}</button>} />
      {showAdd && (
        <section className="section-panel action-add-panel" data-testid="action-add-panel">
          <form onSubmit={create}>
            <label>Title<input required value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="Follow up with repeat complaint about wait times" data-testid="action-title-input" /></label>
            <label>Description<textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="Context, who to call, what to try..." data-testid="action-desc-input" /></label>
            {error && <div className="error">{error}</div>}
            <button className="primary" data-testid="action-create-button">Create action <ChevronRight size={16} /></button>
          </form>
        </section>
      )}
      {items.length === 0
        ? <Empty icon={ListTodo} title="No actions yet." text="When a customer leaves negative feedback, we'll create an action card here automatically." />
        : <div className="kanban" data-testid="kanban-board">
            {columns.map(([key, label, Icon, cls]) => (
              <div className={`kanban-col ${cls}`} key={key} data-testid={`kanban-${key}`}>
                <div className="kanban-head"><Icon size={15} /><strong>{label}</strong><span>{items.filter(a => a.status === key).length}</span></div>
                <div className="kanban-cards">
                  {items.filter(a => a.status === key).map(a => (
                    <article className="action-card" key={a.id} data-testid={`action-${a.id}`}>
                      <div className="action-card-top">
                        {a.source === "auto" && <span className="chip-auto"><Sparkles size={10} /> AI</span>}
                        <button className="icon-btn danger" onClick={() => remove(a.id)} data-testid={`delete-action-${a.id}`}><Trash2 size={13} /></button>
                      </div>
                      <h4>{a.title}</h4>
                      {a.description && <p>{a.description}</p>}
                      <div className="action-foot">
                        <span className="assignee">{a.assignee ? <><span className="assignee-dot">{a.assignee.full_name[0]}</span>{a.assignee.full_name}</> : <button className="link-btn" onClick={() => assignSelf(a.id)} data-testid={`claim-${a.id}`}>Claim</button>}</span>
                        <div className="action-moves">
                          {key !== "open" && <button className="pill" onClick={() => move(a.id, "open")} data-testid={`move-open-${a.id}`}>To do</button>}
                          {key !== "in_progress" && <button className="pill" onClick={() => move(a.id, "in_progress")} data-testid={`move-progress-${a.id}`}>In progress</button>}
                          {key !== "done" && <button className="pill" onClick={() => move(a.id, "done")} data-testid={`move-done-${a.id}`}>Done</button>}
                        </div>
                      </div>
                      {a.response_id && <Link to={`/responses/${a.response_id}`} className="action-link">View response <ChevronRight size={11} /></Link>}
                    </article>
                  ))}
                  {items.filter(a => a.status === key).length === 0 && <p className="kanban-empty">Nothing here.</p>}
                </div>
              </div>
            ))}
          </div>}
    </>
  );
}

/* ===== Settings ===== */
function SettingsPage() {
  const [ws, setWs] = useState(null);
  useEffect(() => { api.get("/workspaces").then(r => setWs(r.data[0])); }, []);
  return (
    <>
      <PageTitle eyebrow="Workspace" title="Business settings" desc="Keep your business details current for customer-facing pages." />
      {ws && (
        <section className="settings-form section-panel">
          <label>Business name<input value={ws.name} readOnly data-testid="settings-business-name" /></label>
          <label>Business type<input value={ws.business_type} readOnly /></label>
          <label>Location<input value={ws.location || "Not added"} readOnly /></label>
          <div className="settings-note"><Building2 size={19} /><span><b>{ws.name}</b><small>Workspace created {fmtDate(ws.created_at)}</small></span></div>
        </section>
      )}
    </>
  );
}

/* ===== Root ===== */
export default function App() {
  const [user, setUser] = useState(undefined);
  useEffect(() => {
    const t = localStorage.getItem("feedback_token");
    if (!t) { setUser(null); return; }
    api.get("/auth/me").then(r => setUser(r.data)).catch(() => { localStorage.removeItem("feedback_token"); setUser(null); });
  }, []);
  const logout = async () => { await api.post("/auth/logout").catch(() => {}); localStorage.removeItem("feedback_token"); setUser(null); };
  if (user === undefined) return <Loading />;
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/dashboard" /> : <Auth onAuth={setUser} />} />
        <Route path="/register" element={user ? <Navigate to="/dashboard" /> : <Auth onAuth={setUser} />} />
        <Route path="/f/:slug" element={<PublicFeedback />} />
        <Route path="/invite/:token" element={<InviteAccept />} />
        <Route path="*" element={
          <Protected user={user}>
            <Shell user={user} onLogout={logout}>
              <Routes>
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/templates" element={<Templates />} />
                <Route path="/templates/new" element={<TemplateBuilder />} />
                <Route path="/templates/:id/edit" element={<TemplateBuilder />} />
                <Route path="/templates/:id/publish" element={<PublishPage />} />
                <Route path="/responses" element={<Responses />} />
                <Route path="/responses/:id" element={<ResponseDetail />} />
                <Route path="/actions" element={<Actions />} />
                <Route path="/analytics" element={<Analytics />} />
                <Route path="/team" element={<Team />} />
                <Route path="/locations" element={<Locations />} />
                <Route path="/settings/business" element={<SettingsPage />} />
                <Route path="*" element={<Navigate to="/dashboard" />} />
              </Routes>
            </Shell>
          </Protected>
        } />
      </Routes>
    </BrowserRouter>
  );
}
