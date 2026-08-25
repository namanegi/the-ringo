# M5 clean-room acceptance

Date: 2026-08-25

Result: **PASS**

Release candidate: `0.1.0`

## Scope and isolation

A Luna tutor Agent followed the root `SKILL.md` against a complete isolated
project root containing a copy of the learner database and the starter pack.
Every state-changing command used an explicit `--root <isolated-root>`.

- native/target languages: `zh-CN` to `ja`;
- initial isolated event count: 4;
- final isolated event count: 24;
- original learner database after the run: 4 events, no session, no course
  plan, and the same SHA-256 hash as before the run;
- tracked worktree after the run: clean.

The copied state already contained the durable goal `准备商务日语面试` and the
saved default of six daily items. Startup calls to `doctor`, `status`, `goal`,
`course`, `session`, and `configure` succeeded. With no active plan, the first
status correctly returned `next_action=expand`.

## Goal-shaped plan

The Agent authored and applied this plan only inside the isolated root:

```toml
[pack]
id = "ja-business-interview-m5"
title = "Japanese business interview preparation"
language = "ja"

[[concepts]]
identifier = "ja.interview-opening"
title = "Interview opening and polite greetings"

[[concepts]]
identifier = "ja.interview-self-introduction"
title = "Professional self-introduction"
prerequisites = ["ja.interview-opening"]

[[concepts]]
identifier = "ja.interview-experience"
title = "Explaining experience and strengths"
prerequisites = ["ja.interview-self-introduction"]
```

## Six-question role play

Before every question, the Agent called `next --json`, presented exactly the
returned target, transparently graded one plausible learner answer, and
recorded it once with a new activity key.

| # | CLI target | Exercise | Simulated learner answer | Activity key | Grade |
| ---: | --- | --- | --- | --- | --- |
| 1 | opening (`new`) | Give a polite interview-room greeting. | `失礼いたします。本日はよろしくお願いいたします。` | `interview-opening-greeting` | good |
| 2 | self-introduction (`new`) | Give a 30-second professional introduction. | `田中と申します。営業を三年間経験し、顧客との信頼関係を大切にしてきました。` | `interview-self-intro-elevator` | good |
| 3 | experience (`new`) | Explain a strength with a STAR-style example. | `前職で納期遅延がありましたが、チームで計画を見直し、予定どおり納品しました。` | `interview-experience-star` | good |
| 4 | opening (`practice`) | Give a different formal arrival response. | `本日はお時間をいただき、ありがとうございます。どうぞよろしくお願いいたします。` | `interview-opening-arrival` | good |
| 5 | self-introduction (`practice`) | Add experience and motivation. | `これまで法人営業を担当してきました。この経験を御社で生かしたいと考えています。` | `interview-self-intro-career` | good |
| 6 | experience (`practice`) | Explain a difficulty and its resolution. | `顧客の要望が変わった際、優先順位を整理して提案し、無事に合意を得ました。` | `interview-experience-challenge` | good |

The target sequence was opening, self-introduction, experience, then one
different practice activity for each. No competency repeated immediately and
all activity keys were distinct.

## Agent-task restart

After question three, a fresh CLI invocation reread all authoritative state:

- the same active goal and course plan;
- the same session identifier;
- `agreed_items=6`, `completed_items=3`, `remaining_items=3`, `status=active`;
- one successful activity for each competency;
- `ja.interview-opening` as the next `practice` target, including its already
  used activity key.

The second half therefore resumed without relying on chat history or a
separate question counter.

## Final state

After the sixth record, `next --json` and `status --json` reported:

```json
{
  "next_action": "complete",
  "target": null,
  "goal_progress": {
    "complete": true,
    "required_coverage": 2,
    "gaps": []
  },
  "session": {
    "agreed_items": 6,
    "completed_items": 6,
    "remaining_items": 0,
    "status": "completed"
  }
}
```

Every competency had two distinct `good` activity keys. The Agent stopped
without a seventh exercise and proposed, without automatically applying, three
follow-up directions: deeper interview follow-ups, business meeting language,
and workplace email/scheduling.

## Acceptance matrix

| Scenario | Result | Evidence |
| --- | --- | --- |
| A. Goal and restart | PASS | A fresh invocation recovered the goal, plan, session, evidence gaps, and next target. |
| B. Bounded lesson | PASS | The saved default was six; the session stopped authoritatively at 6/6. |
| C. Progressive content | PASS | Three relevant, prerequisite-ordered competencies appeared once before varied practice. |
| D. Goal evidence and closure | PASS | Each competency reached two distinct successful activities; `gaps=[]` and `next_action=complete`. |
| E. Continuous supply | PASS | Focused tests verified `expand` without a plan, compatible-only extensions, mastery thresholds, and target exhaustion behavior. |

## Release gate

| Gate | Result | Evidence |
| --- | --- | --- |
| focused state and selection tests | PASS | Learning, state, and CLI focused suites passed 44/44. |
| complete automated suite | PASS | `python -m unittest discover -s tests -v` passed 55/55. |
| clean-room CLI flow | PASS | Startup, plan application, bounded session, restart, and closure all completed in the isolated root. |
| isolated Luna role play | PASS | Six coherent tutor turns used CLI-selected targets, transparent grades, and distinct activity evidence. |
| original learner-state isolation | PASS | Original event count, session/course status, and database hash were unchanged. |

No product or Skill defect was found during the final run. The MVP is ready to
be released as `0.1.0` after the closeout change is merged.
