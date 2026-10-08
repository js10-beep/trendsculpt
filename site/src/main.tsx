import React, {
  useState,
  useEffect,
  createContext,
  useContext,
  useRef,
} from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Routes,
  Route,
  Link,
  NavLink,
  useNavigate,
  useLocation,
  Navigate,
} from "react-router-dom";
import {
  ArrowUpRight,
  ArrowRight,
  Plus,
  Sparkles,
  Layers,
  LayoutDashboard,
  History,
  UserRound,
  Settings,
  LogOut,
  ChevronDown,
  Upload,
  Check,
  Copy,
  Trash2,
  Search,
  Menu,
  X,
  TrendingUp,
  Target,
  Zap,
  FileText,
  Image as ImageIcon,
  Video,
  Shield,
  ArrowLeft,
  Download,
  FlaskConical,
} from "lucide-react";
import { analyze, contentAnalysisService, Input, Report } from "./engine";
import {
  api,
  User,
  me,
  signup as createAccount,
  login as loginAccount,
  logout as signOut,
  recover,
  deleteAccount,
  reportFor,
  usageFor,
  reportsFor,
  persistReport,
  removeReport,
  persistProfile,
  runVideoAnalysis,
} from "./store";
import modelData from "./model-data.json";

import "@fontsource-variable/dm-sans";
import "@fontsource-variable/manrope";
import "./styles.css";
const platforms = [
  "Instagram",
  "YouTube Shorts",
  "YouTube (long-form)",
  "TikTok",
  "LinkedIn",
  "X",
];
const LONG_FORM = "YouTube (long-form)";
const timeLabel = (seconds: number) => {
  const n = Math.floor(seconds);
  const ms = Math.round((seconds - n) * 1000);
  const suffix = ms ? `.${String(ms).padStart(3, "0").replace(/0+$/, "")}` : "";
  return (
    (n >= 3600
      ? `${Math.floor(n / 3600)}:${String(Math.floor(n / 60) % 60).padStart(2, "0")}:${String(n % 60).padStart(2, "0")}`
      : `${Math.floor(n / 60)}:${String(n % 60).padStart(2, "0")}`) + suffix
  );
};
const creators = [
  "Content Creator",
  "Influencer",
  "Founder",
  "Brand",
  "Social Media Manager",
  "Agency",
  "Other",
];
const disclaimer =
  "Predictions combine content signals with limited historical model evidence, not guarantees. Audience behavior, algorithms, timing, and distribution affect actual results.";
type Context = {
  user: User | null;
  setUser: (u: User | null) => void;
  reports: Report[];
  usage: { count: number; limit: number };
  refresh: () => Promise<void>;
  toast: (s: string) => void;
};
const Ctx = createContext<Context>(null!);
const useApp = () => useContext(Ctx);
const err = (e: unknown) =>
  e instanceof DOMException && e.name === "QuotaExceededError"
    ? "Browser storage is full. Try smaller media, delete old reports, or export your reports first."
    : e instanceof Error
      ? e.message
      : typeof e === "object" && e !== null && "message" in e
        ? String(e.message)
        : "Something went wrong. Please try again.";
function App() {
  const [user, setAuthUser] = useState<User | null>(null);
  const currentOwner = useRef<string | undefined>(undefined);
  const [ready, setReady] = useState(false);
  const [reports, setReports] = useState<Report[]>([]);
  const [usage, setUsage] = useState({ count: 0, limit: 100 });
  const [notice, setNotice] = useState("");
  const setUser = (next: User | null) => {
    if (currentOwner.current !== next?.id) {
      setReports([]);
      setUsage({ count: 0, limit: 100 });
    }
    currentOwner.current = next?.id;
    setAuthUser(next);
  };
  const toast = (s: string) => {
    setNotice(s);
    window.setTimeout(() => setNotice(""), 4500);
  };
  const refresh = async () => {
    if (user) {
      const [r, u] = await Promise.all([reportsFor(user.id), usageFor()]);
      if (currentOwner.current === user.id) {
        setReports(r);
        setUsage(u);
      }
    } else {
      setReports([]);
      setUsage({ count: 0, limit: 100 });
    }
  };
  useEffect(() => {
    let active = true;
    me()
      .then(({ user }) => {
        if (active) setUser(user);
      })
      .catch((e) => toast(err(e)))
      .finally(() => {
        if (active) setReady(true);
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    refresh().catch((e) => toast(err(e)));
  }, [user?.id]);
  useEffect(() => {
    const clear = () => setUser(null);
    window.addEventListener("ts-session-expired", clear);
    return () => window.removeEventListener("ts-session-expired", clear);
  }, []);
  if (!ready)
    return <div className="loading-page">Opening your secure workspace…</div>;
  return (
    <Ctx.Provider value={{ user, setUser, reports, usage, refresh, toast }}>
      <ScrollTop />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Auth />} />
        <Route path="/signup" element={<Auth signup />} />
        <Route path="/forgot-password" element={<Reset />} />
        <Route path="/reset-password" element={<Reset update />} />
        <Route
          path="/onboarding"
          element={user ? <Onboarding /> : <Navigate to="/signup" />}
        />
        {[
          "features",
          "impact",
          "about",
          "founder",
          "faqs",
          "privacy",
          "terms",
        ].map((p) => (
          <Route key={p} path={"/" + p} element={<PublicPage page={p} />} />
        ))}
        <Route
          path="/app/*"
          element={user ? <Workspace /> : <Navigate to="/signup" />}
        />
        <Route
          path="*"
          element={
            <>
              <PublicNav />
              <main className="public-content">
                <h1>That page isn’t here.</h1>
                <Link className="button" to="/">
                  Back to home
                </Link>
              </main>
            </>
          }
        />
      </Routes>
      {notice && (
        <div role="status" className="toast">
          <Check size={18} />
          {notice}
        </div>
      )}
    </Ctx.Provider>
  );
}
function ScrollTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}
function Brand() {
  return (
    <Link to="/" className="brand">
      <span className="brand-symbol">
        <Layers size={23} />
      </span>
      trendsculpt<span className="brand-dot">.</span>
    </Link>
  );
}
function PublicNav() {
  const [open, setOpen] = useState(false);
  const { user } = useApp();
  return (
    <header className="public-nav">
      <Brand />
      <button
        className="icon-button mobile-only"
        aria-label="Toggle navigation"
        onClick={() => setOpen(!open)}
      >
        <Menu />
      </button>
      <nav className={open ? "open" : ""}>
        {["Features", "Impact", "About", "Founder", "FAQs"].map((x) => (
          <Link key={x} to={"/" + x.toLowerCase()}>
            {x}
          </Link>
        ))}
        <Link to={user ? "/app" : "/login"}>
          {user ? "Dashboard" : "Log in"}
        </Link>
        <Link className="button small" to={user ? "/app/analyze" : "/signup"}>
          Get started <ArrowUpRight size={16} />
        </Link>
      </nav>
    </header>
  );
}
function Footer() {
  return (
    <footer>
      <div>
        <Brand />
        <p>Shape your content before the world sees it.</p>
      </div>
      <div>
        {[
          "Features",
          "About",
          "Impact",
          "Founder",
          "FAQs",
          "Privacy",
          "Terms",
        ].map((x) => (
          <Link key={x} to={"/" + x.toLowerCase()}>
            {x}
          </Link>
        ))}
      </div>
      <span>© {new Date().getFullYear()} TrendSculpt</span>
    </footer>
  );
}
function Landing() {
  const { user } = useApp();
  const cta = user ? "/app/analyze" : "/signup";
  return (
    <>
      <PublicNav />
      <main>
        <section className="hero">
          <div className="hero-copy">
            <span className="eyebrow">
              <span className="green-dot" /> A LITTLE INTELLIGENCE. A LOT OF
              POTENTIAL.
            </span>
            <h1>
              Shape your content
              <br />
              before the world
              <br />
              <em>sees it.</em>
            </h1>
            <p>
              Shape your content before the world sees it. Get a clearer picture
              of what could resonate—and make your next post your most
              intentional.
            </p>
            <div className="actions">
              <Link className="button" to={cta}>
                Analyze my content <ArrowUpRight size={19} />
              </Link>
              <a className="text-button" href="#how">
                See how it works <ArrowRight size={18} />
              </a>
            </div>
            <div className="hero-note">
              <span className="avatar-stack">
                <b>JC</b>
                <b>AK</b>
                <b>LM</b>
              </span>
              <span>
                Built for creators and brands with something to say.
                <br />
                <small>Free to explore. No guesswork required.</small>
              </span>
            </div>
          </div>
          <div className="hero-visual">
            <div className="hero-visual-top">
              <span>
                <Sparkles size={17} /> YOUR NEXT POST, REIMAGINED
              </span>
              <span className="pill">Sample report</span>
            </div>
            <div className="visual-art">
              <span className="art-label">THE CREATOR’S PLAYBOOK</span>
              <div className="art-orbit" />
              <h2>
                Small changes.
                <br />
                <em>Big energy.</em>
              </h2>
              <div className="art-bottom">
                MAKE SOMETHING THAT MATTERS <ArrowUpRight />
              </div>
            </div>
            <div className="floating-score">
              <div>
                <span className="eyebrow">ENGAGEMENT POTENTIAL</span>
                <h2>
                  82<span>/100</span>
                </h2>
                <span className="status">
                  <span className="green-dot" /> High potential
                </span>
              </div>
              <div className="score-circle">82</div>
            </div>
            <div className="hero-breakdown">
              <div>
                <span>Hook strength</span>
                <b>86</b>
                <i style={{ width: "86%" }} />
              </div>
              <div>
                <span>Audience relevance</span>
                <b>81</b>
                <i style={{ width: "81%" }} />
              </div>
            </div>
            <div className="hero-tip">
              <Sparkles size={18} />
              <span>
                A stronger opening. A clearer next step.
                <br />
                <b>A post with more purpose.</b>
              </span>
            </div>
          </div>
        </section>
        <div className="platform-strip">
          <span>YOUR CREATIVITY. ANY PLATFORM.</span>
          <b>◎ Instagram</b>
          <b>▶ YouTube Shorts</b>
          <b>♪ TikTok</b>
          <b>in LinkedIn</b>
          <b>𝕏</b>
        </div>
        <section className="section" id="how">
          <div className="section-heading">
            <div>
              <span className="eyebrow">
                FROM FIRST DRAFT TO FULL POTENTIAL
              </span>
              <h2>A little insight goes a long way.</h2>
            </div>
            <p>
              Your creative process, with a new perspective.
              <br />
              Four simple steps. One more confident creator.
            </p>
          </div>
          <div className="steps">
            {[
              [
                "01",
                "Bring your idea",
                "A caption, an image, or a short video. Start with what you’ve made.",
                Upload,
              ],
              [
                "02",
                "Find your signals",
                "Explore your hook, clarity, and audience fit.",
                Sparkles,
              ],
              [
                "03",
                "See the potential",
                "Get a structured score and practical feedback.",
                TrendingUp,
              ],
              [
                "04",
                "Make it stronger",
                "Refine, compare, and save your best version.",
                Layers,
              ],
            ].map(([n, t, d, I]) => {
              const Icon = I as typeof Upload;
              return (
                <article className="step" key={String(n)}>
                  <div>
                    <Icon size={24} />
                    <span>{String(n)}</span>
                  </div>
                  <h3>{String(t)}</h3>
                  <p>{String(d)}</p>
                </article>
              );
            })}
          </div>
        </section>
        <section className="manifesto">
          <span className="eyebrow">CREATIVITY × INTELLIGENCE</span>
          <h2>
            Great content deserves
            <br />
            more than guesswork.
          </h2>
          <p>
            Keep the instinct. Add the insight. TrendSculpt helps you find a
            sharper hook, a clearer message, and a more intentional next step.
          </p>
          <Link to="/features" className="text-button">
            Explore the toolkit <ArrowUpRight size={18} />
          </Link>
        </section>
        <section className="section">
          <DatasetCard />
        </section>
        <section className="closing">
          <div>
            <span className="eyebrow">MAKE YOUR NEXT POST COUNT</span>
            <h2>Don’t just post. Sculpt.</h2>
            <p>
              Your creativity is the starting point. Let’s see where it can go.
            </p>
          </div>
          <Link className="button" to={cta}>
            Start sculpting <ArrowUpRight size={20} />
          </Link>
        </section>
      </main>
      <Footer />
    </>
  );
}
function DatasetCard() {
  return (
    <article className="dataset-card">
      <div>
        <span className="eyebrow">
          <FlaskConical size={14} />
          LOCAL MODELS. OPEN CONTEXT.
        </span>
        <h3>Real observations. Transparent estimates.</h3>
        <p>
          Two local models reference Instagram observations and archived YouTube
          API records. Examine the sources, methods, and limitations behind the
          feedback.
        </p>
        <Link
          to={useApp().user ? "/app/sources" : "/features"}
          className="text-button"
        >
          Explore the intelligence <ArrowUpRight size={15} />
        </Link>
      </div>
      <div className="dataset-stats">
        <div>
          <b>176</b>
          <span>Instagram sample posts</span>
        </div>
        <div>
          <b>1,671</b>
          <span>Deduplicated YouTube archive records</span>
        </div>
      </div>
      <small>
        Biased historical samples; the YouTube archive predates Shorts. These
        models do not establish causation or guarantee future performance.
        Private datasets can make the reference more relevant to your account.
      </small>
    </article>
  );
}
const FAQs = [
  [
    "What is TrendSculpt?",
    "A content intelligence workspace that helps you assess and refine content before publishing.",
  ],
  [
    "What can I analyze?",
    "Text, captions, images, and MP4 videos. Video reviews use supplied transcripts or SRT/VTT subtitles, English on-screen text OCR, sampled frames and audio levels. Long-form YouTube supports videos up to 60 minutes / 50 MB, or full transcript reviews. Automatic speech transcription and visual-subject recognition are not connected.",
  ],
  [
    "Does it guarantee engagement?",
    "No. Scores are heuristic estimates. Real performance depends on your audience, timing, distribution, and platform algorithms.",
  ],
  [
    "How does the prediction work?",
    "Local TF-IDF regression models trained on public Instagram and archived YouTube observations supply historical-pattern estimates. Content heuristics supply hook, clarity and CTA feedback. Model evidence is used cautiously and shown with limitations; there is no guarantee of actual engagement.",
  ],
  [
    "Which platforms can I select?",
    "Instagram, YouTube Shorts, YouTube (long-form), TikTok, LinkedIn, and X. Long-form YouTube has a dedicated title, opening, chapter and closing review.",
  ],
  [
    "Is my content private?",
    "Your profile, reports, media and private datasets are stored on this server and accessible only through your authenticated account. Delete reports, datasets or your account to remove them from the active database. Deployment backups may have their own retention policy.",
  ],
  [
    "Is it free?",
    "A free account includes 100 analyses per calendar month. The server enforces the limit. Paid subscriptions are not implemented.",
  ],
  [
    "Can I improve my score?",
    "Try suggested hooks and captions, compare scores, and save both versions. A higher estimated score does not guarantee higher real engagement.",
  ],
];
function PublicPage({ page }: { page: string }) {
  const { user } = useApp();
  const titles: Record<string, string> = {
    features: "A sharper toolkit. A stronger next post.",
    impact: "From intuition to informed creation.",
    about: "Creators shouldn’t have to create in the dark.",
    founder: "Built around human curiosity.",
    faqs: "A little more clarity.",
    privacy: "Your content. Your control.",
    terms: "Create with context.",
  };
  return (
    <>
      <PublicNav />
      <main className="public-content">
        <span className="eyebrow">
          {page === "faqs" ? "YOUR QUESTIONS, ANSWERED" : page.toUpperCase()}
        </span>
        <h1>{titles[page]}</h1>
        {page === "faqs" ? (
          <div className="faq-list">
            {FAQs.map(([q, a]) => (
              <details key={q}>
                <summary>
                  {q}
                  <ChevronDown size={18} />
                </summary>
                <p>{a}</p>
              </details>
            ))}
          </div>
        ) : page === "features" ? (
          <div className="feature-grid">
            {[
              [
                "Content intelligence",
                "Analyze caption clarity, hooks, audience fit, and calls to action.",
              ],
              [
                "Engagement estimates",
                "Five transparent signals with actionable scoring feedback.",
              ],
              [
                "A fresh perspective",
                "Suggested hooks, captions, and CTAs tailored to your topic.",
              ],
              [
                "Before & after",
                "Compare a revision using the same framework.",
              ],
              [
                "A personal library",
                "Save, filter, export, and revisit your analyses.",
              ],
              [
                "Media readiness",
                "Preview images and videos, check their dimensions, and get practical review prompts.",
              ],
            ].map(([t, d]) => (
              <article className="card" key={t}>
                <Sparkles />
                <h3>{t}</h3>
                <p>{d}</p>
              </article>
            ))}
          </div>
        ) : page === "impact" ? (
          <>
            <p className="lead">
              Attention is limited. Your creative decisions matter. TrendSculpt
              is designed to improve decision-making, with structured feedback
              before you publish.
            </p>
            <div className="feature-grid">
              {[
                "Better creation",
                "Better discoverability",
                "Better retention",
                "Better monetization potential",
              ].map((t, i) => (
                <article className="card" key={t}>
                  <span className="eyebrow">0{i + 1}</span>
                  <h3>{t}</h3>
                  <p>
                    {
                      [
                        "Make intentional choices with specific feedback.",
                        "Clarify your topic and the value of your message.",
                        "Review your opening and simplify your story.",
                        "Build a learning habit that may support commercial growth. No income or performance is guaranteed.",
                      ][i]
                    }
                  </p>
                </article>
              ))}
            </div>
          </>
        ) : page === "about" ? (
          <>
            <p className="lead">
              Creativity × Artificial Intelligence × Initiative.
            </p>
            <p>
              Creators have always learned through intuition, experimentation,
              and post-publication analytics. We bring an extra perspective into
              the process before publication.
            </p>
            <div className="feature-grid">
              <article className="card">
                <h3>Our mission</h3>
                <p>
                  Give every creator access to intelligent feedback for stronger
                  content decisions.
                </p>
              </article>
              <article className="card">
                <h3>Our vision</h3>
                <p>Data makes creativity more intentional.</p>
              </article>
              {[
                "Creator first",
                "Intelligence with context",
                "Experimentation",
                "Responsible AI",
              ].map((t) => (
                <article className="card" key={t}>
                  <h3>{t}</h3>
                  <p>
                    Simple tools, transparent estimates, and room to keep
                    learning.
                  </p>
                </article>
              ))}
            </div>
          </>
        ) : page === "founder" ? (
          <div className="founder-card">
            <div className="founder-placeholder">
              <UserRound size={90} />
              <span>Founder photo coming soon</span>
            </div>
            <div>
              <span className="eyebrow">FOUNDER, TRENDSCULPT</span>
              <h2>[FOUNDER NAME]</h2>
              <p>
                TrendSculpt was born from a simple observation: creators have
                more content tools than ever, but still have limited
                intelligence about what might resonate before they publish.
              </p>
              <p>
                The founder brings together experience in content, media and
                digital innovation to build a more intelligent approach to
                content creation.
              </p>
              <small>
                Founder details and contact link will be added when supplied.
              </small>
            </div>
          </div>
        ) : page === "privacy" ? (
          <>
            <p className="lead">Your account controls your content.</p>
            <p>
              Accounts use password hashes and server sessions in an HTTP-only
              cookie. Profiles, uploaded media, reports, and private datasets
              are stored on this server and restricted to the signed-in account.
              Content is not sent to a hosted AI provider in the current
              local-model configuration.
            </p>
            <p>
              You can delete individual reports, remove private training
              datasets, or delete your account and its active database records.
              Deployment operators must separately define backup retention and
              infrastructure access. Transport security depends on using HTTPS
              in your deployment.
            </p>
            <p>
              Your recovery code is shown once and stored as a hash. Keep it
              private; it can reset your password. Email delivery is not
              configured. No advertising or analytics trackers are included.
            </p>
            <p>
              Reference models use public historical observations with source
              attribution. Your uploaded dataset is private to your account.
            </p>
          </>
        ) : (
          <>
            <p className="lead">
              Use this workspace as guidance for creative decisions.
            </p>
            <p>
              Scores, suggested captions, and recommendations are heuristic
              estimates. They do not guarantee reach, revenue, engagement, or
              virality. Check factual claims and rights to uploaded content
              before publishing.
            </p>
            <p>
              The free account includes 100 analyses per month. Historical
              observations may not transfer to your audience or modern formats.
              Use data and content only when you have the necessary rights.
            </p>
          </>
        )}
        {!["privacy", "terms", "founder"].includes(page) && (
          <Link className="button" to={user ? "/app/analyze" : "/signup"}>
            Analyze my content <ArrowUpRight size={18} />
          </Link>
        )}
      </main>
      <Footer />
    </>
  );
}
function RecoveryCard({
  code,
  onContinue,
}: {
  code: string;
  onContinue: () => void;
}) {
  const { toast } = useApp();
  const [stored, setStored] = useState(false);
  return (
    <div className="modal-overlay">
      <section
        className="modal card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="recovery-title"
      >
        <Shield size={30} />
        <span className="eyebrow">KEEP THIS SOMEWHERE SAFE</span>
        <h2 id="recovery-title">Your account recovery code.</h2>
        <p>
          This code can reset your password. Store it in a password manager. We
          won’t show it again. Email recovery is not configured on this server.
        </p>
        <code className="recovery-code">{code}</code>
        <button
          className="text-button"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(code);
              toast("Recovery code copied. Keep it private.");
            } catch {
              toast("Select and copy the code manually.");
            }
          }}
        >
          <Copy size={15} />
          Copy recovery code
        </button>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={stored}
            onChange={(e) => setStored(e.target.checked)}
          />
          I have saved my recovery code.
        </label>
        <button className="button full" disabled={!stored} onClick={onContinue}>
          Continue to my workspace <ArrowRight size={16} />
        </button>
      </section>
    </div>
  );
}
function Auth({ signup = false }: { signup?: boolean }) {
  const { setUser } = useApp();
  const nav = useNavigate();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [remember, setRemember] = useState(false);
  const [recovery, setRecovery] = useState("");
  const [destination, setDestination] = useState("/app");
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (signup && password !== confirm)
        throw new Error("Passwords must match.");
      const result = signup
        ? await createAccount(name, email, password)
        : await loginAccount(email, password, remember);
      setUser(result.user);
      const path = result.user.onboarded ? "/app" : "/onboarding";
      setDestination(path);
      if ("recoveryCode" in result) setRecovery(String(result.recoveryCode));
      else nav(path);
    } catch (e) {
      setError(err(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PublicNav />
      <main className="auth-layout">
        <div className="auth-story">
          <span className="eyebrow">
            FOR CREATORS. FOR BRANDS. FOR WHAT’S NEXT.
          </span>
          <h1>
            Big ideas.
            <br />
            <em>A sharper edge.</em>
          </h1>
          <p>
            A workspace that turns your content into more intentional decisions.
          </p>
          <div className="abstract-shape">
            <Layers size={120} />
          </div>
          <div className="auth-proof">
            <Shield size={17} /> Password-protected accounts · Private saved
            reports
          </div>
        </div>
        <section className="auth-form card">
          <span className="eyebrow">YOUR CONTENT INTELLIGENCE WORKSPACE</span>
          <h2>{signup ? "Your next chapter starts here." : "Welcome back."}</h2>
          <p>
            {signup
              ? "Create your free account. Keep your ideas and reports together."
              : "Good to see you. Let’s shape what comes next."}
          </p>
          <form onSubmit={submit}>
            {signup && (
              <label>
                Full name
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  maxLength={80}
                  autoComplete="name"
                />
              </label>
            )}
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                maxLength={254}
                autoComplete="email"
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={10}
                maxLength={128}
                autoComplete={signup ? "new-password" : "current-password"}
              />
            </label>
            {signup ? (
              <>
                <label>
                  Confirm password
                  <input
                    type="password"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    required
                    minLength={10}
                    maxLength={128}
                    autoComplete="new-password"
                  />
                </label>
                <label className="checkbox">
                  <input type="checkbox" required />I agree to the{" "}
                  <Link to="/terms">Terms</Link> and{" "}
                  <Link to="/privacy">Privacy Policy</Link>.
                </label>
              </>
            ) : (
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                />
                Remember me for 30 days
              </label>
            )}
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
            <button className="button full" disabled={busy}>
              {busy
                ? "Opening your workspace…"
                : signup
                  ? "Create my account"
                  : "Log in"}
              <ArrowRight size={18} />
            </button>
          </form>
          <p className="auth-links">
            {signup ? "Already have an account?" : "New to TrendSculpt?"}{" "}
            <Link to={signup ? "/login" : "/signup"}>
              {signup ? "Log in" : "Get started"}
            </Link>
          </p>
          {!signup && (
            <Link to="/forgot-password" className="muted">
              Forgot password?
            </Link>
          )}
        </section>
      </main>
      {recovery && (
        <RecoveryCard code={recovery} onContinue={() => nav(destination)} />
      )}
    </>
  );
}
function Reset({ update = false }: { update?: boolean }) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [newCode, setNewCode] = useState("");
  const { setUser } = useApp();
  const nav = useNavigate();
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setMessage("");
    setBusy(true);
    try {
      if (password !== confirm) throw new Error("Passwords must match.");
      const result = await recover(email, code, password);
      setUser(null);
      setNewCode(result.recoveryCode);
    } catch (e) {
      setMessage(err(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PublicNav />
      <main className="auth-form standalone card">
        <span className="eyebrow">A SAFE WAY BACK IN</span>
        <h2>Recover your account.</h2>
        <p>
          Use the recovery code saved when you created your account. After a
          reset, old sessions are signed out and you receive a new code. Email
          delivery is not configured.
        </p>
        <form onSubmit={submit}>
          <label>
            Email
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </label>
          <label>
            Recovery code
            <input
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
              autoComplete="off"
            />
          </label>
          <label>
            New password
            <input
              type="password"
              required
              minLength={10}
              maxLength={128}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
            />
          </label>
          <label>
            Confirm new password
            <input
              type="password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="new-password"
            />
          </label>
          {message && (
            <p role="alert" className="error">
              {message}
            </p>
          )}
          <button className="button full" disabled={busy}>
            Reset my password <ArrowRight size={16} />
          </button>
        </form>
        <Link to="/login" className="text-button">
          <ArrowLeft size={16} />
          Back to login
        </Link>
      </main>
      {newCode && (
        <RecoveryCard code={newCode} onContinue={() => nav("/login")} />
      )}
    </>
  );
}
function Onboarding() {
  const { user, setUser, toast } = useApp();
  const [step, setStep] = useState(0);
  const [platform, setPlatform] = useState(user!.platform);
  const [creator, setCreator] = useState(user!.creator);
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();
  async function next() {
    if (step < 2) {
      setStep(step + 1);
      return;
    }
    setBusy(true);
    try {
      const u = { ...user!, platform, creator, onboarded: true };
      await persistProfile(u);
      setUser(u);
      nav("/app");
    } catch (e) {
      toast(err(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="onboarding">
      <Brand />
      <div className="onboarding-card card">
        <span className="eyebrow">
          A WORKSPACE THAT FEELS LIKE YOU · {step + 1}/3
        </span>
        <h1>
          {
            [
              "Welcome to TrendSculpt.",
              "Where do you create?",
              "What kind of creator are you?",
            ][step]
          }
        </h1>
        <p>Let’s personalize your content intelligence.</p>
        {step > 0 ? (
          <div className="choices">
            {(step === 1 ? [...platforms, "Other"] : creators).map((t) => (
              <button
                className={
                  (step === 1 ? platform : creator) === t ? "selected" : ""
                }
                key={t}
                onClick={() => (step === 1 ? setPlatform(t) : setCreator(t))}
              >
                {t}
                <ArrowUpRight size={17} />
              </button>
            ))}
          </div>
        ) : (
          <div className="welcome-graphic">
            <Sparkles size={50} />
            <span>YOUR IDEAS, WITH AN EDGE.</span>
          </div>
        )}
        <button className="button full" onClick={next} disabled={busy}>
          {step === 2 ? "Start analyzing" : "Continue"}
          <ArrowRight size={18} />
        </button>
        {step > 0 && (
          <button className="text-button" onClick={() => setStep(step - 1)}>
            Back
          </button>
        )}
      </div>
    </main>
  );
}
function Workspace() {
  const { user, setUser, toast } = useApp();
  const [open, setOpen] = useState(false);
  async function logout() {
    try {
      await signOut();
      setUser(null);
    } catch (e) {
      toast(err(e));
    }
  }
  return (
    <div className="workspace">
      <aside className={open ? "sidebar open" : "sidebar"}>
        <Brand />
        <div className="workspace-label">CREATOR WORKSPACE</div>
        <nav>
          {[
            ["/app", "Overview", LayoutDashboard],
            ["/app/analyze", "Analyze content", Sparkles],
            ["/app/history", "Content library", History],
            ["/app/sources", "Data & models", FlaskConical],
            ["/app/profile", "Profile", UserRound],
            ["/app/settings", "Settings", Settings],
          ].map(([p, n, I]) => {
            const Icon = I as typeof Settings;
            return (
              <NavLink
                end={p === "/app"}
                to={String(p)}
                key={String(p)}
                onClick={() => setOpen(false)}
              >
                <Icon size={19} />
                {String(n)}
                {n === "Analyze content" && (
                  <span className="nav-new">NEW</span>
                )}
              </NavLink>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="plan-card">
            <span>
              <Zap size={15} /> YOUR CREATIVE EDGE
            </span>
            <h4>
              A little insight.
              <br />A better next post.
            </h4>
            <Link to="/app/analyze">
              Let’s sculpt <ArrowUpRight size={16} />
            </Link>
          </div>
          <button className="account-button" onClick={logout}>
            <span className="avatar">
              {user!.name.slice(0, 2).toUpperCase()}
            </span>
            <span>
              <b>{user!.name}</b>
              <small>Free account</small>
            </span>
            <LogOut size={16} />
          </button>
        </div>
      </aside>
      <div className="app-body">
        <header className="app-header">
          <button
            className="icon-button mobile-only"
            aria-label="Toggle sidebar"
            onClick={() => setOpen(!open)}
          >
            {open ? <X /> : <Menu />}
          </button>
          <span>
            <span className="green-dot" /> YOUR CREATIVE SPACE
          </span>
          <div>
            <span className="pill">Free workspace</span>
            <Link
              to="/app/profile"
              className="avatar"
              aria-label="Your profile"
            >
              {user!.name.slice(0, 2).toUpperCase()}
            </Link>
          </div>
        </header>
        <Routes>
          <Route index element={<Overview />} />
          <Route path="analyze" element={<AnalyzePage />} />
          <Route path="report/:id" element={<ReportPage />} />
          <Route path="history" element={<Library />} />
          <Route path="sources" element={<SourcesPage />} />
          <Route path="profile" element={<Profile />} />
          <Route path="settings" element={<Profile settings />} />
          <Route path="*" element={<Navigate to="/app" />} />
        </Routes>
        <div className="app-foot">
          MADE FOR YOUR NEXT BIG IDEA{" "}
          <span>Intelligence with context. Creativity with purpose.</span>
        </div>
      </div>
    </div>
  );
}
const samples: Input[] = [
  {
    text: "5 content mistakes creators make. Before you publish your next post, check your hook, simplify your message, and give your audience a reason to save it. Which one do you see most? #creators",
    type: "Text",
    platform: "Instagram",
    objective: "Engagement",
    audience: "creators",
    topic: "content strategy",
    cta: "",
  },
  {
    text: "How I built my morning routine. Small habits add up. Try one new habit tomorrow and tell me how it feels.",
    type: "Text",
    platform: "TikTok",
    objective: "Followers",
    audience: "busy professionals",
    topic: "morning routines",
    cta: "",
  },
  {
    text: "3 AI tools every creator should know. Build a simpler workflow, keep your voice, and save your time. Which task would you automate first? Save this guide. #AI #creators",
    type: "Text",
    platform: "LinkedIn",
    objective: "Awareness",
    audience: "creators",
    topic: "AI tools",
    cta: "",
  },
];
function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
function Overview() {
  const { user, reports } = useApp();
  const nav = useNavigate();
  const average = reports.length
    ? Math.round(
        reports.reduce((a, r) => a + r.overallScore, 0) / reports.length,
      )
    : 0;
  return (
    <main className="app-main">
      <PageHeading
        eyebrow="A FRESH PERSPECTIVE STARTS HERE"
        title={`Welcome back, ${user!.name.split(" ")[0]}.`}
        description="Let’s put a little more intention into your next post."
        action={
          <Link className="button" to="/app/analyze">
            <Plus size={18} />
            Analyze new content
          </Link>
        }
      />
      <div className="welcome-banner">
        <div>
          <span className="eyebrow">YOUR CREATIVITY. A NEW PERSPECTIVE.</span>
          <h2>
            Good ideas deserve
            <br />a great first impression.
          </h2>
          <p>
            Find your strongest hook. Clarify your message.
            <br />
            Shape what comes next.
          </p>
          <Link className="text-button" to="/app/analyze">
            Let’s sculpt something <ArrowUpRight size={18} />
          </Link>
        </div>
        <div className="banner-art">
          <div className="orbit-one" />
          <div className="orbit-two" />
          <span>
            <Sparkles size={38} />
          </span>
          <div className="mini-note">
            A LITTLE INSIGHT.
            <br />
            <b>A LOT OF POTENTIAL.</b>
          </div>
        </div>
      </div>
      <div className="metrics">
        {[
          [
            FileText,
            "Content analyzed",
            reports.length,
            "Your creative output",
          ],
          [
            TrendingUp,
            "Average score",
            average ? `${average}/100` : "—",
            "Estimated potential",
          ],
          [
            Target,
            "High potential",
            reports.filter((r) => r.overallScore >= 75).length,
            "Scored 75 or above",
          ],
          [
            Sparkles,
            "Versions sculpted",
            reports.filter((r) => r.applied).length,
            "Saved revised reports",
          ],
        ].map(([I, l, v, d]) => {
          const Icon = I as typeof FileText;
          return (
            <article className="metric card" key={String(l)}>
              <div>
                <span>{String(l)}</span>
                <Icon size={18} />
              </div>
              <b>{String(v)}</b>
              <small>{String(d)}</small>
            </article>
          );
        })}
      </div>
      <div className="overview-grid">
        <article className="card chart-card">
          <div className="card-heading">
            <div>
              <h3>Your creative momentum</h3>
              <p>Predicted score across saved analyses</p>
            </div>
            <span className="pill">Last 12 analyses</span>
          </div>
          {reports.length ? (
            <TrendChart reports={reports} />
          ) : (
            <div className="chart-empty">
              <div className="chart-lines" />
              <TrendingUp size={32} />
              <h4>Your story starts with one post.</h4>
              <p>Save an analysis to see your score trend.</p>
              <Link to="/app/analyze">
                Analyze your first post <ArrowRight size={15} />
              </Link>
            </div>
          )}
        </article>
        <article className="card insight-card">
          <span className="eyebrow">
            <Sparkles size={15} /> THE SCULPT NOTE
          </span>
          <div className="insight-icon">“</div>
          <h3>
            Your first line is
            <br />
            an invitation.
          </h3>
          <p>
            Tell your audience why this moment is worth their attention. Be
            specific. Be useful. Be you.
          </p>
          <Link to="/app/analyze" className="text-button">
            Work on your hook <ArrowUpRight size={16} />
          </Link>
        </article>
      </div>
      <section className="recent">
        <div className="card-heading">
          <div>
            <h3>
              {reports.length
                ? "Fresh from your workspace"
                : "Take a look around"}
            </h3>
            <p>
              {reports.length
                ? "Your recent content, with a little more context."
                : "Sample analyses to explore. Separate from your personal statistics."}
            </p>
          </div>
          <Link to="/app/history" className="text-button">
            View library <ArrowRight size={16} />
          </Link>
        </div>
        <div className="report-grid">
          {(reports.length
            ? reports.slice(0, 3)
            : samples.map((s) => ({ ...analyze(s), sample: true }))
          ).map((r, i) => (
            <ReportTile
              key={r.id}
              report={r}
              index={i}
              onClick={() =>
                nav(
                  r.sample ? "/app/report/sample-" + i : "/app/report/" + r.id,
                )
              }
            />
          ))}
        </div>
      </section>
      <DatasetCard />
    </main>
  );
}
function TrendChart({ reports }: { reports: Report[] }) {
  const points = [...reports].reverse().slice(-12);
  const path = points
    .map(
      (r, i) =>
        `${i === 0 ? "M" : "L"} ${40 + (i * 520) / Math.max(points.length - 1, 1)} ${180 - r.overallScore * 1.4}`,
    )
    .join(" ");
  return (
    <div className="trend-chart">
      <svg
        viewBox="0 0 600 220"
        role="img"
        aria-label="Predicted score trend for saved reports"
      >
        {[25, 50, 75, 100].map((n) => (
          <g key={n}>
            <line
              x1="40"
              x2="575"
              y1={180 - n * 1.4}
              y2={180 - n * 1.4}
              stroke="#edf0e8"
            />
            <text x="4" y={184 - n * 1.4} fontSize="10" fill="#81857e">
              {n}
            </text>
          </g>
        ))}
        <path d={path} fill="none" stroke="#72993e" strokeWidth="3" />
        {points.map((r, i) => (
          <circle
            key={r.id}
            cx={40 + (i * 520) / Math.max(points.length - 1, 1)}
            cy={180 - r.overallScore * 1.4}
            r="4"
            fill="#72993e"
          >
            <title>
              {r.title}: {r.overallScore}
            </title>
          </circle>
        ))}
        <text x="40" y="211" fontSize="10" fill="#81857e">
          Earlier
        </text>
        <text x="535" y="211" fontSize="10" fill="#81857e">
          Latest
        </text>
      </svg>
    </div>
  );
}
function ReportTile({
  report: r,
  index,
  onClick,
}: {
  report: Report;
  index: number;
  onClick: () => void;
}) {
  return (
    <button className="report-tile card" onClick={onClick}>
      <div className={"tile-art art-" + (index % 3)}>
        {r.type === "Image" ? (
          <ImageIcon size={32} />
        ) : r.type === "Video" ? (
          <Video size={32} />
        ) : (
          <FileText size={32} />
        )}
        <span>
          {r.sample ? "SAMPLE ANALYSIS" : r.type.toUpperCase() + " CONTENT"}
        </span>
        <b>
          {r.overallScore}
          <small>/100</small>
        </b>
      </div>
      <div className="tile-body">
        <span className="eyebrow">
          {r.platform}{" "}
          <span>
            · {r.sample ? "Demo" : new Date(r.createdAt).toLocaleDateString()}
          </span>
        </span>
        <h4>{r.title}</h4>
        <div>
          <span className="status">
            {r.overallScore >= 75 ? "High potential" : "Room to sculpt"}
          </span>
          <ArrowUpRight size={17} />
        </div>
      </div>
    </button>
  );
}
const blank = (platform: string): Input => ({
  text: "",
  type: "Text",
  platform: platforms.includes(platform) ? platform : "Instagram",
  objective: "Engagement",
  audience: "",
  topic: "",
  cta: "",
});
function AnalyzePage() {
  const { user, reports, toast, usage, refresh } = useApp();
  const nav = useNavigate();
  const [input, setInput] = useState<Input>(() => blank(user!.platform));
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState(0);
  const [error, setError] = useState("");
  const [fileBusy, setFileBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const objectURL = useRef("");
  const longForm = input.platform === LONG_FORM;
  useEffect(
    () => () => {
      if (objectURL.current) URL.revokeObjectURL(objectURL.current);
    },
    [],
  );
  const resetMedia = () => {
    if (objectURL.current) URL.revokeObjectURL(objectURL.current);
    objectURL.current = "";
    setVideoFile(null);
  };
  const phases = [
    "Reading your content",
    "Analyzing the hook",
    "Evaluating audience context",
    "Estimating potential",
    "Sculpting recommendations",
  ];
  const change = (k: keyof Input, v: unknown) =>
    setInput((p) => ({ ...p, [k]: v }));
  async function upload(file?: File) {
    if (!file) return;
    setError("");
    if (
      !["image/png", "image/jpeg", "image/webp", "video/mp4"].includes(
        file.type,
      )
    ) {
      setError("This file type isn’t supported. Try PNG, JPG, WEBP or MP4.");
      return;
    }
    const longVideo = longForm && file.type === "video/mp4";
    if (file.size > (longVideo ? 50 : 10) * 1024 * 1024) {
      setError(
        longVideo
          ? "This video exceeds 50 MB. Use a compressed MP4 or analyze its full transcript."
          : "This file is too large. Maximum size is 10 MB.",
      );
      return;
    }
    setFileBusy(true);
    let pendingURL = "";
    try {
      const media = longVideo
        ? (pendingURL = URL.createObjectURL(file))
        : await new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result));
            reader.onerror = () =>
              reject(new Error("Could not read this file."));
            reader.readAsDataURL(file);
          });
      const type = file.type.startsWith("video") ? "Video" : "Image";
      const meta = await new Promise<Partial<Input>>((resolve, reject) => {
        if (type === "Image") {
          const img = new window.Image();
          img.onload = () =>
            resolve({ mediaWidth: img.width, mediaHeight: img.height });
          img.onerror = () =>
            reject(new Error("This image could not be decoded."));
          img.src = media;
        } else {
          const video = document.createElement("video");
          video.preload = "metadata";
          video.onloadedmetadata = () => {
            if (
              video.duration > (longVideo ? 3600 : 180) ||
              !Number.isFinite(video.duration)
            )
              reject(
                new Error(
                  longVideo
                    ? "Long-form videos must be 60 minutes or less."
                    : "Select YouTube (long-form) for videos longer than 3 minutes.",
                ),
              );
            else
              resolve({
                mediaWidth: video.videoWidth,
                mediaHeight: video.videoHeight,
                duration: video.duration,
              });
          };
          video.onerror = () =>
            longVideo
              ? resolve({})
              : reject(
                  new Error("This video cannot be played in this browser."),
                );
          video.src = media;
        }
      });
      resetMedia();
      if (longVideo) {
        objectURL.current = media;
        setVideoFile(file);
      }
      pendingURL = "";
      setInput((p) => ({ ...p, type, media, mediaName: file.name, ...meta }));
    } catch (e) {
      if (pendingURL) URL.revokeObjectURL(pendingURL);
      setError(err(e));
    } finally {
      setFileBusy(false);
    }
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (input.type !== "Text" && !input.media) {
      setError("Upload your image or video first.");
      return;
    }
    setBusy(true);
    const timer = setInterval(() => setPhase((p) => Math.min(p + 1, 4)), 350);
    try {
      const r =
        videoFile && longForm
          ? await runVideoAnalysis(input, videoFile)
          : await contentAnalysisService.analyze(input);

      refresh().catch(() =>
        toast(
          "Your report is ready. Refresh the library if its count has not updated.",
        ),
      );
      nav("/app/report/" + r.id);
    } catch (e) {
      setError(err(e));
    } finally {
      clearInterval(timer);
      setBusy(false);
      setPhase(0);
    }
  }
  return (
    <main className="app-main">
      <PageHeading
        eyebrow="FROM IDEA TO INTENTION"
        title="Let’s sculpt your content."
        description="Bring your first draft. We’ll help you find its next version."
      />
      <div className="analyze-layout">
        <form className="card analyze-form" onSubmit={submit}>
          <div className="card-heading">
            <h3>Your content</h3>
            <span className="pill">Step 01 → 02</span>
          </div>
          <div className="type-tabs">
            {[
              ["Text", FileText],
              ["Image", ImageIcon],
              ["Video", Video],
            ].map(([t, I]) => {
              const Icon = I as typeof FileText;
              return (
                <button
                  type="button"
                  disabled={busy || fileBusy}
                  key={String(t)}
                  className={input.type === t ? "active" : ""}
                  onClick={() => {
                    resetMedia();
                    setInput((p) => ({
                      ...p,
                      type: String(t),
                      media: undefined,
                      mediaName: undefined,
                      mediaWidth: undefined,
                      mediaHeight: undefined,
                      duration: undefined,
                    }));
                  }}
                >
                  <Icon size={17} />
                  {String(t)}
                </button>
              );
            })}
          </div>
          <label>
            Where will it live?
            <select
              value={input.platform}
              disabled={busy || fileBusy}
              onChange={(e) => {
                resetMedia();
                setInput((p) => ({
                  ...p,
                  platform: e.target.value,
                  media: undefined,
                  mediaName: undefined,
                  duration: undefined,
                }));
              }}
            >
              {platforms.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </label>
          {longForm && (
            <div className="video-workflow-note">
              <span className="eyebrow">LONG-FORM WORKSPACE</span>
              <h3>A full explanation deserves its own review.</h3>
              <p>
                Upload an MP4 up to 60 minutes / 50 MB, or choose Text and
                supply the full transcript. Reviews cover your title, opening,
                actual sections and closing. Saved reports retain sampled frames
                and feedback; full long-form videos are processed temporarily.
              </p>
            </div>
          )}
          {(longForm || input.type === "Video") && (
            <>
              <label>
                Video title
                <input
                  value={input.videoTitle || ""}
                  onChange={(e) => change("videoTitle", e.target.value)}
                  maxLength={140}
                  placeholder="The actual title or the title you plan to publish"
                />
              </label>
              <label>
                Transcript / subtitles (optional)
                <textarea
                  value={input.transcript || ""}
                  onChange={(e) => change("transcript", e.target.value)}
                  rows={6}
                  maxLength={200000}
                  placeholder="Paste the actual spoken words. SRT, WebVTT and timestamped transcripts are supported."
                />
              </label>
              <label className="subtitle-upload">
                Upload subtitles
                <input
                  type="file"
                  accept=".srt,.vtt,.txt"
                  aria-label="Upload subtitles"
                  disabled={busy || fileBusy}
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    if (
                      file.size > 1024 * 1024 ||
                      !/\.(srt|vtt|txt)$/i.test(file.name)
                    ) {
                      setError("Use an SRT, VTT or TXT file under 1 MB.");
                      return;
                    }
                    setFileBusy(true);
                    try {
                      const words = await file.text();
                      if (words.length > 200000)
                        throw new Error(
                          "Use at most 200,000 transcript characters.",
                        );
                      change("transcript", words);
                      setError("");
                      toast(
                        "Subtitles loaded. Their actual words and timestamps will guide the review.",
                      );
                    } catch (e) {
                      setError(err(e));
                    } finally {
                      setFileBusy(false);
                    }
                  }}
                />
              </label>
              <p className="fine-print">
                Transcripts are reviewed as supplied. English overlay text and
                visual/audio measurements come from the file. The app does not
                automatically transcribe speech or identify visual subjects.
              </p>
            </>
          )}
          {input.type !== "Text" && (
            <>
              <div
                className={"upload-zone " + (drag ? "dragging" : "")}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDrag(true);
                }}
                onDragLeave={() => setDrag(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDrag(false);
                  upload(e.dataTransfer.files[0]);
                }}
              >
                <Upload size={28} />
                <h4>
                  {fileBusy
                    ? "Preparing preview…"
                    : "Drop your " + input.type.toLowerCase() + " here"}
                </h4>
                <p>
                  {longForm && input.type === "Video"
                    ? "MP4 · Up to 50 MB / 60 minutes"
                    : "PNG, JPG, WEBP or MP4 · Up to 10 MB"}
                </p>
                <label className="button secondary small">
                  Choose a file
                  <input
                    aria-label="Upload media"
                    type="file"
                    accept={
                      input.type === "Image"
                        ? "image/png,image/jpeg,image/webp"
                        : "video/mp4"
                    }
                    disabled={fileBusy || busy}
                    onChange={(e) => upload(e.target.files?.[0])}
                  />
                </label>
              </div>
              {input.media && (
                <div className="media-preview">
                  {input.type === "Image" ? (
                    <img src={input.media} alt="Your uploaded content" />
                  ) : (
                    <video controls src={input.media} />
                  )}
                  <div>
                    <span>
                      {input.mediaName}
                      {input.mediaWidth
                        ? ` · ${input.mediaWidth} × ${input.mediaHeight}`
                        : " · Metadata will be checked on the server"}
                    </span>
                    <button
                      type="button"
                      className="icon-button"
                      aria-label="Remove uploaded media"
                      onClick={() => {
                        resetMedia();
                        setInput((p) => ({
                          ...p,
                          media: undefined,
                          mediaName: undefined,
                          mediaWidth: undefined,
                          mediaHeight: undefined,
                          duration: undefined,
                        }));
                      }}
                    >
                      <X size={16} />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
          <label>
            {input.type === "Text"
              ? longForm
                ? "Video description / content context"
                : "Caption or content"
              : "Caption / content context (optional)"}
            <textarea
              placeholder="What have you been working on? Add your caption, opening hook, or post idea…"
              value={input.text}
              onChange={(e) => change("text", e.target.value)}
              maxLength={5000}
              rows={7}
              required={input.type === "Text" && !input.transcript?.trim()}
            />
          </label>
          <div className="input-meta">
            <span>A great post starts with a clear idea.</span>
            <span>{input.text.length} / 5,000</span>
          </div>
          <div className="form-grid">
            <label>
              Content objective
              <select
                value={input.objective}
                onChange={(e) => change("objective", e.target.value)}
              >
                {["Reach", "Engagement", "Followers", "Leads", "Awareness"].map(
                  (x) => (
                    <option key={x}>{x}</option>
                  ),
                )}
              </select>
            </label>
            <label>
              Topic / category
              <input
                placeholder="e.g. creative routines"
                value={input.topic}
                maxLength={100}
                onChange={(e) => change("topic", e.target.value)}
              />
            </label>
            <label>
              Target audience
              <input
                placeholder="e.g. independent creators"
                value={input.audience}
                maxLength={150}
                onChange={(e) => change("audience", e.target.value)}
              />
            </label>
            <label>
              Intended call to action
              <input
                placeholder="e.g. save this guide"
                value={input.cta}
                maxLength={150}
                onChange={(e) => change("cta", e.target.value)}
              />
            </label>
          </div>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <button disabled={busy || fileBusy} className="button full">
            <Sparkles size={18} />
            {busy ? "Finding your creative edge…" : "Analyze my content"}
            <ArrowRight size={18} />
          </button>
          <p className="fine-print">{disclaimer}</p>
        </form>
        <aside className="analyze-aside">
          <div className="card">
            <span className="eyebrow">A THOUGHTFUL SECOND LOOK</span>
            <h3>
              Keep your voice.
              <br />
              Find your edge.
            </h3>
            <p>
              We’ll look for the signals that make your message easier to
              understand—and easier to act on.
            </p>
            {[
              "Opening hook",
              "Audience context",
              "Engagement signals",
              "Topic clarity",
              "Caption readability",
            ].map((x, i) => (
              <div className="check-row" key={x}>
                <span>0{i + 1}</span>
                {x}
                <Check size={15} />
              </div>
            ))}
          </div>
          <div className="privacy-note">
            <Shield size={20} />
            <p>Your reports and media are private to your signed-in account.</p>
          </div>
          <button
            className="text-button"
            onClick={() => {
              setInput({ ...samples[0] });
              toast("Sample loaded. Make it your own.");
            }}
          >
            Try a sample caption <ArrowUpRight size={16} />
          </button>
        </aside>
      </div>
      {busy && (
        <div className="processing" role="status">
          <div className="processing-card">
            <div className="processing-orb">
              <Sparkles size={40} />
            </div>
            <span className="eyebrow">INTELLIGENCE IN PROGRESS</span>
            <h2>{phases[phase]}…</h2>
            <div className="processing-steps">
              {phases.map((p, i) => (
                <span key={p} className={i <= phase ? "active" : ""}>
                  {i < phase ? (
                    <Check size={14} />
                  ) : (
                    <span className="green-dot" />
                  )}
                  {p}
                </span>
              ))}
            </div>
            <p>Your creativity is the starting point.</p>
          </div>
        </div>
      )}
    </main>
  );
}
function ReportPage() {
  const { reports, user, refresh, toast } = useApp();
  const location = useLocation();
  const nav = useNavigate();
  const id = location.pathname.split("/").pop()!;
  const sample = id.startsWith("sample-");
  const initial = sample
    ? {
        ...analyze(samples[Number(id.split("-")[1]) % 3] || samples[0]),
        id,
        sample: true,
      }
    : reports.find((r) => r.id === id) || null;
  const [report, setReport] = useState<Report | null>(initial);
  const [version, setVersion] = useState("");
  const [comparison, setComparison] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);
  const [media, setMedia] = useState(report?.media || "");
  const [focusTime, setFocusTime] = useState<number | null>(null);
  const saved = reports.some((r) => r.id === report?.id);
  const [loading, setLoading] = useState(!initial);
  useEffect(() => {
    let active = true;
    setReport(initial);
    setVersion("");
    setComparison(null);
    setFocusTime(null);
    if (!sample) {
      setLoading(true);
      reportFor(id)
        .then((r) => {
          if (active) {
            setReport(r);
            setMedia(r.media || "");
          }
        })
        .catch((e) => {
          if (active) {
            setReport(null);
            setMedia("");
          }
          toast(err(e));
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    } else {
      setMedia(initial?.media || "");
      setLoading(false);
    }
    return () => {
      active = false;
    };
  }, [id]);
  if (loading)
    return (
      <main className="app-main">
        <div className="report-skeleton card">
          <div />
          <div />
          <div />
        </div>
        <p className="fine-print">Loading your private report…</p>
      </main>
    );
  if (!report)
    return (
      <main className="app-main">
        <h1>Report not found.</h1>
        <p>
          This report is unavailable or belongs to another account. Your saved
          reports are in your content library.
        </p>
        <Link to="/app/history" className="button">
          View library
        </Link>
      </main>
    );
  async function save(r: Report) {
    setBusy(true);
    try {
      await persistReport(user!.id, { ...r, sample: false });
      await refresh();
      toast("Analysis saved to your library.");
      return true;
    } catch (e) {
      toast(err(e));
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function copy(t: string) {
    try {
      await navigator.clipboard.writeText(t);
      toast("Copied to clipboard.");
    } catch {
      toast("Clipboard unavailable. Select and copy the text manually.");
    }
  }
  async function useVersion(t: string) {
    setVersion(t);
    setBusy(true);
    try {
      const r = await contentAnalysisService.analyze({
        ...report!,
        text: t,
        applied: true,
        sourceReportId: report!.id,
      });
      setComparison(r);
      await refresh();
      toast("Sculpted version ready to compare.");
    } catch (e) {
      toast(err(e));
    } finally {
      setBusy(false);
    }
  }
  function exportReport() {
    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "trendsculpt-report.json";
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <main className="app-main">
      <Link className="text-button back" to="/app">
        <ArrowLeft size={16} />
        Back to workspace
      </Link>
      <PageHeading
        eyebrow={
          sample
            ? "SAMPLE ANALYSIS · NOT YOUR PERSONAL DATA"
            : "A LITTLE CLARITY FOR YOUR NEXT POST"
        }
        title="Your content intelligence report."
        description={`${report.platform} · ${report.type} · ${new Date(report.createdAt).toLocaleDateString()}`}
        action={
          <div className="actions">
            <button
              className="icon-button"
              title="Export report"
              aria-label="Export report"
              onClick={exportReport}
            >
              <Download size={20} />
            </button>
            <button
              className="button"
              disabled={busy || saved || sample}
              onClick={() => save(report)}
            >
              <Check size={18} />
              {saved
                ? "Saved to library"
                : sample
                  ? "Sample report"
                  : "Save analysis"}
            </button>
          </div>
        }
      />
      <div className="report-top">
        <article className="card primary-score">
          <span className="eyebrow">
            {report.contentReview
              ? "CONTENT REVIEW SCORE"
              : "ENGAGEMENT POTENTIAL"}
          </span>
          <div className="big-score">
            {report.overallScore}
            <span>/100</span>
            <div className="score-orbit">
              <Sparkles size={30} />
            </div>
          </div>
          <span className="status">
            <span className="green-dot" />
            {report.contentReview
              ? "Based on the available content evidence"
              : report.overallScore >= 75
                ? "High engagement potential"
                : report.overallScore >= 55
                  ? "Developing potential"
                  : "A starting point to sculpt"}
          </span>
          <p>{disclaimer}</p>
        </article>
        <article className="card summary-card">
          <span className="eyebrow">
            <Sparkles size={15} /> WHAT THE FRAMEWORK SEES
          </span>
          <h3>{report.title}</h3>
          <p>{report.summary}</p>
          <span className="pill">Local content intelligence · v2</span>
          {media &&
            (report.type === "Image" ? (
              <img
                className="report-media"
                src={media}
                alt="Analyzed content"
              />
            ) : (
              <video className="report-media" src={media} controls />
            ))}
        </article>
      </div>
      <EvidencePanel report={report} />
      <VideoReview
        key={report.id}
        report={report}
        focusTime={focusTime}
        onCopy={copy}
      />
      <div className="score-grid">
        {Object.entries(report.scores).map(([label, n]) => (
          <article className="card score-card" key={label}>
            <span>{label}</span>
            <b>
              {n}
              <small>/100</small>
            </b>
            <div className="progress-track">
              <div style={{ width: n + "%" }} />
            </div>
          </article>
        ))}
      </div>
      <div className="report-columns">
        <article className="card">
          <span className="eyebrow">KEEP THESE SIGNALS</span>
          <h3>What’s working</h3>
          {report.strengths.map((t) => (
            <p className="strength" key={t}>
              <Check size={17} />
              {t}
            </p>
          ))}
        </article>
        <article className="card">
          <span className="eyebrow">SMALL CHANGES. MORE INTENTION.</span>
          <h3>What to refine</h3>
          {report.recommendations.map((r, i) => (
            <div className="recommendation" key={r.title}>
              <span>0{i + 1}</span>
              <div>
                {r.source && (
                  <div className="recommendation-source">
                    <span className="pill">
                      {r.priority || "Medium"} priority · {r.source}
                    </span>
                    {r.timestamp != null && (
                      <button
                        className="text-button"
                        onClick={() => {
                          setFocusTime(r.timestamp!);
                          document
                            .getElementById("video-evidence")
                            ?.scrollIntoView({
                              behavior: "smooth",
                              block: "start",
                            });
                        }}
                      >
                        {timeLabel(r.timestamp)} <ArrowUpRight size={13} />
                      </button>
                    )}
                  </div>
                )}
                <h4>{r.title}</h4>
                <p>{r.reason}</p>
                {r.quote && (
                  <div className="observed-quote">
                    <span className="eyebrow">SOURCE WORDING</span>
                    <p>“{r.quote}”</p>
                  </div>
                )}
                <blockquote>{r.suggestion}</blockquote>
              </div>
            </div>
          ))}
        </article>
      </div>
      <section className="sculpt-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">YOUR IDEA, WITH A FRESH ANGLE</span>
            <h2>Ready to sculpt it?</h2>
          </div>
          <p>
            Suggested starting points—not factual claims.
            <br />
            Edit these to match your voice.
          </p>
        </div>
        <div className="alternatives">
          <div className="card">
            <h3>Better hooks</h3>
            {!report.hooks.length && (
              <p>
                Add a transcript or readable content context to generate wording
                grounded in this video.
              </p>
            )}
            {report.hooks.map((t, i) => (
              <div className="alternative" key={t}>
                <span className="eyebrow">OPTION 0{i + 1}</span>
                <p>{t}</p>
                <button className="text-button" onClick={() => copy(t)}>
                  <Copy size={14} />
                  Copy suggestion
                </button>
              </div>
            ))}
          </div>
          <div className="card">
            <h3>Caption directions</h3>
            {!report.captions.length && (
              <p>
                Caption drafts become available when the report has supplied
                words or readable overlay text.
              </p>
            )}
            {report.captions.map((t, i) => (
              <div className="alternative" key={t}>
                <span className="eyebrow">VERSION 0{i + 1}</span>
                <p>{t}</p>
                <div className="actions">
                  <button className="text-button" onClick={() => copy(t)}>
                    <Copy size={14} />
                    Copy
                  </button>
                  <button
                    className="button secondary small"
                    disabled={busy || sample}
                    onClick={() => useVersion(t)}
                  >
                    Use this version <ArrowRight size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
        <article className="card cta-card">
          <h3>A clearer next step</h3>
          {report.ctas.map((t) => (
            <button className="cta-suggestion" key={t} onClick={() => copy(t)}>
              {t}
              <Copy size={15} />
            </button>
          ))}
        </article>
      </section>
      <section className="card comparison">
        <div className="card-heading">
          <div>
            <span className="eyebrow">BEFORE → AFTER</span>
            <h3>Same idea. A little more intention.</h3>
          </div>
          {comparison && (
            <span className="pill">
              {report.overallScore} → {comparison.overallScore} · Model estimate
            </span>
          )}
        </div>
        <div className="form-grid">
          <div>
            <label>
              Original
              <textarea readOnly value={report.text} rows={7} />
            </label>
          </div>
          <div>
            <label>
              Your sculpted version
              <textarea
                placeholder="Choose a caption above, or write your own revision…"
                value={version}
                onChange={(e) => {
                  setVersion(e.target.value);
                  setComparison(null);
                }}
                rows={7}
                maxLength={5000}
              />
            </label>
            <div className="actions">
              <button
                className="button secondary small"
                disabled={!version.trim() || busy}
                onClick={() => useVersion(version)}
              >
                Compare scores <ArrowRight size={15} />
              </button>
              {comparison && (
                <button
                  className="button small"
                  disabled={busy || sample}
                  onClick={async () => {
                    if (!(await save(comparison))) return;
                    nav("/app/report/" + comparison.id);
                  }}
                >
                  Save revision
                </button>
              )}
            </div>
          </div>
        </div>
        {comparison && (
          <div className="comparison-scores" aria-live="polite">
            {Object.entries(comparison.scores).map(([k, v]) => (
              <div key={k}>
                <span>{k}</span>
                <b>
                  {report.scores[k]} → {v}
                </b>
              </div>
            ))}
          </div>
        )}
        <p className="fine-print">
          A change in estimated score does not imply an actual performance lift.
        </p>
      </section>
      <div className="closing compact">
        <div>
          <h2>Your next idea is waiting.</h2>
          <p>Keep creating. Keep learning.</p>
        </div>
        <Link className="button" to="/app/analyze">
          Analyze another <Plus size={17} />
        </Link>
      </div>
    </main>
  );
}
function Library() {
  const { reports, user, refresh, toast } = useApp();
  const [search, setSearch] = useState("");
  const [platform, setPlatform] = useState("All platforms");
  const [type, setType] = useState("All types");
  const [score, setScore] = useState("All scores");
  const [date, setDate] = useState("");
  const [deleting, setDeleting] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();
  const filtered = reports.filter(
    (r) =>
      (r.title + " " + r.text).toLowerCase().includes(search.toLowerCase()) &&
      (platform === "All platforms" || r.platform === platform) &&
      (type === "All types" || r.type === type) &&
      (score === "All scores" ||
        (score === "75 and above"
          ? r.overallScore >= 75
          : r.overallScore < 75)) &&
      (!date || r.createdAt.slice(0, 10) === date),
  );
  const clear = () => {
    setSearch("");
    setPlatform("All platforms");
    setType("All types");
    setScore("All scores");
    setDate("");
  };
  async function remove() {
    setBusy(true);
    try {
      await removeReport(user!.id, deleting!);
      await refresh();
      setDeleting(null);
      toast("Analysis deleted.");
    } catch (e) {
      toast(err(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="app-main">
      <PageHeading
        eyebrow="YOUR IDEAS, ALL IN ONE PLACE"
        title="The content library."
        description="A record of your creative process. Revisit, refine, repeat."
        action={
          <Link to="/app/analyze" className="button">
            <Plus size={18} />
            Analyze new content
          </Link>
        }
      />
      <div className="library-filters card">
        <label className="search-input">
          <Search size={17} />
          <input
            aria-label="Search analyses"
            placeholder="Find an idea…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <select
          aria-label="Filter by platform"
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
        >
          {["All platforms", ...platforms].map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
        <select
          aria-label="Filter by type"
          value={type}
          onChange={(e) => setType(e.target.value)}
        >
          {["All types", "Text", "Image", "Video"].map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
        <select
          aria-label="Filter by score"
          value={score}
          onChange={(e) => setScore(e.target.value)}
        >
          {["All scores", "75 and above", "Below 75"].map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
        <input
          type="date"
          aria-label="Filter by date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
      </div>
      <div className="library-count">
        <span>
          {filtered.length} saved{" "}
          {filtered.length === 1 ? "analysis" : "analyses"}
        </span>
        <button className="text-button" onClick={clear}>
          Clear filters
        </button>
      </div>
      {filtered.length ? (
        <div className="report-grid">
          {filtered.map((r, i) => (
            <div key={r.id} className="library-item">
              <ReportTile
                report={r}
                index={i}
                onClick={() => nav("/app/report/" + r.id)}
              />
              <button
                className="delete-tile icon-button"
                aria-label={"Delete " + r.title}
                onClick={() => setDeleting(r)}
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="card empty-state">
          <div className="empty-icon">
            <Layers size={35} />
          </div>
          <h2>
            {reports.length
              ? "Nothing matches these filters."
              : "Your first content is waiting to be sculpted."}
          </h2>
          <p>
            {reports.length
              ? "Try another search or clear your filters."
              : "Your saved reports will appear here. Every idea is a new starting point."}
          </p>
          {reports.length ? (
            <button className="button" onClick={clear}>
              Clear filters
            </button>
          ) : (
            <Link className="button" to="/app/analyze">
              Analyze your first post <ArrowRight size={18} />
            </Link>
          )}
        </div>
      )}
      {deleting && (
        <Confirm
          title="Delete this analysis?"
          description="The saved report and its uploaded media will be removed. This can’t be undone."
          confirm="Delete analysis"
          busy={busy}
          onConfirm={remove}
          onCancel={() => setDeleting(null)}
        />
      )}
    </main>
  );
}
function Confirm({
  title,
  description,
  confirm,
  busy,
  onConfirm,
  onCancel,
}: {
  title: string;
  description: string;
  confirm: string;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    const listener = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onCancel();
      if (e.key === "Tab") {
        const buttons = ref.current?.querySelectorAll<HTMLButtonElement>(
          "button:not(:disabled)",
        );
        if (!buttons?.length) {
          e.preventDefault();
          return;
        }
        const first = buttons[0],
          last = buttons[buttons.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", listener);
    return () => {
      window.removeEventListener("keydown", listener);
      previous?.focus();
    };
  }, [busy]);
  return (
    <div className="modal-overlay">
      <div
        ref={ref}
        className="modal card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
      >
        <h2 id="confirm-title">{title}</h2>
        <p>{description}</p>
        <div className="actions">
          <button
            autoFocus
            className="button secondary"
            onClick={onCancel}
            disabled={busy}
          >
            Keep it
          </button>
          <button className="button danger" onClick={onConfirm} disabled={busy}>
            {busy ? "Removing…" : confirm}
          </button>
        </div>
      </div>
    </div>
  );
}
function EvidencePanel({ report }: { report: Report }) {
  const evidence = report.evidence;
  const visual = report.mediaAnalysis;
  if (!evidence && !visual)
    return (
      <div className="evidence-note">
        <Shield size={16} />
        This platform has no matching local training dataset. Scores use the
        transparent content framework.
      </div>
    );
  return (
    <section className="evidence-section">
      <div className="card-heading">
        <div>
          <span className="eyebrow">KNOW WHAT’S BEHIND THE SCORE</span>
          <h3>Evidence, with context.</h3>
        </div>
        <Link className="text-button" to="/app/sources">
          Explore data & models <ArrowUpRight size={15} />
        </Link>
      </div>
      <div className="evidence-grid">
        {evidence && (
          <article className="card">
            <span className="pill">
              {evidence.platform} · Limited confidence
            </span>
            <h3>
              {evidence.datasetRows.toLocaleString()} observations. One
              perspective.
            </h3>
            <p>
              Historical-pattern estimate: <b>{evidence.historicalEstimate}%</b>{" "}
              interactions per exposure. Error-band reference:{" "}
              {evidence.range[0]}–{evidence.range[1]}%. This is not a prediction
              of your actual post’s engagement.
            </p>
            <div className="evidence-numbers">
              <div>
                <b>{evidence.matchedRows}</b>
                <span>Similar reference records</span>
              </div>
              <div>
                <b>{evidence.similarity.toFixed(2)}</b>
                <span>Maximum text similarity</span>
              </div>
              <div>
                <b>{evidence.validation.holdoutMAE}</b>
                <span>Holdout error (percentage points)</span>
              </div>
            </div>
            <p className="fine-print">
              {evidence.modelUsedForScore
                ? "The model contributed a limited 20% adjustment to the engagement signal."
                : "The model was not used to adjust the score because relevance or validation was insufficient."}
            </p>
            <details>
              <summary>
                Dataset context & limitations <ChevronDown size={14} />
              </summary>
              <p>
                {evidence.validation.label}. {evidence.validation.limitations}
              </p>
              <p>{evidence.note}</p>
              {evidence.neighbors.map((n, i) => (
                <div className="neighbor" key={i}>
                  <span>{n.title}</span>
                  <b>{n.observedRate}%</b>
                </div>
              ))}
            </details>
          </article>
        )}
        {visual && (
          <article className="card">
            <span className="pill">
              {report.type === "Video"
                ? "Sampled video frames"
                : "Image measurements"}
            </span>
            <h3>We looked at the actual pixels.</h3>
            <div className="evidence-numbers">
              <div>
                <b>{visual.brightness}</b>
                <span>Opening luminance / 255</span>
              </div>
              <div>
                <b>{visual.contrast}</b>
                <span>Measured contrast</span>
              </div>
              <div>
                <b>{visual.framesSampled}</b>
                <span>Frames measured</span>
              </div>
            </div>
            <p>
              {visual.width} × {visual.height} px{" "}
              {visual.duration
                ? `· ${visual.duration.toFixed(1)} seconds · ${visual.hasAudio ? "Audio track present" : "No audio track"}`
                : ""}
            </p>
            <p className="fine-print">{visual.limits}</p>
          </article>
        )}
      </div>
    </section>
  );
}
function VideoReview({
  report,
  focusTime,
  onCopy,
}: {
  report: Report;
  focusTime: number | null;
  onCopy: (text: string) => void;
}) {
  const context = report.contentReview;
  const timeline = report.mediaAnalysis?.timeline || [];
  const [selected, setSelected] = useState(0);
  useEffect(() => {
    if (focusTime != null && timeline.length)
      setSelected(
        timeline.reduce(
          (best, f, i) =>
            Math.abs(f.timestamp - focusTime) <
            Math.abs(timeline[best].timestamp - focusTime)
              ? i
              : best,
          0,
        ),
      );
  }, [focusTime]);
  if (!context && !timeline.length) return null;
  const frame = timeline[selected];
  return (
    <section className="video-review card" id="video-evidence">
      <div className="card-heading">
        <div>
          <span className="eyebrow">FROM YOUR WORDS & YOUR FILE</span>
          <h2>
            {context?.longForm
              ? "Your long-form review."
              : "Your video, reviewed in context."}
          </h2>
        </div>
        <span className="pill">
          {context?.source || "Sampled video measurements"}
        </span>
      </div>
      {context && (
        <>
          <p className="fine-print">{context.coverage}</p>
          {!!context.keywords.length && (
            <div className="review-keywords">
              {context.keywords.map((word) => (
                <span className="pill" key={word}>
                  {word}
                </span>
              ))}
            </div>
          )}
          {context.openingQuote && (
            <div className="review-quotes">
              <div>
                <span className="eyebrow">OPENING IN THE SUPPLIED WORDS</span>
                <p>“{context.openingQuote}”</p>
              </div>
              <div>
                <span className="eyebrow">CLOSING IN THE SUPPLIED WORDS</span>
                <p>“{context.closingQuote}”</p>
              </div>
            </div>
          )}
        </>
      )}
      {frame && (
        <>
          <div className="sample-controls" aria-label="Video timeline samples">
            {timeline.map((f, i) => (
              <button
                key={f.timestamp}
                className={i === selected ? "active" : ""}
                onClick={() => setSelected(i)}
                aria-label={`Inspect sample at ${timeLabel(f.timestamp)}`}
                aria-pressed={i === selected}
              >
                {timeLabel(f.timestamp)}
              </button>
            ))}
          </div>
          <div className="sample-frame">
            <img
              src={frame.thumbnail}
              alt={`Video sample at ${timeLabel(frame.timestamp)}`}
            />
            <div>
              <span className="eyebrow">
                ACTUAL FRAME · {timeLabel(frame.timestamp)}
              </span>
              <h3>
                {frame.overlayText
                  ? "Text estimated from this frame"
                  : "A closer look at this moment"}
              </h3>
              <p>
                {frame.overlayText ||
                  (frame.ocrStatus === "completed"
                    ? "No readable English overlay text was detected in this sample."
                    : "Overlay text was not read for this sample. Inspect the preview or use your transcript for wording feedback.")}
              </p>
              <div className="sample-metrics">
                <span>
                  Luminance <b>{frame.brightness}/255</b>
                </span>
                <span>
                  Contrast <b>{frame.contrast}</b>
                </span>
                <span>
                  Clipped pixels <b>{frame.clippedPercent}%</b>
                </span>
              </div>
              <p className="fine-print">
                Compare this preview with the edit suggestion. Sparse frames do
                not describe everything between samples.
              </p>
            </div>
          </div>
        </>
      )}
      {context?.longForm && (
        <div className="long-form-structure">
          <div className="card-heading">
            <div>
              <span className="eyebrow">A STARTING POINT FOR YOUR EDIT</span>
              <h3>Chapter draft from your transcript</h3>
            </div>
            {!!context.chapters.length && (
              <button
                className="text-button"
                onClick={() =>
                  onCopy(
                    context.chapters
                      .map(
                        (c, i) =>
                          `${c.timestamp == null ? `Section ${i + 1}` : timeLabel(c.timestamp)} ${c.title}`,
                      )
                      .join("\n"),
                  )
                }
              >
                <Copy size={15} />
                Copy chapter draft
              </button>
            )}
          </div>
          {context.chapters.length ? (
            <ol className="chapter-list">
              {context.chapters.map((c, i) => (
                <li key={i}>
                  <span>
                    {c.timestamp == null
                      ? `Section ${i + 1}`
                      : timeLabel(c.timestamp)}
                  </span>
                  <p>{c.title}</p>
                </li>
              ))}
            </ol>
          ) : (
            <p>
              Add the full transcript or subtitles to review the sequence and
              draft chapters.
            </p>
          )}
          <p className="fine-print">
            Review these boundaries before publishing. YouTube chapters start at
            0:00, need at least 3 chapters and each must be at least 10 seconds.
            Untimed text produces section ideas, not invented timestamps.
          </p>
        </div>
      )}
      {context?.longForm && timeline.length > 0 && !report.media && (
        <p className="fine-print">
          Your saved report contains these sampled frames and the review. The
          full long-form upload was processed temporarily.
        </p>
      )}
    </section>
  );
}
function SourcesPage() {
  const { toast } = useApp();
  const [own, setOwn] = useState<any[]>([]);
  const [platform, setPlatform] = useState("Instagram");
  const [csv, setCsv] = useState("");
  const [fileName, setFileName] = useState("");
  const [permission, setPermission] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState("");
  const reload = () => api<any[]>("/datasets").then(setOwn);
  useEffect(() => {
    reload().catch((e) => toast(err(e)));
  }, []);
  async function upload(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/datasets", {
        method: "POST",
        body: JSON.stringify({ platform, csv, permission }),
      });
      await reload();
      toast(
        "Private dataset trained. New analyses will use your matching platform model.",
      );
      setCsv("");
      setFileName("");
      setPermission(false);
    } catch (e) {
      setError(err(e));
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    setBusy(true);
    try {
      await api("/datasets/" + deleting, { method: "DELETE" });
      await reload();
      setDeleting("");
      toast(
        "Private dataset removed. New reports use the bundled reference model.",
      );
    } catch (e) {
      toast(err(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="app-main">
      <PageHeading
        eyebrow="MORE CONTEXT. BETTER QUESTIONS."
        title="Data & model studio."
        description="Know where your signals come from. Bring your own observations."
      />
      <div className="source-model-grid">
        {modelData.models.map((m) => (
          <article className="card" key={m.platform}>
            <span className="eyebrow">BUNDLED LOCAL MODEL</span>
            <h2>{m.platform}</h2>
            <p>{m.label}</p>
            <div className="evidence-numbers">
              <div>
                <b>{m.rows.toLocaleString()}</b>
                <span>Training observations</span>
              </div>
              <div>
                <b>{m.testRows}</b>
                <span>Grouped holdout records</span>
              </div>
            </div>
            <details>
              <summary>
                Validation & method <ChevronDown size={14} />
              </summary>
              <p>{m.method}</p>
              <p>
                Mean absolute error: {m.holdoutMAE} percentage points.
                Median-only baseline: {m.baselineMAE}. Better than baseline:{" "}
                {m.beatsBaseline ? "yes" : "no"}. This is a single offline
                split, not a production accuracy guarantee.
              </p>
              <p>{m.limitations}</p>
            </details>
          </article>
        ))}
      </div>
      <section className="dataset-import card">
        <div>
          <span className="eyebrow">YOUR DATA, YOUR WORKSPACE</span>
          <h2>Bring your own evidence.</h2>
          <p>
            Upload a CSV from Kaggle, Hugging Face, a permitted YouTube API
            export, or your own Instagram insights. We train a private local
            model and use it only for your account.
          </p>
          <p>
            Use 20–5,000 valid records, under 5 MB. Columns:{" "}
            <code>caption</code>, <code>title</code> or <code>text</code>;{" "}
            <code>impressions</code> for Instagram or <code>views</code> for
            YouTube; plus <code>likes</code> and <code>comments</code>.
            Instagram can include <code>shares</code> and <code>saves</code>.
            Add <code>channel_id</code> when combining channels.
          </p>
          <div className="actions">
            <a
              className="text-button"
              href="https://www.kaggle.com/datasets"
              target="_blank"
              rel="noreferrer"
            >
              Find Kaggle datasets <ArrowUpRight size={14} />
            </a>
            <a
              className="text-button"
              href="https://huggingface.co/datasets"
              target="_blank"
              rel="noreferrer"
            >
              Explore Hugging Face <ArrowUpRight size={14} />
            </a>
          </div>
          <p className="fine-print">
            Direct hosted connectors are not configured. Uploaded CSVs work now.
            Never upload data you lack permission to process.
          </p>
        </div>
        <form onSubmit={upload}>
          <label>
            Dataset platform
            <select
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
            >
              <option>Instagram</option>
              <option>YouTube</option>
            </select>
          </label>
          <label>
            CSV dataset
            <input
              type="file"
              accept=".csv,text/csv"
              required
              onChange={async (e) => {
                setError("");
                const f = e.target.files?.[0];
                if (!f) return;
                if (f.size > 5 * 1024 * 1024) {
                  setError("Dataset must be under 5 MB.");
                  setCsv("");
                  return;
                }
                setFileName(f.name);
                setCsv(await f.text());
              }}
            />
          </label>
          <span className="fine-print">{fileName}</span>
          <label className="checkbox">
            <input
              type="checkbox"
              required
              checked={permission}
              onChange={(e) => setPermission(e.target.checked)}
            />
            I have permission to use these records.
          </label>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <button className="button full" disabled={busy || !csv}>
            {busy ? "Validating and training…" : "Train my private model"}
            <Sparkles size={17} />
          </button>
        </form>
      </section>
      {own.length > 0 && (
        <section className="card private-datasets">
          <h3>Your private models</h3>
          {own.map((m) => (
            <div className="private-model" key={m.platform}>
              <div>
                <b>
                  {m.platform} · {m.rows} records
                </b>
                <p>
                  {m.beatsBaseline
                    ? "Beat the median-only holdout baseline."
                    : "Did not beat the baseline; score adjustments are disabled."}{" "}
                  Holdout error: {m.holdoutMAE} percentage points.
                </p>
              </div>
              <button
                className="icon-button"
                aria-label={"Delete " + m.platform + " dataset"}
                onClick={() => setDeleting(m.platform)}
              >
                <Trash2 size={17} />
              </button>
            </div>
          ))}
        </section>
      )}
      <details className="card source-ledger">
        <summary>
          Public source ledger <ChevronDown size={17} />
        </summary>
        {modelData.sources.map((s) => (
          <div key={s.file}>
            <a href={s.source} target="_blank" rel="noreferrer">
              {s.file} <ArrowUpRight size={13} />
            </a>
            <span>{s.rows} source rows · SHA-256 verified</span>
          </div>
        ))}
      </details>
      {deleting && (
        <Confirm
          title="Delete this private dataset?"
          description="The private model and training observations will be removed. Your saved reports remain available with their original evidence."
          confirm="Delete dataset"
          busy={busy}
          onConfirm={remove}
          onCancel={() => setDeleting("")}
        />
      )}
    </main>
  );
}

function Profile({ settings = false }: { settings?: boolean }) {
  const { user, setUser, reports, refresh, toast, usage } = useApp();
  const [name, setName] = useState(user!.name);
  const [platform, setPlatform] = useState(user!.platform);
  const [creator, setCreator] = useState(user!.creator);
  const [notify, setNotify] = useState(user!.notifications);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const u = {
        ...user!,
        name: name.trim(),
        platform,
        creator,
        notifications: notify,
      };
      await persistProfile(u);
      setUser(u);
      toast("Your preferences are saved.");
    } catch (e) {
      toast(err(e));
    } finally {
      setBusy(false);
    }
  }
  async function removeAll() {
    setBusy(true);
    try {
      await deleteAccount(deletePassword);
      setUser(null);

      toast("Account and private data deleted.");
    } catch (e) {
      toast(err(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="app-main">
      <PageHeading
        eyebrow="MAKE THIS SPACE YOURS"
        title={settings ? "Your preferences." : "Your creator profile."}
        description="A few details to help your workspace feel more like you."
      />
      <div className="profile-layout">
        <form className="card" onSubmit={save}>
          <div className="profile-header">
            <span className="avatar large">
              {name.slice(0, 2).toUpperCase()}
            </span>
            <div>
              <h3>{name}</h3>
              <p>Free creator account</p>
            </div>
          </div>
          <label>
            Full name
            <input
              required
              maxLength={80}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label>
            Email
            <input readOnly value={user!.email} />
          </label>
          <div className="form-grid">
            <label>
              Primary platform
              <select
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
              >
                {[...platforms, "Other"].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </label>
            <label>
              Creator type
              <select
                value={creator}
                onChange={(e) => setCreator(e.target.value)}
              >
                {creators.map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </label>
          </div>
          {settings && (
            <div className="notification-row">
              <div>
                <h4>Email notifications</h4>
                <p>
                  Preference stored for future notification support.
                  <br />
                  Email delivery is not enabled in this MVP.
                </p>
              </div>
              <input
                type="checkbox"
                aria-label="Email notification preference"
                checked={notify}
                onChange={(e) => setNotify(e.target.checked)}
              />
            </div>
          )}
          <button className="button" disabled={busy}>
            Save changes <Check size={17} />
          </button>
        </form>
        <div>
          <article className="card">
            <span className="eyebrow">YOUR WORKSPACE</span>
            <h3>Room to experiment.</h3>
            <p>{usage.count} / 100 analyses this month.</p>
            <p>
              Your free workspace includes 100 analyses per month, enforced by
              the server.
            </p>
            <Link to="/privacy" className="text-button">
              Content & privacy <ArrowUpRight size={16} />
            </Link>
          </article>
          {settings && (
            <article className="card danger-zone">
              <h3>{"Delete account"}</h3>
              <p>
                Remove this profile, its reports, and uploaded content. This
                action can’t be undone.
              </p>
              <label>
                Confirm account password
                <input
                  type="password"
                  value={deletePassword}
                  onChange={(e) => setDeletePassword(e.target.value)}
                  autoComplete="current-password"
                />
              </label>
              <button
                className="button secondary"
                disabled={!deletePassword}
                onClick={() => setConfirm(true)}
              >
                <Trash2 size={16} />
                {"Delete account"}
              </button>
            </article>
          )}
        </div>
      </div>
      {confirm && (
        <Confirm
          title={"Delete your account?"}
          description="Your profile and saved analyses will be permanently removed."
          confirm="Delete my data"
          busy={busy}
          onConfirm={removeAll}
          onCancel={() => setConfirm(false)}
        />
      )}
    </main>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
