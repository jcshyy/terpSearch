import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import terpLogo from "./assets/terpcolored.png";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

const GENED_OPTIONS = [
  { value: "", label: "Any requirement" },
  { value: "SCIS", label: "I-Series (SCIS)" },
  { value: "DSHU", label: "Humanities (DSHU)" },
  { value: "DSHS", label: "History & Social Sciences (DSHS)" },
  { value: "DSNS", label: "Natural Sciences (DSNS)" },
  { value: "DSNL", label: "Natural Science Lab (DSNL)" },
  { value: "DSSP", label: "Scholarship in Practice (DSSP)" },
  { value: "DVCC", label: "Cultural Competence (DVCC)" },
  { value: "DVUP", label: "Understanding Plural Societies (DVUP)" },
  { value: "FSAW", label: "Academic Writing (FSAW)" },
  { value: "FSAR", label: "Analytic Reasoning (FSAR)" },
  { value: "FSMA", label: "Math (FSMA)" },
  { value: "FSOC", label: "Oral Communication (FSOC)" },
  { value: "FSPW", label: "Professional Writing (FSPW)" },
];

const EASE_OPTIONS = [
  { value: "", label: "Any ease" },
  { value: "0.4", label: "40+ / 100" },
  { value: "0.6", label: "60+ / 100" },
  { value: "0.8", label: "80+ / 100" },
];

const SORT_OPTIONS = [
  { value: "relevance", label: "Relevance" },
  { value: "gpa", label: "Avg GPA" },
  { value: "ease", label: "Ease" },
  { value: "popularity", label: "Popularity" },
];

const PAGE_SIZE_OPTIONS = [
  { value: 12, label: "12 / page" },
  { value: 24, label: "24 / page" },
  { value: 48, label: "48 / page" },
];

const SURFACE = "rounded-xl border border-slate-200 bg-white shadow-sm";
const UMD_LOGO_PATH = terpLogo;

const QUICK_SEARCH_CHIPS = [
  { label: "DVUP", query: "DVUP" },
  { label: "DSHU", query: "DSHU" },
  { label: "DSSP", query: "DSSP" },
  { label: "I-Series", query: "I-Series" },
  { label: "Easy GPA", query: "easy GPA" },
  { label: "Easy workload", query: "easy workload" },
  { label: "Humanities", query: "humanities" },
  { label: "Ethics", query: "ethics" },
];

function formatGpa(value) {
  return value == null || Number.isNaN(Number(value)) ? "--" : Number(value).toFixed(2);
}

function formatEase(value) {
  if (value == null || Number.isNaN(Number(value))) return "--";
  return `${Math.round(Number(value) * 100)}`;
}

function formatCount(value) {
  return value == null || Number.isNaN(Number(value))
    ? "--"
    : Number(value).toLocaleString();
}

function splitCourseTitle(title, fallbackId) {
  if (!title) return { code: fallbackId || "Course", name: "" };
  const parts = title.split(" - ");
  if (parts.length === 1) return { code: fallbackId || parts[0], name: "" };
  return { code: parts[0], name: parts.slice(1).join(" - ") };
}

function buildPageWindow(currentPage, totalPages) {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const pages = [1];
  const start = Math.max(2, currentPage - 1);
  const end = Math.min(totalPages - 1, currentPage + 1);

  if (start > 2) pages.push("left-ellipsis");

  for (let page = start; page <= end; page += 1) {
    pages.push(page);
  }

  if (end < totalPages - 1) pages.push("right-ellipsis");

  pages.push(totalPages);
  return pages;
}

function StatCard({ label, value, hint }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
      <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
        {label}
      </div>
      <div className="mt-2 text-3xl font-black tracking-tight text-slate-950">
        {value}
      </div>
      <div className="mt-1 text-sm text-slate-500">{hint}</div>
    </div>
  );
}

function StatPill({ label, value, accent = "default" }) {
  const accentClass =
    accent === "gold"
      ? "border-amber-300 bg-amber-50 text-amber-950"
      : accent === "red"
        ? "border-rose-200 bg-rose-50 text-rose-950"
        : "border-slate-200 bg-white text-slate-900";

  return (
    <div
      className={`inline-flex items-center gap-2 rounded-md border px-3 py-1.5 ${accentClass}`}
    >
      <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
        {label}
      </span>
      <span className="text-sm font-black tracking-tight">{value}</span>
    </div>
  );
}

function FilterField({ label, info, children }) {
  return (
    <label className="flex min-w-0 flex-col gap-2">
      <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
        <span>{label}</span>
        {info ? (
          <span className="group relative inline-flex">
            <span
              tabIndex={0}
              role="img"
              aria-label={`${label} info`}
              className="inline-flex h-[18px] w-[18px] items-center justify-center rounded-md border border-slate-300 bg-white text-[11px] font-bold normal-case tracking-normal text-slate-500 transition hover:border-rose-400 hover:text-rose-700 focus:border-rose-400 focus:text-rose-700 focus:outline-none"
            >
              i
            </span>
            <span className="pointer-events-none absolute left-1/2 top-full z-20 mt-2 hidden w-56 -translate-x-1/2 rounded-lg border border-slate-200 bg-slate-950 px-3 py-2 text-[11px] font-medium normal-case tracking-normal text-white shadow-lg group-hover:block group-focus-within:block">
              {info}
            </span>
          </span>
        ) : null}
      </span>
      {children}
    </label>
  );
}

function MetricPill({ tone = "default", children }) {
  const toneClass =
    tone === "gold"
      ? "border-amber-300 bg-amber-50 text-amber-900"
      : tone === "red"
        ? "border-rose-300 bg-rose-50 text-rose-900"
        : "border-slate-200 bg-slate-50 text-slate-700";

  return (
    <span
      className={`inline-flex items-center rounded-md border px-2.5 py-1 text-xs font-semibold ${toneClass}`}
    >
      {children}
    </span>
  );
}

function LoadingSplash({ logoVisible, onLogoError, reducedMotion }) {
  return (
    <div className="splash-screen" aria-hidden="true">
      <div className="splash-mark">
        {logoVisible ? (
          <img
            src={UMD_LOGO_PATH}
            alt=""
            onError={onLogoError}
            className={`splash-logo ${reducedMotion ? "splash-static" : ""}`}
          />
        ) : (
          <div className={`splash-fallback ${reducedMotion ? "splash-static" : ""}`}>TS</div>
        )}
      </div>
      <div className={`splash-wordmark ${reducedMotion ? "splash-static" : ""}`}>
        TerpSearch
      </div>
      <div className="splash-subtitle">UMD course search by GPA, ease, reviews, and GenEds</div>
    </div>
  );
}

function DashboardChart({ results }) {
  const data = useMemo(
    () =>
      (results || [])
        .filter((result) => result.kind === "course" && result.meta?.avg_gpa != null)
        .slice()
        .sort((a, b) => Number(b.meta?.avg_gpa || 0) - Number(a.meta?.avg_gpa || 0))
        .slice(0, 8)
        .map((result) => {
          const { code } = splitCourseTitle(result.title, result.meta?.course_id);
          return {
            code,
            gpa: Number(result.meta?.avg_gpa || 0),
          };
        }),
    [results],
  );

  return (
    <section className={`${SURFACE} p-6`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-950">Top GPAs in this result set</h2>
          <p className="mt-1 text-sm text-slate-500">
            A quick scan of the highest-average GPA courses currently on screen.
          </p>
        </div>
      </div>

      <div className="mt-5 h-72">
        {data.length === 0 ? (
          <div className="flex h-full items-center justify-center rounded-3xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500">
            Search for courses with GPA data to populate this chart.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 10, right: 12, left: -16, bottom: 8 }}>
              <CartesianGrid vertical={false} stroke="rgba(148,163,184,0.25)" />
              <XAxis
                dataKey="code"
                tickLine={false}
                axisLine={false}
                tick={{ fill: "#475569", fontSize: 12 }}
              />
              <YAxis
                domain={[2, 4]}
                tickLine={false}
                axisLine={false}
                tick={{ fill: "#475569", fontSize: 12 }}
              />
              <Tooltip
                cursor={{ fill: "rgba(226,24,51,0.06)" }}
                contentStyle={{
                  borderRadius: 16,
                  border: "1px solid rgba(226,232,240,1)",
                  boxShadow: "0 16px 40px rgba(15,23,42,0.12)",
                }}
              />
              <Bar dataKey="gpa" fill="#E21833" radius={[10, 10, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}

function CourseCard({ result, onSelect }) {
  const { code, name } = splitCourseTitle(result.title, result.meta?.course_id);
  const preview = result.meta?.description || result.snippet || "";
  const genedTags = (result.meta?.geneds || "")
    .split(" ")
    .map((tag) => tag.trim())
    .filter(Boolean);

  return (
    <button
      type="button"
      onClick={() => onSelect(code)}
      className={`${SURFACE} group w-full p-5 text-left transition hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-rose-100`}
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-sm font-semibold uppercase tracking-[0.22em] text-rose-600">
                {code}
              </div>
              <h3 className="mt-2 text-xl font-bold tracking-tight text-slate-950">
                {name || "Course overview"}
              </h3>
            </div>

            <div className="hidden items-center gap-2 rounded-md border border-slate-200 bg-stone-50 px-3 py-1 text-xs font-semibold text-slate-700 sm:inline-flex">
              View details
              <span className="transition group-hover:translate-x-0.5">-&gt;</span>
            </div>
          </div>

          {preview ? (
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
              {preview.length > 220 ? `${preview.slice(0, 220)}...` : preview}
            </p>
          ) : (
            <p className="mt-3 text-sm leading-6 text-slate-400">
              No course description is available for this result yet.
            </p>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            {genedTags.map((tag) => (
              <MetricPill key={tag}>{tag}</MetricPill>
            ))}
            {result.meta?.credits != null && (
              <MetricPill>{`${result.meta.credits} credits`}</MetricPill>
            )}
            {result.meta?.popularity != null && (
              <MetricPill>{`${formatCount(result.meta.popularity)} graded`}</MetricPill>
            )}
          </div>
        </div>

        <div className="grid min-w-[250px] grid-cols-3 gap-2">
          <div className="rounded-lg border border-slate-200 bg-stone-50 px-3 py-3">
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Avg GPA
            </div>
            <div className="mt-2 text-2xl font-black text-slate-950">
              {formatGpa(result.meta?.avg_gpa)}
            </div>
          </div>
          <div className="rounded-lg border border-slate-200 bg-stone-50 px-3 py-3">
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Ease
            </div>
            <div className="mt-2 text-2xl font-black text-slate-950">
              {formatEase(result.meta?.ease_score)}
            </div>
          </div>
          <div className="rounded-lg border border-slate-200 bg-stone-50 px-3 py-3">
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Popularity
            </div>
            <div className="mt-2 text-2xl font-black text-slate-950">
              {formatCount(result.meta?.popularity)}
            </div>
          </div>
        </div>
      </div>
    </button>
  );
}

function DetailSection({ title, children, action }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <h3 className="text-base font-bold text-slate-950">{title}</h3>
        {action}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function GradeDistributionCard({ detail }) {
  const chartData = Array.isArray(detail?.grade_distribution)
    ? detail.grade_distribution
    : [];

  if (!chartData.length) {
    return (
      <DetailSection title="Grade distribution">
        <div className="rounded-xl border border-dashed border-slate-200 bg-stone-50 px-5 py-10 text-center text-sm text-slate-500">
          Grade distribution unavailable.
        </div>
      </DetailSection>
    );
  }

  return (
    <DetailSection title="Grade distribution">
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 10, right: 6, left: -24, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="rgba(148,163,184,0.22)" />
            <XAxis dataKey="grade" tickLine={false} axisLine={false} />
            <YAxis tickLine={false} axisLine={false} />
            <Tooltip />
            <Bar dataKey="count" fill="#FFD200" radius={[10, 10, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </DetailSection>
  );
}

function CourseDetailModal({ courseId, detail, loading, error, onClose }) {
  useEffect(() => {
    if (!courseId) return undefined;

    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose();
    };

    document.body.classList.add("modal-open");
    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.classList.remove("modal-open");
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [courseId, onClose]);

  if (!courseId) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4 py-6 backdrop-blur-sm">
      <div className="absolute inset-0" onClick={onClose} />
      <div className="relative z-10 max-h-[92vh] w-full max-w-5xl overflow-y-auto rounded-xl border border-slate-200 bg-[#fcfcfb] shadow-xl">
        <div className="sticky top-0 z-10 border-b border-slate-200 bg-[#fcfcfb]/95 px-6 py-5 backdrop-blur sm:px-8">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-sm font-semibold uppercase tracking-[0.22em] text-rose-600">
                {courseId}
              </div>
              <h2 className="mt-2 text-2xl font-black tracking-tight text-slate-950">
                {detail?.title || "Course details"}
              </h2>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-stone-50"
            >
              Close
            </button>
          </div>
        </div>

        <div className="p-6 sm:p-8">
          {loading ? (
            <div className="flex min-h-[320px] items-center justify-center rounded-xl border border-dashed border-slate-200 bg-white text-sm text-slate-500">
              Loading course details...
            </div>
          ) : error ? (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700">
              {error}
            </div>
          ) : !detail ? (
            <div className="rounded-xl border border-slate-200 bg-white px-5 py-4 text-sm text-slate-500">
              No course details available.
            </div>
          ) : (
            <div className="space-y-6">
              <div className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
                <DetailSection
                  title="Course overview"
                  action={
                    <a
                      href={detail.planetterp_url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-md border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-700 transition hover:bg-stone-50"
                    >
                      Open on PlanetTerp
                    </a>
                  }
                >
                  <p className="text-sm leading-7 text-slate-600">
                    {detail.description || "No full course description is available."}
                  </p>
                  <div className="mt-5 flex flex-wrap gap-2">
                    {detail.geneds?.map((tag) => (
                      <MetricPill key={tag}>{tag}</MetricPill>
                    ))}
                    {detail.credits != null && (
                      <MetricPill>{`${detail.credits} credits`}</MetricPill>
                    )}
                    {detail.pct_ab != null && (
                      <MetricPill tone="gold">{`${Math.round(detail.pct_ab * 100)}% A/B share`}</MetricPill>
                    )}
                  </div>
                </DetailSection>

                <section className="grid gap-4">
                  <StatCard
                    label="Avg GPA"
                    value={formatGpa(detail.avg_gpa)}
                    hint="Across available grade records"
                  />
                  <StatCard
                    label="Ease"
                    value={formatEase(detail.ease_score)}
                    hint="Normalized ease score out of 100"
                  />
                  <StatCard
                    label="Popularity"
                    value={formatCount(detail.popularity)}
                    hint="Graded records in the local cache"
                  />
                </section>
              </div>

              <GradeDistributionCard detail={detail} />

              {detail.professors?.length > 0 && (
                <DetailSection title="Professors mentioned in reviews">
                  <div className="grid gap-3 sm:grid-cols-2">
                    {detail.professors.map((professor) => (
                      <div
                        key={professor.id}
                        className="rounded-xl border border-slate-200 bg-stone-50 px-4 py-4"
                      >
                        <div className="text-base font-bold text-slate-900">
                          {professor.name}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          <MetricPill>{`${professor.review_count} reviews`}</MetricPill>
                          {professor.avg_rating != null && (
                            <MetricPill tone="gold">
                              {`${Number(professor.avg_rating).toFixed(2)} rating`}
                            </MetricPill>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </DetailSection>
              )}

              <DetailSection title="Recent review excerpts">
                {detail.reviews?.length > 0 ? (
                  <div className="space-y-3">
                    {detail.reviews.map((review) => (
                      <div
                        key={review.id}
                        className="rounded-xl border border-slate-200 bg-stone-50 px-4 py-4"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          {review.professor_name && (
                            <MetricPill>{review.professor_name}</MetricPill>
                          )}
                          {review.rating != null && (
                            <MetricPill tone="gold">
                              {`${Number(review.rating).toFixed(1)} / 5`}
                            </MetricPill>
                          )}
                          {review.term && <MetricPill>{review.term}</MetricPill>}
                        </div>
                        <p className="mt-3 text-sm leading-6 text-slate-600">
                          {review.review_text || "No review text provided."}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-xl border border-dashed border-slate-200 bg-stone-50 px-5 py-10 text-center text-sm text-slate-500">
                    No review excerpts are available for this course.
                  </div>
                )}
              </DetailSection>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function PaginationControls({
  currentPage,
  pageSize,
  totalItems,
  totalPages,
  onPageChange,
  onPageSizeChange,
  showPageSize = true,
  showNavigation = true,
}) {
  if (!totalItems) return null;

  const start = (currentPage - 1) * pageSize + 1;
  const end = Math.min(currentPage * pageSize, totalItems);
  const pageWindow = buildPageWindow(currentPage, totalPages);

  return (
    <div className={`${SURFACE} flex flex-col gap-4 px-4 py-3 sm:flex-row sm:items-center sm:justify-between`}>
      <div>
        <div className="text-sm font-semibold text-slate-900">
          Showing {start}-{end} of {totalItems} courses
        </div>
        <div className="mt-1 text-sm text-slate-500">
          Use smaller pages for easier scanning or larger pages for faster browsing.
        </div>
      </div>

      <div className="flex flex-col gap-3 sm:items-end">
        {showPageSize && (
          <div className="flex items-center gap-3">
            <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Page size
            </label>
            <select
              value={pageSize}
              onChange={(event) => onPageSizeChange(Number(event.target.value))}
              className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none transition focus:border-rose-500 focus:ring-2 focus:ring-rose-100"
            >
              {PAGE_SIZE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        )}

        {showNavigation && totalPages > 1 && (
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => onPageChange(currentPage - 1)}
              disabled={currentPage === 1}
              className="inline-flex h-10 items-center justify-center rounded-md border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-stone-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Previous
            </button>

            {pageWindow.map((item) =>
              typeof item === "string" ? (
                <span key={item} className="px-1 text-sm text-slate-400">
                  ...
                </span>
              ) : (
                <button
                  key={item}
                  type="button"
                  onClick={() => onPageChange(item)}
                  className={`inline-flex h-10 min-w-10 items-center justify-center rounded-md border px-3 text-sm font-semibold transition ${
                    item === currentPage
                      ? "border-rose-700 bg-rose-700 text-white"
                      : "border-slate-300 bg-white text-slate-700 hover:bg-stone-50 hover:text-slate-950"
                  }`}
                >
                  {item}
                </button>
              ),
            )}

            <button
              type="button"
              onClick={() => onPageChange(currentPage + 1)}
              disabled={currentPage === totalPages}
              className="inline-flex h-10 items-center justify-center rounded-md border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-stone-50 hover:text-slate-950 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [query, setQuery] = useState("");
  const [searchData, setSearchData] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [hasSearched, setHasSearched] = useState(false);

  const [gened, setGened] = useState("");
  const [minGpa, setMinGpa] = useState("");
  const [minEase, setMinEase] = useState("");
  const [sortBy, setSortBy] = useState("relevance");
  const [pageSize, setPageSize] = useState(12);
  const [currentPage, setCurrentPage] = useState(1);

  const [selectedCourseId, setSelectedCourseId] = useState("");
  const [selectedCourse, setSelectedCourse] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [logoVisible, setLogoVisible] = useState(true);
  const [showSplash, setShowSplash] = useState(true);
  const [reducedMotion, setReducedMotion] = useState(false);

  const courseResults = useMemo(
    () => (searchData?.results || []).filter((result) => result.kind === "course"),
    [searchData],
  );

  const nonCourseCount = (searchData?.results || []).length - courseResults.length;
  const filterActive = Boolean(gened || minGpa || minEase);
  const totalPages = Math.max(1, Math.ceil(courseResults.length / pageSize));
  const paginatedCourseResults = useMemo(() => {
    const startIndex = (currentPage - 1) * pageSize;
    return courseResults.slice(startIndex, startIndex + pageSize);
  }, [courseResults, currentPage, pageSize]);

  const summary = useMemo(() => {
    const avg = (items) =>
      items.length ? items.reduce((total, value) => total + value, 0) / items.length : null;

    const gpas = courseResults
      .map((result) => Number(result.meta?.avg_gpa))
      .filter((value) => Number.isFinite(value));

    const easeScores = courseResults
      .map((result) => Number(result.meta?.ease_score))
      .filter((value) => Number.isFinite(value));

    const popularity = courseResults
      .map((result) => Number(result.meta?.popularity))
      .filter((value) => Number.isFinite(value));

    return {
      count: courseResults.length,
      avgGpa: avg(gpas),
      avgEase: avg(easeScores),
      avgPopularity: avg(popularity),
    };
  }, [courseResults]);

  async function runSearch(nextQuery = query, options = {}) {
    const { markSearched = true } = options;
    const trimmedQuery = nextQuery.trim();
    const canSearch = Boolean(trimmedQuery || gened || minGpa || minEase);

    if (markSearched) setHasSearched(true);

    if (!canSearch) {
      setSearchData(null);
      setSearchLoading(false);
      setSearchError(markSearched ? "Enter a search term or apply at least one filter." : "");
      return;
    }

    setSearchLoading(true);
    setSearchError("");

    try {
      const url = new URL(`${API_BASE}/search`);
      url.searchParams.set("q", nextQuery);
      url.searchParams.set("top_k", "50");
      url.searchParams.set("alpha", "0.6");
      url.searchParams.set("sort_by", sortBy);
      if (gened) url.searchParams.set("gened", gened);
      if (minGpa) url.searchParams.set("min_avg_gpa", minGpa);
      if (minEase) url.searchParams.set("min_ease", minEase);

      const response = await fetch(url);
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(payload?.detail || `HTTP ${response.status}`);
      }

      setCurrentPage(1);
      setSearchData(payload);
    } catch (error) {
      setSearchData(null);
      setSearchError(error?.message || String(error));
    } finally {
      setSearchLoading(false);
    }
  }

  useEffect(() => {
    if (!hasSearched && !filterActive) return;
    runSearch(query, { markSearched: hasSearched });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gened, minGpa, minEase, sortBy]);

  useEffect(() => {
    setCurrentPage(1);
  }, [pageSize]);

  useEffect(() => {
    if (currentPage <= totalPages) return;
    setCurrentPage(totalPages);
  }, [currentPage, totalPages]);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) {
      setShowSplash(false);
      return undefined;
    }

    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updatePreference = () => setReducedMotion(mediaQuery.matches);
    updatePreference();

    const splashDuration = mediaQuery.matches ? 120 : 950;
    const timer = window.setTimeout(() => setShowSplash(false), splashDuration);

    mediaQuery.addEventListener?.("change", updatePreference);

    return () => {
      window.clearTimeout(timer);
      mediaQuery.removeEventListener?.("change", updatePreference);
    };
  }, []);

  useEffect(() => {
    if (!selectedCourseId) {
      setSelectedCourse(null);
      setDetailError("");
      setDetailLoading(false);
      return;
    }

    let ignore = false;

    async function fetchDetail() {
      setDetailLoading(true);
      setDetailError("");

      try {
        if (!ignore) setSelectedCourse(null);
        const response = await fetch(`${API_BASE}/courses/${selectedCourseId}`);
        const payload = await response.json().catch(() => null);
        if (!response.ok) {
          throw new Error(payload?.detail || `HTTP ${response.status}`);
        }
        if (!ignore) setSelectedCourse(payload);
      } catch (error) {
        if (!ignore) {
          setSelectedCourse(null);
          setDetailError(error?.message || String(error));
        }
      } finally {
        if (!ignore) setDetailLoading(false);
      }
    }

    fetchDetail();
    return () => {
      ignore = true;
    };
  }, [selectedCourseId]);

  return (
    <div className="relative min-h-screen bg-stone-50 text-slate-900">
      {showSplash ? (
        <LoadingSplash
          logoVisible={logoVisible}
          onLogoError={() => setLogoVisible(false)}
          reducedMotion={reducedMotion}
        />
      ) : null}

      <main className={`app-shell mx-auto flex min-h-screen max-w-7xl flex-col gap-5 px-4 py-4 sm:px-6 lg:px-8 lg:py-5 ${showSplash ? "app-shell-hidden" : "app-shell-visible"}`}>
        <header className={`${SURFACE} p-4 sm:p-4`}>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-slate-200 bg-white">
                {logoVisible ? (
                  <img
                    src={UMD_LOGO_PATH}
                    alt="TerpSearch logo"
                    onError={() => setLogoVisible(false)}
                    className="h-8 w-8 object-contain"
                  />
                ) : (
                  <span className="text-sm font-black tracking-[0.16em] text-slate-900">TS</span>
                )}
              </div>

              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-2xl font-black tracking-tight text-slate-950">
                    TerpSearch
                  </h1>
                </div>
                <p className="mt-1 text-sm text-slate-600">
                  UMD course search by GPA, ease, reviews, and GenEds
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-2 lg:justify-end">
              <span className="inline-flex items-center rounded-md border border-slate-200 bg-stone-50 px-2.5 py-1 text-xs font-semibold text-slate-700">
                Course dashboard
              </span>
            </div>
          </div>
        </header>

        <section className={`${SURFACE} p-4 sm:p-4`}>
          <div className="flex flex-col gap-4">
            <form
              onSubmit={(event) => {
                event.preventDefault();
                runSearch(query, { markSearched: true });
              }}
              className="space-y-4"
            >
              <div className="flex flex-col gap-3 lg:flex-row">
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search courses, GenEds, or topics"
                  className="h-11 flex-1 rounded-md border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-rose-500 focus:ring-2 focus:ring-rose-100"
                />
                <button
                  type="submit"
                  disabled={searchLoading}
                  className="inline-flex h-11 items-center justify-center rounded-md border border-rose-700 bg-rose-700 px-5 text-sm font-semibold text-white transition hover:bg-rose-800 disabled:cursor-not-allowed disabled:border-rose-300 disabled:bg-rose-300"
                >
                  {searchLoading ? "Searching..." : "Search"}
                </button>
              </div>

              <div className="flex flex-wrap gap-2">
                {QUICK_SEARCH_CHIPS.map((chip) => (
                  <button
                    key={chip.label}
                    type="button"
                    onClick={() => {
                      setQuery(chip.query);
                      runSearch(chip.query, { markSearched: true });
                    }}
                    className="inline-flex items-center rounded-md border border-slate-200 bg-stone-50 px-2.5 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-white hover:text-slate-900"
                  >
                    {chip.label}
                  </button>
                ))}
              </div>

              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <FilterField label="Min GPA">
                  <input
                    value={minGpa}
                    onChange={(event) => setMinGpa(event.target.value)}
                    type="number"
                    min="0"
                    max="4"
                    step="0.1"
                    placeholder="3.0"
                    className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-rose-500 focus:ring-2 focus:ring-rose-100"
                  />
                </FilterField>

                <FilterField label="GenEd requirement">
                  <select
                    value={gened}
                    onChange={(event) => setGened(event.target.value)}
                    className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none transition focus:border-rose-500 focus:ring-2 focus:ring-rose-100"
                  >
                    {GENED_OPTIONS.map((option) => (
                      <option key={option.value || "all"} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </FilterField>

                <FilterField
                  label="Min Ease"
                  info="Ease is based on course grades. Higher scores mean students usually earn higher grades in that class."
                >
                  <select
                    value={minEase}
                    onChange={(event) => setMinEase(event.target.value)}
                    className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none transition focus:border-rose-500 focus:ring-2 focus:ring-rose-100"
                  >
                    {EASE_OPTIONS.map((option) => (
                      <option key={option.value || "all"} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </FilterField>

                <FilterField label="Sort by">
                  <select
                    value={sortBy}
                    onChange={(event) => setSortBy(event.target.value)}
                    className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none transition focus:border-rose-500 focus:ring-2 focus:ring-rose-100"
                  >
                    {SORT_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </FilterField>
              </div>
            </form>

            <div className="flex flex-wrap gap-2">
              <StatPill label="Courses" value={summary.count.toString()} accent="red" />
              <StatPill label="Avg GPA" value={formatGpa(summary.avgGpa)} />
              <StatPill label="Avg Ease" value={formatEase(summary.avgEase)} accent="gold" />
              <StatPill
                label="Sort"
                value={SORT_OPTIONS.find((option) => option.value === sortBy)?.label || "Relevance"}
              />
              {filterActive ? <StatPill label="Filters" value="On" /> : null}
            </div>

            {searchError && (
              <div className="rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                {searchError}
              </div>
            )}
          </div>
        </section>

        <section className="flex flex-col gap-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-2xl font-black tracking-tight text-slate-950">
                Course matches
              </h2>
              <p className="text-sm text-slate-500">
                Click any card to open a full course detail view with PlanetTerp context.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <StatPill label="Page" value={`${currentPage}/${totalPages}`} />
              <StatPill label="Avg Popularity" value={formatCount(summary.avgPopularity)} />
              {nonCourseCount > 0 ? (
                <span className="text-sm text-slate-500">
                  {nonCourseCount} professor/review matches hidden from the course dashboard.
                </span>
              ) : null}
            </div>
          </div>

          {searchLoading ? (
            <div className={`${SURFACE} px-6 py-10 text-sm text-slate-500`}>
              Loading course results...
            </div>
          ) : courseResults.length > 0 ? (
            <>
              <PaginationControls
                currentPage={currentPage}
                pageSize={pageSize}
                totalItems={courseResults.length}
                totalPages={totalPages}
                onPageChange={(page) =>
                  setCurrentPage(Math.min(totalPages, Math.max(1, page)))
                }
                onPageSizeChange={setPageSize}
                showNavigation={false}
              />
              <div className="grid gap-4">
                {paginatedCourseResults.map((result) => (
                  <CourseCard
                    key={result.doc_id}
                    result={result}
                    onSelect={(courseId) => setSelectedCourseId(courseId)}
                  />
                ))}
              </div>
              <PaginationControls
                currentPage={currentPage}
                pageSize={pageSize}
                totalItems={courseResults.length}
                totalPages={totalPages}
                onPageChange={(page) =>
                  setCurrentPage(Math.min(totalPages, Math.max(1, page)))
                }
                onPageSizeChange={setPageSize}
                showPageSize={false}
              />
            </>
          ) : hasSearched || filterActive ? (
            <div className={`${SURFACE} px-6 py-12 text-center`}>
              <div className="text-lg font-bold text-slate-900">No course matches found</div>
              <p className="mt-2 text-sm text-slate-500">
                Try broadening your query, lowering a filter threshold, or switching the GenEd
                requirement.
              </p>
            </div>
          ) : (
            <div className={`${SURFACE} px-6 py-12 text-center`}>
              <div className="text-lg font-bold text-slate-900">
                Start with a search or filter
              </div>
              <p className="mt-2 text-sm text-slate-500">
                Results will appear here once you search for a topic or apply a filter like GPA,
                GenEd, or ease.
              </p>
            </div>
          )}
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <DashboardChart results={courseResults} />

          <section className={`${SURFACE} p-6`}>
            <div className="flex flex-col gap-2">
              <h2 className="text-lg font-bold text-slate-950">Search snapshot</h2>
              <p className="text-sm text-slate-500">
                A quick read on the current course list after your filters and sort order.
              </p>
            </div>

            <div className="mt-5 flex flex-wrap gap-2">
              <StatPill label="Page results" value={paginatedCourseResults.length.toString()} />
              <StatPill label="Avg popularity" value={formatCount(summary.avgPopularity)} />
              <StatPill label="Filter state" value={filterActive ? "On" : "Off"} />
              <StatPill
                label="Sort mode"
                value={SORT_OPTIONS.find((option) => option.value === sortBy)?.label || "Relevance"}
              />
            </div>
          </section>
        </section>
      </main>

      <CourseDetailModal
        courseId={selectedCourseId}
        detail={selectedCourse}
        loading={detailLoading}
        error={detailError}
        onClose={() => setSelectedCourseId("")}
      />
    </div>
  );
}
