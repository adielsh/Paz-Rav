# Paz Rav — תוכנית שדרוג 2026

> גרסה מפורטת (עברית). גרסה קצרה: [`UPGRADE-2026-simple.he.md`](UPGRADE-2026-simple.he.md) ·
> English: [`UPGRADE-2026.en.md`](UPGRADE-2026.en.md)

---

## 1. למה בכלל

Paz Rav היום הוא פרויקט טוב מאוד. הארכיטקטורה נקייה: מונוליט מודולרי, `Protocol` לכל
שכבת אחסון, קו-ברזל דטרמיניסטי (כל מספר מחושב ב-Python, ה-LLM רק שוקל), ו-degradation
ladder בכל שכבה. 106 טסטים עוברים, הכל רץ בפקודה אחת.

אבל שלוש אמיתות מפרידות בינו לבין פרויקט דגל:

1. **שכבת ה-AI נכתבה מול API של 2025**, ואין לה שום מדידה. יש בה גם באג שמשתיק את כל
   הטרייסינג — כלומר אי אפשר להוכיח שום דבר על איכות ההחלטות.
2. **הליבה הכמותית מדויקת אבל רדודה** — sigma שטוח יחיד, בלי חיוך ובלי מבנה עתי.
3. **הבקטסט לא באמת בודק את המערכת** — הוא אגרגטור P&L שלא מריץ את הפייפליין ולא
   מפעיל את כללי היציאה.

**המטרה:** קודם להביא את הפרויקט למקום שמרשים מהנדס בכיר (עומק AI, מדידות,
observability), ובאותה תנועה לבנות בסיס מספיק נכון כדי לסמוך עליו בכסף אמיתי בשלב הבא.

---

## 2. ממצאים מהסקירה

הטבלה הבאה היא מה שנמצא בקוד עצמו — לא הערכות.

| # | ממצא | קובץ | חומרה |
|---|---|---|---|
| 1 | `langfuse>=2.0` מוצהר ב-`pyproject.toml`, אבל הקוד קורא ל-API של **v3** (`create_trace_id`, `create_event(trace_context=)`, `create_score(data_type=)`). הכל עטוף ב-`except Exception: pass` → **הטרייסינג מת בשקט** | `pyproject.toml`, `agents/*.py`, `positions/exit_manager.py:70` | 🔴 |
| 2 | אף `messages.create` לא נרשם כ-generation. אין prompt/completion/tokens/עלות/latency. אין `flush()` — Langfuse מאגד ברקע, ולקוח קצר-חיים מאבד אירועים | כל `agents/` | 🔴 |
| 3 | `anthropic>=0.25` (SDK עתיק); מודל מקודד קשיח `claude-haiku-4-5-20251001` בשתי נקודות; לקוח `AsyncAnthropic` **חדש בכל קריאה**; אין timeout / retry / thinking / effort / prompt caching | `close_advisor.py:210`, `reflection.py:143` | 🔴 |
| 4 | forced tool-use בלי ולידציה — `dict(block.input)` + `.get()` עם ברירות מחדל. `confidence` יכול לחזור 5.0 ואיש לא בודק | `close_advisor._ask` | 🟠 |
| 5 | `open_advisor` ממחזר את ה-enum של הסגירה: `_DECISION_MAP = {"hold":"open","close":"skip","reduce":"wait"}` — המודל פולט אסימוני-סגירה שמשמעותם פתיחה. אין לו טרייסינג בכלל, והקאש שלו לא מתבטל על תנועת שוק | `open_advisor.py` | 🟠 |
| 6 | **אפס טסטים על נתיב ה-LLM. אין CI כלל** (`.github/` לא קיים). `ruff`/`mypy` מוצהרים ולא רצים. יש `eslint-disable` בקוד בלי ש-ESLint מותקן. Postgres/Redis/scheduler — בדיוק הקוד שרץ רק בפרודקשן — לא מכוסים | הריפו כולו | 🔴 |
| 7 | `numpy/scipy/py_vollib/polars/duckdb/pyarrow` מוצהרים ב-extra `quant` — **מיובאים באפס מקומות**. גם "מבחן הפריטי מול py_vollib" שמוזכר בשני docstrings לא קיים | `quant/` | 🟡 |
| 8 | `grid_stats` משתמש ב-sigma שטוח יחיד. אין skew, אין term structure, אין מסלול תנודתיות → כנף ה-put של הקונדור מתומחרת שגוי בשיטתיות | `quant/valuation.py:62` | 🟠 |
| 9 | `backtest/runner.py` הוא **אגרגטור P&L של 54 שורות** — מקבל זוגות `(candidate, terminal_price)` מוכנים. לא מריץ דאטה, לא מיישם כללי יציאה, לא נשמר לשום מקום. `scripts/backtest_demo.py` לא קורא ל-`Pipeline.run_once` → **טענת ה-"backtest=live parity" ב-ROADMAP לא מתקיימת בקוד** | `backtest/`, `scripts/backtest_demo.py` | 🟠 |
| 10 | האנומרציה מייצרת **לכל היותר 4 קונדורים + DACS אחד לנייר** (2 דלתאות × 2 כנפיים; DACS מחזיר 0 או 1). אין סריקת strike / width / DTE. `top_n=10` לעולם לא נכנס לפעולה | `strategies/iron_condor.py:63`, `dacs.py:26` | 🟡 |
| 11 | צמיחה בלתי-חסומה: `candidates` הוא INSERT ללא retention (~65k שורות/יום); ה-zset של IV-history נקרא **כולו** ל-Python בכל סריקה כדי לחשב min/max | `postgres_store.py`, `redis_store.py` | 🟠 |
| 12 | באגי import: יבוא מעגלי `quant/valuation ↔ strategies/base` (עובד רק בזכות סדר היבוא); `quant/__init__.py` דורס את המודול `greeks` בפונקציה `greeks` | `quant/` | 🟡 |
| 13 | ה-frontend מקבל הודעות WebSocket **וזורק את התוכן** — במקום זה מבצע שתי קריאות REST מחדש. אין שכבת דאטה, שגיאות נבלעות ב-`.catch(() => {})` | `web/src/App.tsx:139` | 🟡 |

---

## 3. מה **לא** נכניס, ולמה

הכלל: כלי נכנס רק אם הוא פותר בעיה אמיתית שקיימת כאן.

| כלי | למה לא |
|---|---|
| **DeepAgents** | harness לעבודה פתוחה וארוכת-טווח עם filesystem, planning tool ו-shell. הסוכנים כאן קצרים, חסומים, ומעל מספרים שכבר חושבו. shell לסוכן = הפרה ישירה של חוק הברזל. היכולת היחידה שרצינו ממנו — שהמודל *יחקור* — מושגת ב-Pillar 2 בשבריר משטח-התקיפה |
| **Claude Agent SDK** | אותו נימוק. זה harness לסוכן קידוד/filesystem, לא למנוע החלטות מעל מספרים |
| **Braintrust / LangSmith** | Langfuse כבר מחווט בפרויקט; v3 מביא Datasets + Experiments + Scores — בדיוק פלטפורמת ה-evals המנוהלת. ספק אחד, לא שניים |
| **MCP** | ה-ARCHITECTURE כבר דוחה אותו בצדק ("plain typed functions give the same shared code path with less indirection") |
| **Temporal / Prefect** | scheduler של 60 שניות מעל 9 סימבולים. אורקסטרציה עמידה היא overkill מוחלט |
| **Kafka, K8s, CrewAI, AutoGen, LangChain המלא, vector DB חיצוני** | pgvector נכון; Redis Streams מספיק; ≤3 deployables זה עיקרון מוצהר של הפרויקט |
| **דאטת אופציות בתשלום** | לא נבחרה בתקציב. Pillar 4 עוקף את זה עם בקטסט יום-אחר-יום כן, שמתקן את חוסר-ההוגנות ל-DACS גם בלי דאטה היסטורית קנויה |

**LangGraph נשאר.** הוא באמת מרוויח את מקומו: הוא מנהל צמתי-מודל אמיתיים עם לולאת
רוויזיה מותנית. סוכן יחיד לא היה צריך גרף.

---

## 4. Pillar 1 — שכבת ה-AI ל-2026

**קבצים:** `agents/llm.py` (חדש), `agents/close_advisor.py`, `agents/open_advisor.py`,
`agents/reflection.py`, `config.py`, `pyproject.toml`, `Dockerfile`.

### 4.1 `agents/llm.py` — התפר היחיד מול Anthropic

היום `_ask` יושב פרטי ב-`close_advisor`, ו-`open_advisor` מייבא ממנו `_ask`,
`_STANCE_TOOL`, `_DECIDE_TOOL`, `_memory_note` — צימוד לשמות פרטיים. מוציאים למודול אחד:

- **לקוח יחיד ברמת מודול** (lazy singleton) עם `timeout=60`, `max_retries=3`.
  מחליף את `AsyncAnthropic(...)` שנבנה מחדש בכל אחת מ-3 הקריאות של כל ויכוח.
- **Structured Outputs** (`output_config={"format": {...}}`) עם מודל Pydantic במקום
  forced tool-use, **ועם ולידציה בפועל**. פותר ממצא #4: `confidence` מחוץ ל-[0,1] נכשל
  בקול, לא נבלע בשקט.
- **Adaptive thinking**: `thinking={"type":"adaptive","display":"summarized"}` בשילוב
  `output_config={"effort": ...}`. זו משימת שיפוט — thinking הוא בדיוק המנוף.
- **Prompt caching**: ה-system prompt הקבוע ובלוק ה-SITUATION המשותף מקבלים
  `cache_control`. שלושת התפקידים חולקים prefix, אז קריאות 2 ו-3 הן cache reads —
  מה שמקזז את רוב יוקר המודל החזק.
- **חשבונאות עלות**: קוראים `msg.usage` (כולל `cache_read_input_tokens` /
  `cache_creation_input_tokens`), מצטברים לכל ויכוח →
  `result["cost"] = {tokens, usd, cache_hit_rate}`, ומציגים ב-UI. מערכת מסחר שלא יודעת
  כמה עולה לה החלטה אינה מערכת דגל.
- **שרשרת שגיאות מוטיפסת** — `RateLimitError` → `APIStatusError` → `APIConnectionError`
  במקום `except Exception: pass`. כשל אמיתי נרשם ומוחזר כ-`engine:"degraded"` עם סיבה,
  ולא מתחזה בשקט ל-`deterministic`. **זה הבדל קריטי**: היום כשל SDK נראה בדיוק כמו
  "אין מפתח".

### 4.2 מודלים מדורגים, נשלטים מקונפיג

`PAZ_MODEL_ANALYST` / `_CRITIC` / `_DECIDER` / `_REFLECTION` ב-`config.py`:

| תפקיד | מודל | effort | נימוק |
|---|---|---|---|
| Analyst | `claude-sonnet-5` | medium | טיעון ראשוני מעל מספרים נתונים |
| Critic | `claude-sonnet-5` | high | איפכא-מסתברא; מפעיל כלים (Pillar 2) |
| **Decider** | **`claude-opus-5`** | high + adaptive thinking | ההכרעה היחידה שנוגעת בכסף |
| Reflection | `claude-opus-5` | high | רץ נדיר, מסתכל על כל ההיסטוריה |

מסירים את סיומת התאריך מה-model id. `AGENT_CONCURRENCY` (קיים בקונפיג, לא בשימוש)
הופך ל-`Semaphore` אמיתי סביב הקריאות.

> **הערה על תקציב:** בבחירות שלך לא סומן שדרוג מודלים. המבנה כאן נשלט מקונפיג במלואו,
> כך שאפשר להשאיר את הכל על Haiku/Sonnet ולשדרג רק את ה-Decider — או בכלל לא. עם
> prompt caching פעיל, ההפרש בעלות קטן משמעותית ממה שנראה על הנייר.

### 4.3 תיקונים נקודתיים

- **`open_advisor`** — סכמה משלו (`open | skip | wait`) במקום מיפוי ה-enum של הסגירה;
  חתימת-קאש שמתבטלת על תנועת שוק (כמו `close_advisor._signature`); טרייסינג Langfuse.
- **קאש** — מחליפים את שני ה-`dict` הגלובליים הבלתי-חסומים ב-TTL+LRU, מגובה Redis כאשר
  `PAZ_PERSIST=redis_postgres` (בטוח ל-uvicorn רב-workers; היום זה נשבר).
- **Langfuse v3** — מצמידים `langfuse>=3`, לקוח יחיד ברמת מודול,
  `@observe(as_type="generation")` על `ask()` כך שפרומפט/תשובה/טוקנים/עלות/latency
  באמת נרשמים, ו-`flush()` ב-`lifespan` shutdown. פותר ממצאים #1 ו-#2.

### 4.4 סטרימינג הוויכוח ל-UI

`astream_events` על גרף ה-LangGraph → פרסום לבאס הקיים → WebSocket → הדשבורד מציג
Analyst → Critic → Decider מופיעים בזמן אמת. זול לביצוע, ומשנה לגמרי את תחושת האיכות
בהדגמה. בדרך מסירים את ה-`client` החי מ-`DebateState` — זה מה שחוסם היום הוספת
checkpointer.

---

## 5. Pillar 2 — ארגז כלים דטרמיניסטי למודלים ⭐

**קובץ חדש:** `src/paz_rav/agents/tools.py`.

היום המודל מקבל JSON קפוא וחייב לנחש "מה אם". השדרוג: הליבה הכמותית נחשפת ככלים
שהמודל **קורא להם**, דרך ה-tool runner של ה-SDK.

**זה מחזק את חוק הברזל, לא מחליש אותו:** המודל עדיין לא מחשב — הוא **מבקש חישוב**
מ-`quant/`. במקום שה-Critic יטען "אולי קפיצה של 3% תסכן", הוא יריץ את התרחיש ויקבל
מספר אמיתי מהתאום הדיגיטלי.

| כלי | עוטף | מחזיר |
|---|---|---|
| `what_if(spot_move_pct, iv_shift_vol, days_forward)` | `structure_pnl` + `grid_stats` | P&L חדש, % מהמקסימום, POP, מרחק מהסטופ |
| `price_at(spot, on_date)` | `structure_pnl` | שווי המבנה בנקודה |
| `position_greeks()` | חדש ב-`quant/` מעל `greeks()` | דלתא / גמא / תטא / וגא נטו |
| `roll_cost(new_expiry, new_short_strike)` | התאום הדיגיטלי | עלות גלגול |
| `similar_cases(k, min_similarity)` | `CaseMemory.similar` הקיים | עסקאות סגורות דומות |
| `payoff_curve(n)` | `grid_stats` | הצורה, כדי שהמודל "יראה" אותה |

**הכללים ששומרים על השפיות:**

1. כל כלי **טהור וקריאה-בלבד**, מחושב ב-`quant/`. המודל בוחר *איזו שאלה לשאול*,
   לעולם לא את התשובה.
2. סכמות `strict: true` וחסומות (`|spot_move_pct| ≤ 25`, `days_forward ≤ 60`) — אין נדידה.
3. **כל קריאת כלי נרשמת ל-`result["evidence"]` ומוצגת ב-UI.** המשתמש רואה בדיוק אילו
   תרחישים ה-Critic בדק ומה יצא. זה גם ה-audit trail וגם ההדגמה החזקה ביותר בפרויקט.
4. `max_uses` לכל תפקיד (Critic 6 בדיקות, Decider 3) — התקציב חסום מראש.

**תוספת אופציונלית, כבויה כברירת מחדל — בדיקת קטליזטורים.** קריאה נפרדת וצרה עם
`web_search_20260209` של Anthropic, שמחזירה **דגלים בלבד** בסכמה קשיחה
(`earnings_in_days`, `macro_event`, `ex_div`) — לעולם לא מספר שנכנס לחישוב. זו הדרך
היחידה להכניס מודעות-לחדשות בלי לשבור את החוק.

---

## 6. Pillar 3 — Evals + CI: להוכיח שזה עובד

### 6.1 Golden dataset

`tests/evals/dataset/` — ~60–80 מקרי `Situation` / `OpenSituation`:

- כל הפוזיציות הסגורות (סקריפט ייצוא מ-Postgres) — מקרים אמיתיים עם תוצאה ידועה.
- מקרי-קצה בנויים ביד: פריצת strike קצר, 21-DTE בדיוק, 90% רווח, IV crush, גאפ מעבר
  לשורט, ואיתותים סותרים במכוון.

### 6.2 בודקים דטרמיניסטיים — *הפנינה של הפרויקט*

לראשונה חוק הברזל נאכף **מכנית**, לא בהבטחה:

| Grader | מה בודק |
|---|---|
| **`grounding`** | כל מספר שמופיע ב-`reasons` / `rationale` **חייב** להתקיים ב-Situation או בתוצאת כלי (חילוץ numerals + התאמה בסבילות). **מספר מומצא = כישלון קשה.** זה בדיוק מה שהפרויקט מבטיח ומעולם לא בדק |
| `schema_valid` | פרסינג Pydantic מלא |
| `tool_discipline` | כל ארגומנט בתחום; אין סתירה בין תוצאת כלי לפרוזה |
| `stance_opposition` | ה-Critic באמת מתנגד ל-Analyst (לא מסכים איתו בניסוח אחר) |
| `decision_vs_outcome` | רק למקרים מפוזיציות אמיתיות: האם `close` ירה לפני שהרווח נשחק — **מול כלל היציאה הדטרמיניסטי כבייסליין**. זה נותן **מספר אלפא אמיתי לשכבת ה-AI** |

בנוסף `llm-as-judge` (Opus 5) לאיכות הנימוק — מכויל מול ~20 דוגמאות מתויגות ידנית,
ומשמש רק כמדד רך.

### 6.3 הרצה, טסטים ו-CI

- **Langfuse Datasets + Experiments** (v3 `dataset.run()`) — הציונים נוחתים באותו פרויקט
  שבו יושבים טרייסי הפרודקשן. `scripts/eval_run.py` + `pytest -m evals`.
- **טסטים לנתיב ה-LLM בלי רשת**: `httpx.MockTransport` מוזרק ללקוח — בלי תלות חדשה,
  בלי קלטות. סוגר את הפער שבו רגרסיה בנתיב ה-LLM מתחזה בשקט לתשובה דטרמיניסטית.
- **`.github/workflows/ci.yml`** (לא קיים היום): `ruff` + `mypy` + `pytest --cov` +
  `npm run build` + ESLint על כל PR, עם `services: postgres` (pgvector) כדי לכסות
  לראשונה את ה-repos שרצים רק בפרודקשן.
- **`.github/workflows/evals.yml`**: מריץ את ה-golden set ו**נכשל על רגרסיה** מול
  baseline שמור.
- **`uv` + `uv.lock`**; ה-`Dockerfile` עובר ל-`uv sync` במקום רשימת pip ידנית — מחסל
  את הדריפט בין `pyproject.toml` לבין ה-Dockerfile (היום שני מקורות אמת).

---

## 7. Pillar 4 — עומק כמותי

### 7.1 הפעלת numpy/scipy
כבר מוצהרים ב-extra `quant`, לא בשימוש. וקטוריזציה של `grid_stats` → רשת של 10k נקודות
או 50k מסלולי Monte-Carlo באותו זמן-קיר. משאירים את המסלול הטהור כרפרנס ומוסיפים
**מבחן פריטי בין השניים + מול `py_vollib`** — זה שהובטח בשני docstrings ומעולם לא נכתב.

### 7.2 משטח תנודתיות
`quant/surface.py` חדש: התאמת **SVI לכל תפוגה** (או SSVI חוצה-תפוגות) עם בדיקות
אי-ארביטראז'. מחליף את ה-sigma השטוח היחיד ב-`iv(strike, expiry)` בתוך `grid_stats`,
`scoring.finalize` ו-`exit_rules`.

**זה משנה מספרים אמיתיים** — כנף ה-put של הקונדור מתומחרת נכון לראשונה.
ב-UI: גרף חיוך + מבנה עתי (הוויזואל שמוכר את הפרויקט).

### 7.3 זנבות שמנים
לצד הלוגנורמלי, התפלגות **היסטורית מבוטסטרפת / Student-t** לאינטגרל ה-POP.
מציגים `pop_lognormal` לצד `pop_empirical` — כנה, ומבדל ויזואלית.

### 7.4 סיכון תיקי
`positions/portfolio.py` חדש: דלתא / גמא / תטא / וגא נטו על כל הספר, ריכוזיות לפי נייר,
ומבחן קיצון מתואם ("SPX ‎-5% ו-IV ‎+10 — מה קורה לתיק?"). מוזן ל-Reflection ולשורת KPI חדשה.

**זה בדיוק הטריגר ש-`ARCHITECTURE.md` מגדיר כמצדיק סוכן נוסף** ("they'd only earn their
place managing a correlated portfolio") — אז ההרחבה מיושרת עם כוונת המחבר, לא נגדה.

### 7.5 בקטסט כנה
`backtest/walk_forward.py` שמחליף את `scripts/backtest_demo.py`:

1. איטרציה **יום-אחר-יום** על מסלול מחיר.
2. **הפעלת כללי היציאה האמיתיים** בכל יום דרך `exit_manager.sweep`.
3. אופציונלית — ניתוב הכרעת הסגירה דרך ויכוח ה-AI, כדי למדוד **AI מול כללים**.

זה מילולית התיקון ש-`ROADMAP.md` מבקש כדי לשפוט את DACS בהוגנות ("A fair backtest needs
a day-by-day price path with those exit rules modeled"). `BacktestResult` נשמר ל-Postgres
+ endpoint + גרף עקומת הון.

### 7.6 מרחב חיפוש
ממצא #10: הרחבת האנומרציה לסריקה אמיתית (short delta × wing width × DTE), עכשיו
שהניקוד וקטורי. ממערכת שמציעה 5 מבנים — למנוע אופטימיזציה עם תצוגת חזית-יעילה.
בדרך מתקנים ש-`regime_fit` (טווח ×0.36–×1.56) מכריע היום את איבר התוחלת עצמו.

### 7.7 תיקוני נכונות שנוסעים יחד
- יבוא מעגלי `quant/valuation ↔ strategies/base`; דריסת המודול `greeks` ב-`quant/__init__.py`.
- `backtest/payoff.pnl_at_expiry` שגוי למבנים רב-תפוגתיים (DACS) — לנתב ל-`structure_pnl`.
- retention + אינדקס חלקי על `candidates`; דגימת IV-history פעם ביום + min/max מקוּשה.
- `LOG_LEVEL` לא מוחל בפועל — לוגינג מובנה אמיתי.
- קוד מת: `quant/pop.prob_of_profit`, `analytics/iv.iv_percentile`.

---

## 8. סדר ביצוע

| שלב | תוצר | למה בסדר הזה |
|---|---|---|
| **0** | `uv.lock` + CI ירוק + תיקון Langfuse v3 | בלי מדידה אי אפשר להוכיח שום שיפור |
| **1** | Pillar 1 — `agents/llm.py`, מודלים מדורגים, caching, מעקב עלות | תשתית לכל השאר |
| **2** | Pillar 2 — ארגז הכלים + `evidence` ב-UI | הפיצ'ר שמייצר "וואו" |
| **3** | Pillar 3 — golden set + graders + evals ב-CI | מוכיח ש-1 ו-2 באמת שיפרו |
| **4** | Pillar 4 — משטח, MC, תיק, בקטסט כנה | מה שהופך אותו לאמין לכסף אמיתי |

---

## 9. אימות end-to-end

```bash
# ליבה
uv sync --extra quant --extra agents --extra feeds --extra dev
uv run ruff check . && uv run mypy src && uv run pytest --cov=paz_rav
cd web && npm run build          # tsc -b חייב לעבור (noUnusedLocals פעיל)

# הרצה מלאה
docker compose up -d --build
curl -s http://localhost:8000/health
curl -s "http://localhost:8000/api/top?n=5"
docker inspect --format='{{.State.Health.Status}}' paz-rav-app-1   # → healthy
```

**Pillar 1** — עם `ANTHROPIC_API_KEY` אמיתי: `POST /api/positions/{id}/close-advice`,
ואז לוודא ב-Langfuse UI שיש **generation** עם prompt / completion / tokens / עלות
(לא רק event), ושה-`cache_read_input_tokens` בקריאות 2–3 גדול מאפס. לוודא ש-`result.cost`
מופיע ב-UI. בלי מפתח — הנתיב הדטרמיניסטי עדיין עונה, וכל 106 הטסטים הקיימים עוברים.

**Pillar 2** — לפתוח פוזיציה ולבקש עצה: `result["evidence"]` חייב להכיל קריאות `what_if`
עם ארגומנטים בתחום, וה-P&L שהוחזר חייב להיות **זהה** לחישוב ידני של `structure_pnl`
באותם פרמטרים (טסט פריטי).

**Pillar 3** — `uv run python scripts/eval_run.py` → הריצה מופיעה ב-Langfuse Experiments;
`grounding` = 100%; הרצת CI על PR עם prompt מכוון-רע חייבת **להיכשל**.

**Pillar 4** — `pytest tests/test_surface.py` (SVI ללא ארביטראז', פריטי מול הרשת הטהורה);
`uv run python -m paz_rav.backtest.walk_forward` — DACS חייב להיבדק **עם** כללי יציאה,
ולדווח מספר שונה מהסימולציה הפסיבית הנוכחית.
