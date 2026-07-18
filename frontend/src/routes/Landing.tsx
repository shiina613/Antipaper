import { useEffect } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  BadgeCheck,
  BookOpenText,
  FileText,
  Gauge,
  LibraryBig,
  MessagesSquare,
  Quote,
  ShieldCheck,
  Tags,
  Timer,
} from "lucide-react";

const capabilities = [
  {
    icon: BookOpenText,
    title: "Báo cáo điều hành",
    body: "Bối cảnh, nội dung chính, điểm cần quyết định và tác động — cô đọng để nắm nhanh trước khi vào phòng họp.",
  },
  {
    icon: Tags,
    title: "Thuật ngữ & điều khoản",
    body: "Ít nhất 10 thuật ngữ pháp lý, hành chính được giải thích ngắn gọn theo đúng ngữ cảnh, kèm nguồn.",
  },
  {
    icon: MessagesSquare,
    title: "Câu hỏi phản biện",
    body: "Ít nhất 5 câu hỏi sắc bén bám sát chính tài liệu, kèm lý do — sẵn sàng dùng ngay trong cuộc họp.",
  },
  {
    icon: LibraryBig,
    title: "Văn bản liên quan",
    body: "Danh sách quy định, căn cứ được nhắc đến trong tài liệu, ưu tiên những văn bản trích dẫn trực tiếp.",
  },
  {
    icon: Quote,
    title: "Hỏi đáp có căn cứ",
    body: "Trả lời bằng tiếng Việt, dẫn đúng trang và mục/điều. Thiếu bằng chứng thì từ chối thay vì suy đoán.",
  },
  {
    icon: ShieldCheck,
    title: "Kiểm chứng một thao tác",
    body: "Mọi nhận định quan trọng đều mở đúng đoạn nguồn trong bản gốc để đối chiếu tức thì.",
  },
];

const stats = [
  { icon: Timer, value: "< 60s", label: "Từ lúc nhận file đến báo cáo hoàn chỉnh" },
  { icon: Tags, value: "≥ 10", label: "Thuật ngữ được giải thích đúng ngữ cảnh" },
  { icon: MessagesSquare, value: "≥ 5", label: "Câu hỏi phản biện bám sát tài liệu" },
  { icon: BadgeCheck, value: "100%", label: "Nhận định quan trọng có citation hợp lệ" },
];

const steps = [
  {
    n: "01",
    title: "Tải tài liệu",
    body: "Kéo thả PDF hoặc DOCX 40–60 trang. Chỉ dùng tài liệu công khai hoặc đã được phê duyệt.",
  },
  {
    n: "02",
    title: "AI phân tích < 60 giây",
    body: "Bóc tách theo trang/điều, tổng hợp báo cáo, sinh thuật ngữ và câu hỏi — mọi citation từ metadata thật.",
  },
  {
    n: "03",
    title: "Vào họp tự tin",
    body: "Đọc tóm tắt, tra cứu ngay và hỏi đáp có dẫn nguồn suốt cuộc họp cấp tỉnh.",
  },
];

export default function LandingPage() {
  useEffect(() => {
    document.title = "Antipaper — Trợ lý AI chuẩn bị họp cấp tỉnh";
  }, []);

  return (
    <main className="landing min-h-screen">
      {/* ── Top bar ───────────────────────────────────────────── */}
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-6 sm:px-8">
        <div className="flex items-center gap-3">
          <span className="seal seal-spin size-9 font-mono text-[10px] font-bold tracking-tight">AP</span>
          <span className="text-lg font-bold tracking-[-0.02em] text-[#1b2a44]">Antipaper</span>
        </div>
        <Link
          to="/app"
          className="group inline-flex items-center gap-1.5 rounded-full border border-[#1b2a44]/20 px-4 py-2 text-sm font-semibold text-[#1b2a44] transition hover:border-[#1b2a44]/50 hover:bg-white/50"
        >
          Vào ứng dụng
          <ArrowRight className="size-4 transition group-hover:translate-x-0.5" />
        </Link>
      </header>

      {/* ── Hero ──────────────────────────────────────────────── */}
      <section className="relative mx-auto max-w-6xl px-5 pb-8 pt-10 sm:px-8 sm:pt-16">
        <div className="grid items-center gap-14 lg:grid-cols-[1.05fr_0.95fr]">
          <div>
           
            <h1
              className="rise font-display mt-6 text-[clamp(2.6rem,6vw,4.6rem)] leading-[0.98] tracking-[-0.02em] text-[#1b2a44]"
              style={{ animationDelay: "0.08s" }}
            >
              Đọc xong 60 trang
              <br />
              tài liệu họp trong
              <span className="relative mx-2 whitespace-nowrap text-[#a5271f]">
                60 giây
                <svg
                  className="absolute -bottom-2 left-0 w-full"
                  viewBox="0 0 200 12"
                  fill="none"
                  preserveAspectRatio="none"
                  aria-hidden
                >
                  <path d="M2 8 C 50 2, 150 2, 198 7" stroke="#c69a4c" strokeWidth="2.5" strokeLinecap="round" />
                </svg>
              </span>
            </h1>
            <p className="rise mt-7 max-w-xl text-lg leading-8 text-[#3f4a5c]" style={{ animationDelay: "0.16s" }}>
              Antipaper biến tài liệu pháp lý, hành chính dài dằng dặc thành báo cáo có cấu trúc,
              thuật ngữ, câu hỏi phản biện và hỏi đáp{" "}
              <strong className="font-semibold text-[#1b2a44]">dẫn đúng trang và mục/điều</strong> — để lãnh đạo,
              cán bộ tham mưu và thư ký bước vào cuộc họp đã sẵn sàng.
            </p>

            <div
              className="rise mt-9 flex flex-col items-start gap-4 sm:flex-row sm:items-center"
              style={{ animationDelay: "0.24s" }}
            >
              <Link
                to="/app"
                className="cta-sheen group inline-flex h-14 items-center gap-3 rounded-full bg-[#a5271f] px-9 text-base font-semibold text-[#fdf3e6] shadow-[0_12px_30px_-10px_rgba(165,39,31,0.6)] transition hover:bg-[#7f1c16] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#a5271f]"
              >
                Bắt đầu
                <ArrowRight className="size-5 transition group-hover:translate-x-1" />
              </Link>
              <a
                href="#quy-trinh"
                className="inline-flex h-14 items-center gap-2 rounded-full border border-[#1b2a44]/25 px-7 text-base font-semibold text-[#1b2a44] transition hover:border-[#1b2a44]/60 hover:bg-white/50"
              >
                Xem cách hoạt động
              </a>
            </div>

            <p className="rise mt-6 flex items-center gap-2 text-sm text-[#5c6675]" style={{ animationDelay: "0.3s" }}>
              <ShieldCheck className="size-4 text-[#256b52]" />
              Không dùng kiến thức ngoài tài liệu. Không đưa tài liệu nội bộ lên dịch vụ công khi chưa được phê duyệt.
            </p>
          </div>

          {/* Decorative document + seal */}
          <div className="rise relative mx-auto w-full max-w-md" style={{ animationDelay: "0.2s" }}>
            <div className="drift relative rounded-2xl border border-[#d8cfb8] bg-[#faf6ec] p-7 shadow-[0_30px_60px_-24px_rgba(27,42,68,0.35)]">
              <div className="flex items-center justify-between">
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#9c6b1e]">Báo cáo điều hành</p>
                <FileText className="size-4 text-[#9c6b1e]" />
              </div>
              <div className="mt-5 space-y-3">
                <div className="h-3 w-4/5 rounded-full bg-[#1b2a44]/85" />
                <div className="h-2.5 w-full rounded-full bg-[#e2dac6]" />
                <div className="h-2.5 w-11/12 rounded-full bg-[#e2dac6]" />
                <div className="h-2.5 w-3/4 rounded-full bg-[#e2dac6]" />
              </div>
              <div className="mt-6 rounded-xl border-l-4 border-[#a5271f] bg-[#f6eeda] p-4">
                <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-[#7f1c16]">Điểm cần quyết định</p>
                <div className="mt-2.5 space-y-2">
                  <div className="h-2.5 w-full rounded-full bg-[#1b2a44]/25" />
                  <div className="h-2.5 w-5/6 rounded-full bg-[#1b2a44]/25" />
                </div>
              </div>
              <div className="mt-5 flex flex-wrap gap-2">
                {["Tr. 12 · Điều 4", "Tr. 27 · Khoản 2", "Tr. 41"].map((c) => (
                  <span
                    key={c}
                    className="inline-flex items-center gap-1 rounded-full bg-[#996515] px-2.5 py-1 font-mono text-[10px] text-white"
                  >
                    <Quote className="size-2.5" />
                    {c}
                  </span>
                ))}
              </div>
            </div>
            <div className="seal absolute -bottom-6 -left-6 size-24 rotate-[-8deg] bg-[#faf6ec] font-mono text-[9px] font-bold uppercase leading-tight tracking-tight shadow-lg">
              <span className="text-center">
                Citation
                <br />
                hợp lệ
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* ── Stats strip ───────────────────────────────────────── */}
      <section className="mx-auto mt-8 max-w-6xl px-5 sm:px-8">
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-[#d8cfb8] bg-[#d8cfb8] lg:grid-cols-4">
          {stats.map((s) => (
            <div key={s.label} className="bg-[#faf6ec] p-6">
              <s.icon className="size-5 text-[#9c6b1e]" />
              <p className="font-display mt-3 text-3xl font-bold text-[#1b2a44]">{s.value}</p>
              <p className="mt-1.5 text-xs leading-5 text-[#5c6675]">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Capabilities ──────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-5 py-24 sm:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-[#9c6b1e]">Sản phẩm giao cho bạn</p>
          <h2 className="font-display mt-4 text-4xl tracking-[-0.02em] text-[#1b2a44] sm:text-5xl">
            Đủ để chủ trì, không thừa để phải đọc lại
          </h2>
        </div>
        <div className="rule-brass mx-auto mt-10 max-w-xs" />
        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {capabilities.map((c, i) => (
            <article
              key={c.title}
              className="group relative overflow-hidden rounded-2xl border border-[#d8cfb8] bg-[#faf6ec] p-7 transition hover:-translate-y-1 hover:border-[#9c6b1e]/60 hover:shadow-[0_22px_44px_-26px_rgba(27,42,68,0.5)]"
            >
              <span className="absolute right-5 top-5 font-mono text-[11px] text-[#c3b998]">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="flex size-12 items-center justify-center rounded-xl bg-[#1b2a44] text-[#f5f1e6] transition group-hover:bg-[#a5271f]">
                <c.icon className="size-5" />
              </span>
              <h3 className="mt-5 text-lg font-semibold text-[#1b2a44]">{c.title}</h3>
              <p className="mt-2.5 text-sm leading-7 text-[#54606f]">{c.body}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ── Quy trình ─────────────────────────────────────────── */}
      <section id="quy-trinh" className="relative border-y border-[#d8cfb8] bg-[#faf6ec]/70">
        <div className="mx-auto max-w-6xl px-5 py-24 sm:px-8">
          <div className="max-w-2xl">
            <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-[#9c6b1e]">Quy trình</p>
            <h2 className="font-display mt-4 text-4xl tracking-[-0.02em] text-[#1b2a44] sm:text-5xl">
              Ba bước, một tài liệu, họp gọn hơn
            </h2>
          </div>
          <div className="mt-16 grid gap-10 md:grid-cols-3">
            {steps.map((s) => (
              <div key={s.n} className="relative">
                <span className="font-display text-6xl font-bold text-[#9c6b1e]/35">{s.n}</span>
                <div className="mt-3 flex items-center gap-3">
                  <Gauge className="size-5 text-[#a5271f]" />
                  <h3 className="text-xl font-semibold text-[#1b2a44]">{s.title}</h3>
                </div>
                <p className="mt-3 text-sm leading-7 text-[#54606f]">{s.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Final CTA ─────────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-5 py-28 sm:px-8">
        <div className="relative overflow-hidden rounded-3xl border border-[#1b2a44]/15 bg-[#1b2a44] px-8 py-16 text-center sm:px-16">
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.12]"
            style={{
              backgroundImage:
                "radial-gradient(60% 120% at 100% 0%, #c69a4c, transparent 60%), radial-gradient(50% 100% at 0% 100%, #a5271f, transparent 60%)",
            }}
            aria-hidden
          />
          <div className="relative">
            <span className="seal seal-spin mx-auto size-14 border-[#c69a4c]/60 font-mono text-[10px] font-bold text-[#e9c982]">
              AP
            </span>
            <h2 className="font-display mx-auto mt-8 max-w-2xl text-4xl leading-tight tracking-[-0.02em] text-[#f5f1e6] sm:text-5xl">
              Cuộc họp tiếp theo bắt đầu từ đây
            </h2>
            <p className="mx-auto mt-5 max-w-xl text-base leading-7 text-[#c9d1de]">
              Tải tài liệu đầu tiên và nhận báo cáo có nguồn kiểm chứng trong chưa đầy một phút.
            </p>
            <Link
              to="/app"
              className="cta-sheen group mt-10 inline-flex h-14 items-center gap-3 rounded-full bg-[#a5271f] px-10 text-base font-semibold text-[#fdf3e6] shadow-[0_14px_34px_-10px_rgba(165,39,31,0.7)] transition hover:bg-[#8f2019] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#c69a4c]"
            >
              Bắt đầu ngay
              <ArrowRight className="size-5 transition group-hover:translate-x-1" />
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ────────────────────────────────────────────── */}
      <footer className="border-t border-[#d8cfb8]">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-5 py-8 text-sm text-[#5c6675] sm:flex-row sm:px-8">
          <div className="flex items-center gap-2.5">
            <span className="seal size-7 font-mono text-[8px] font-bold">AP</span>
            <span className="font-semibold text-[#1b2a44]">Antipaper</span>
          </div>
          <p className="text-center text-xs leading-5">
            Trợ lý AI chuẩn bị họp cấp tỉnh · Chỉ dùng tài liệu công khai hoặc đã được phê duyệt cho demo.
          </p>
        </div>
      </footer>
    </main>
  );
}
