<div class="fp-hero" markdown>

<span class="fp-eyebrow">Free · 13 modules · FR / EN</span>

# Mastering FastAPI

<p class="fp-tagline">A complete, hands-on curriculum to design, build, test and operate
production-grade FastAPI APIs — one running project that grows with every module.</p>

<div class="fp-cta">
<a class="fp-primary" href="https://github.com/patrick26-Developer/Backend-Python">View the repository on GitHub</a>
<a class="fp-ghost" href="../">Site en français</a>
</div>

</div>

<div class="fp-quickstart" markdown>
```bash
git clone https://github.com/patrick26-Developer/Backend-Python.git
cd Backend-Python && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" && fastapi dev taskman/main.py
```
</div>

## A note on the language

This course is written **in French** — theory, explanations, exercise statements. Technical
vocabulary (the words that matter for your career: *middleware*, *dependency injection*,
*rate limiting*...) is kept in **English** throughout, on purpose: that's the real
vocabulary of the job.

The **code itself** — `taskman`, the reference solutions, the tests, the comments in
source files — reads like any other professional Python codebase and needs no translation
to follow along.

If you're comfortable reading technical French (or happy to use a translator alongside),
the [full site in French](../) covers, module by module:

- HTTP fundamentals & FastAPI basics
- Request/response modelling with Pydantic v2
- Layered architecture & dependency injection
- SQLAlchemy 2.0 async + Alembic migrations
- Structured errors, logging, middleware
- OAuth2 + JWT authentication & RBAC authorization
- The test pyramid, factories, TDD
- Caching, cursor pagination, background workers
- Observability: Prometheus metrics, OpenTelemetry, health/readiness
- OWASP API Security Top 10, rate limiting, hardening
- Docker, CI/CD, production deployment
- Event-driven architecture, idempotency, API versioning

Plus four "checkpoint" mini-projects and a full e-commerce reference project (`shopfast`),
all with complete, tested source code.

## Repository

Everything — theory, exercises, tested reference solutions, line-by-line explanations,
and runnable code — lives in one public repository:

**[github.com/patrick26-Developer/Backend-Python](https://github.com/patrick26-Developer/Backend-Python)**

---

<p style="color:var(--md-default-fg-color--light)">
Course designed and written by <strong>Patrick De Grâce</strong>.
Portfolio: <a href="https://portfolio-personnel-ecru.vercel.app/">portfolio-personnel-ecru.vercel.app</a>
</p>
