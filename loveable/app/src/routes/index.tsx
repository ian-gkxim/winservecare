import { createFileRoute } from "@tanstack/react-router";
import faviconMark from "../../brand/svg/favicon.svg?url";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "WinServeCare — The operating system for care" },
      {
        name: "description",
        content:
          "WinServeCare is the UK's first AI-native home care platform — matching families with trusted carers, fast.",
      },
      { property: "og:title", content: "WinServeCare — The operating system for care" },
      {
        property: "og:description",
        content:
          "WinServeCare is the UK's first AI-native home care platform — matching families with trusted carers, fast.",
      },
    ],
  }),
  component: Splash,
});

function Splash() {
  return (
    <div className="min-h-screen bg-[color:var(--brand-surface)] text-[color:var(--brand-ink)] font-sans">
      {/* Top bar */}
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-3">
          <img src={faviconMark} alt="WinServeCare" width={40} height={40} className="rounded-xl" />
          <div className="leading-tight">
            <div className="font-serif text-lg font-semibold tracking-wide">WINSERVECARE</div>
            <div className="text-[10px] uppercase tracking-[0.25em] text-[color:var(--brand-primary)]">
              Management Console
            </div>
          </div>
        </div>
        <div className="hidden items-center gap-3 text-sm md:flex">
          <span className="inline-flex items-center gap-2 rounded-full border border-[color:var(--brand-mist)] bg-white/60 px-3 py-1">
            <span className="h-2 w-2 rounded-full bg-[color:var(--brand-sage)]" />
            All systems operational
          </span>
          <span className="text-[color:var(--brand-ink)]/60">
            {new Date().toLocaleDateString("en-GB", {
              weekday: "long",
              day: "numeric",
              month: "long",
              year: "numeric",
            })}
          </span>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.06]"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 20%, var(--brand-primary) 0, transparent 45%), radial-gradient(circle at 80% 60%, var(--brand-accent) 0, transparent 40%)",
          }}
        />
        <div className="relative mx-auto grid max-w-6xl gap-12 px-6 pb-20 pt-10 md:grid-cols-[1.2fr_1fr] md:pt-16">
          <div>
            <h1 className="font-serif text-5xl leading-[1.05] tracking-tight md:text-6xl lg:text-7xl">
              The future of home care{" "}
              <span className="text-[color:var(--brand-primary)]">starts here.</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-[color:var(--brand-ink)]/75 md:text-xl">
              WinServeCare is the UK's first AI-native home care platform — matching families with
              trusted carers, fast. This is day one of something bigger.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <a
                href="https://wsc.gkim.digital/ainative"
                className="inline-flex items-center justify-center rounded-xl bg-[color:var(--brand-primary)] px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:brightness-110"
              >
                Enter
              </a>
            </div>
          </div>

          {/* Logo card */}
          <div className="relative flex items-center justify-center">
            <div className="relative rounded-3xl border border-[color:var(--brand-mist)] bg-white p-10 shadow-[0_20px_60px_-30px_rgba(15,35,64,0.35)]">
              <img src={faviconMark} alt="" width={220} height={220} className="rounded-3xl" />
              <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-[color:var(--brand-ink)] px-4 py-1.5 text-center text-[10px] font-semibold uppercase tracking-[0.25em] text-white">
                Care at the heart
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* What we do */}
      <section className="mx-auto max-w-6xl px-6 py-16">
        <div className="mb-10 max-w-2xl">
          <h2 className="font-serif text-4xl tracking-tight md:text-5xl">
            One place. Every answer, instantly.
          </h2>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {[
            {
              title: "Matched with intelligence",
              body: "AI matches your family with carers suited to your needs, budget, and preferences — ranked and explained in plain English.",
            },
            {
              title: "Real-time availability",
              body: "Live carer availability, so families find and book help today — not next week.",
            },
            {
              title: "Guided care journeys",
              body: "We stay with families from first search through ongoing care, handling the coordination.",
            },
          ].map((f) => (
            <article
              key={f.title}
              className="group rounded-2xl border border-[color:var(--brand-mist)] bg-white p-6 transition hover:-translate-y-0.5 hover:border-[color:var(--brand-primary)]/40 hover:shadow-md"
            >
              <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-[color:var(--brand-primary)]/10 text-[color:var(--brand-primary)]">
                <img src={faviconMark} alt="" width={22} height={22} className="rounded-md" />
              </div>
              <h3 className="font-serif text-xl font-semibold">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-[color:var(--brand-ink)]/70">
                {f.body}
              </p>
            </article>
          ))}
        </div>
      </section>

      {/* Bigger picture */}
      <section className="mx-auto max-w-6xl px-6 py-16">
        <div className="overflow-hidden rounded-3xl bg-[color:var(--brand-ink)] p-10 text-white md:p-16">
          <div className="grid gap-10 md:grid-cols-[1.3fr_1fr] md:items-end">
            <div>
              <div className="mb-4 text-xs font-semibold uppercase tracking-[0.25em] text-[color:var(--brand-accent)]">
                The bigger picture
              </div>
              <h2 className="font-serif text-4xl leading-tight tracking-tight md:text-5xl">
                This is the front door.{" "}
                <span className="text-[color:var(--brand-accent)]">
                  The whole house is coming.
                </span>
              </h2>
              <p className="mt-6 max-w-xl text-white/75">
                WinServeCare is the foundation of a full AI-native operating system for care in the
                UK. Home care matching is module one. We're building toward a platform that runs the
                entire care journey — carer operations, family communication, compliance, funding,
                ongoing management — all connected, all intelligent.
              </p>
              <p className="mt-4 font-serif text-lg italic text-white/90">
                We're building the operating system the UK's care sector runs on.
              </p>
            </div>
            <ul className="space-y-3 text-sm">
              {[
                "Module 1 · Home care matching",
                "Module 2 · Carer operations",
                "Module 3 · Family communication",
                "Module 4 · Compliance & funding",
                "Module 5 · Ongoing care management",
              ].map((m, i) => (
                <li
                  key={m}
                  className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 px-4 py-3"
                >
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[color:var(--brand-accent)] text-[11px] font-bold text-white">
                    {i + 1}
                  </span>
                  <span className={i === 0 ? "font-semibold" : "text-white/70"}>{m}</span>
                  {i === 0 && (
                    <span className="ml-auto rounded-full bg-[color:var(--brand-sage)]/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-[color:var(--brand-sage)]">
                      Live
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* Why */}
      <section className="mx-auto max-w-6xl px-6 py-16">
        <h2 className="font-serif text-4xl tracking-tight md:text-5xl">Why WinServeCare</h2>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {[
            "Built for the UK care system — CQC-aware, funding-aware, home-grown.",
            "We explain every match.",
            "Free for families, always.",
          ].map((w) => (
            <div
              key={w}
              className="rounded-2xl border-l-4 border-[color:var(--brand-accent)] bg-white p-6 shadow-sm"
            >
              <p className="font-serif text-lg leading-snug">{w}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Closing CTA */}
      <section className="mx-auto max-w-6xl px-6 pb-24 pt-8">
        <div className="rounded-3xl border border-[color:var(--brand-mist)] bg-white p-10 text-center md:p-16">
          <h2 className="mx-auto max-w-3xl font-serif text-4xl leading-tight tracking-tight md:text-5xl">
            The care your family deserves,{" "}
            <span className="text-[color:var(--brand-primary)]">matched in minutes.</span>
          </h2>
          <div className="mt-8">
            <a
              href="https://wsc.gkim.digital/ainative"
              className="inline-flex items-center justify-center rounded-xl bg-[color:var(--brand-primary)] px-8 py-4 text-base font-semibold text-white shadow-sm transition hover:brightness-110"
            >
              Enter
            </a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[color:var(--brand-mist)]">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 py-8 text-xs text-[color:var(--brand-ink)]/60 md:flex-row">
          <div className="font-serif italic">
            WinServeCare — AI-native home care, built for Britain.
          </div>
          <div>© {new Date().getFullYear()} WinServeCare Ltd.</div>
        </div>
      </footer>
    </div>
  );
}
