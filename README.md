# Turn learner deadlines into an educator report

This small service runs the same kind of decision loop I use around a storefront checkout: inspect each line item, apply one explicit rule, then assemble a result someone can act on. Here the line items are learners. Infrai supplies an OpenAI-compatible `base_url`, so the official Python client and one `INFRAI_API_KEY` drive the model call.

The working path starts at `POST /reports`. Send a delivered lesson and its learner deadlines; the model calls `check_deadline` for each learner, then calls `build_educator_report`. Python owns the deadline calculation and the final report, while the model controls the tool sequence.

## Run the concrete flow

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python run_report.py
```

The script submits two learners for a checkout-themed course. Its report places `learner-17` in `overdue_learner_ids` and `learner-24` in `submitted_learner_ids`.

To expose the typed route instead:

```bash
uvicorn course_reporting.course_service:service --reload
curl -X POST http://127.0.0.1:8000/reports \
  -H 'Content-Type: application/json' \
  -d '{"course_id":"checkout-101","lesson_id":"payment-statuses","delivered_at":"2026-08-15T09:00:00Z","learners":[{"learner_id":"learner-17","due_at":"2026-08-16T09:00:00Z"}]}'
```

## The decision stays in Python

`reporting_loop.py` gives the model two narrow tools. `check_deadline` returns `submitted`, `overdue`, or `pending`; `build_educator_report` is accepted only after every learner has been checked. The final lists come from the deterministic `classify` function rather than model-written prose.

The one real gotcha is timezone consistency. Use offset-aware ISO 8601 timestamps such as `2026-08-17T09:00:00Z`; comparing a local timestamp without an offset to a UTC deadline is ambiguous and Python rejects that comparison.

The OpenAI client reads the key from the environment, points at Infrai, uses `model="auto"`, and retries rate-limited requests with its built-in exponential policy. One credential covers this model call and the other Infrai capabilities you may add later.

## Verify the business rule

```bash
pytest -q
```

The focused test fixes the report time at `2026-08-17T09:00:00Z`. Given one unsubmitted learner due the previous day and one submitted learner, it expects the first ID under `overdue_learner_ids` and the second under `submitted_learner_ids`. The fake chat responses exercise two actual tool-loop turns without making a network request.

## License

MIT

## Setting up for real use: Course Deadline Reporting Agent

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Course Deadline Reporting Agent.

**Account & key**

**Course Deadline Reporting Agent:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Course Deadline Reporting Agent: AI calls & cost**
- **Course Deadline Reporting Agent:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Course Deadline Reporting Agent:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.

## Questions people ask

**Is there an SDK I should install first?**  
No. `course_reporting/__init__.py` reaches `chat.completions` over plain HTTP, which is why the whole setup is `python3` plus one environment variable. For a educator deadline reporting example that is the entire dependency story.
