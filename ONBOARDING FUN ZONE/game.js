/* ============================================================
   פז רב — אזור הכיף · game engine + content
   Vanilla JS, works from file:// with a double click.
   ============================================================ */
(() => {
'use strict';

/* ---------------- state ---------------- */
const KEY = 'pazrav-funzone-v1';
function loadState(){
  try { return JSON.parse(localStorage.getItem(KEY) || 'null'); }
  catch { return null; }
}
let S = Object.assign({ xp: 0, stars: {}, unlocked: 1, muted: false }, loadState() || {});
function save(){ try { localStorage.setItem(KEY, JSON.stringify(S)); } catch {} }

/* ---------------- dom helpers ---------------- */
const $ = s => document.querySelector(s);
const screen = $('#screen');
function el(tag, cls, html){
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
}
function shake(node){
  node.classList.remove('shake');
  void node.offsetWidth;
  node.classList.add('shake');
}
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ---------------- audio (tiny arcade blips) ---------------- */
let AC = null;
function tone(freq, delay, dur, type = 'triangle', gain = 0.09){
  if (S.muted) return;
  try {
    AC = AC || new (window.AudioContext || window.webkitAudioContext)();
    const t0 = AC.currentTime + delay;
    const o = AC.createOscillator(), g = AC.createGain();
    o.type = type; o.frequency.value = freq;
    g.gain.setValueAtTime(gain, t0);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    o.connect(g).connect(AC.destination);
    o.start(t0); o.stop(t0 + dur + 0.05);
  } catch {}
}
const sGood = () => { tone(660, 0, .12); tone(880, .1, .16); };
const sBad  = () => { tone(196, 0, .2, 'sawtooth', .05); };
const sWin  = () => { [523, 659, 784, 1047].forEach((f, i) => tone(f, i * .12, .22)); };

/* ---------------- confetti ---------------- */
const CONF_COLORS = ['#2e7df6', '#8a5cff', '#14b58b', '#ef6157', '#ffb020'];
function confetti(n = 90){
  if (reducedMotion) return;
  for (let i = 0; i < n; i++){
    const b = el('span', 'confetti-bit');
    b.style.left = Math.random() * 100 + 'vw';
    b.style.background = CONF_COLORS[i % CONF_COLORS.length];
    b.style.animationDuration = (2.2 + Math.random() * 2) + 's';
    b.style.animationDelay = (Math.random() * .6) + 's';
    b.style.transform = `rotate(${Math.random() * 360}deg)`;
    document.body.appendChild(b);
    setTimeout(() => b.remove(), 5200);
  }
}

/* ---------------- hud ---------------- */
function totalStars(){ return Object.values(S.stars).reduce((a, b) => a + b, 0); }
function updateHud(){
  $('#hud-stars').textContent = totalStars();
  $('#hud-xp').textContent = S.xp;
  $('#mute-btn').textContent = S.muted ? '🔇' : '🔊';
}

/* ---------------- shared widgets ---------------- */

/* multiple-choice quiz; done(mistakes) */
function quiz(container, questions, done){
  let qi = 0, mistakes = 0;
  const box = el('div', 'card');
  container.appendChild(box);
  function show(){
    box.innerHTML = '';
    if (qi >= questions.length){ done(mistakes); return; }
    const dots = el('div', 'progress-dots');
    questions.forEach((_, i) =>
      dots.appendChild(el('i', i < qi ? 'done' : i === qi ? 'now' : '')));
    box.appendChild(dots);
    const q = questions[qi];
    box.appendChild(el('div', 'quiz-q', q.q));
    const opts = el('div', 'quiz-opts');
    q.opts.forEach((o, i) => {
      const b = el('button', 'btn', o);
      b.onclick = () => {
        if (i === q.correct){
          sGood();
          b.classList.add('hit-good');
          [...opts.children].forEach(x => x.disabled = true);
          box.appendChild(el('div', 'why', '✅ ' + q.why));
          const next = el('button', 'btn primary mt', qi === questions.length - 1 ? 'סיימנו! 🏁' : 'לשאלה הבאה ⬅');
          next.onclick = () => { qi++; show(); window.scrollBy({ top: -60 }); };
          box.appendChild(next);
          next.focus();
        } else {
          sBad(); mistakes++;
          b.classList.add('hit-bad'); b.disabled = true;
          shake(box);
        }
      };
      opts.appendChild(b);
    });
    box.appendChild(opts);
  }
  show();
}

/* chat stepper: reveals steps one by one; done() at the end */
function stepper(container, steps, done, btnLabel = 'מה קורה עכשיו? ⬅'){
  const chat = el('div', 'chat');
  container.appendChild(chat);
  let i = 0;
  const next = el('button', 'btn primary', btnLabel);
  container.appendChild(next);
  next.onclick = () => {
    const st = steps[i++];
    if (st.loop){
      chat.appendChild(el('div', 'loopback', st.text));
    } else {
      chat.appendChild(el('div', 'bubble ' + st.who, `<b>${st.name}</b>${st.text}`));
    }
    tone(440 + i * 40, 0, .07);
    next.scrollIntoView({ block: 'nearest', behavior: reducedMotion ? 'auto' : 'smooth' });
    if (i >= steps.length){ next.remove(); done(); }
  };
}

/* order game: click chips in the right order; done(mistakes) */
function orderGame(container, items, done){
  let next = 0, mistakes = 0;
  const card = el('div', 'card');
  card.appendChild(el('h3', null, '🧩 סדרו את המסוע: לחצו על התחנות לפי הסדר הנכון'));
  const slots = el('ol', 'slots');
  items.forEach(() => slots.appendChild(el('li', null, '&nbsp;')));
  const pool = el('div', 'pool');
  const idx = items.map((_, i) => i).sort(() => Math.random() - .5);
  idx.forEach(i => {
    const b = el('button', 'btn', items[i].t);
    b.onclick = () => {
      if (i === next){
        sGood();
        const li = slots.children[next];
        li.classList.add('filled');
        li.innerHTML = `<div><b>${items[i].t}</b> — <small>${items[i].d}</small></div>`;
        b.remove();
        next++;
        if (next >= items.length) done(mistakes);
      } else {
        sBad(); mistakes++; shake(b);
      }
    };
    pool.appendChild(b);
  });
  card.appendChild(slots);
  card.appendChild(pool);
  container.appendChild(card);
}

/* ---------------- level completion ---------------- */
function starsFor(mistakes, generous){
  const lim2 = generous ? 3 : 2;
  return mistakes === 0 ? 3 : mistakes <= lim2 ? 2 : 1;
}
function finishLevel(idx, mistakes, generous = false){
  const lv = LEVELS[idx];
  const stars = starsFor(mistakes, generous);
  const gained = stars * 25;
  S.stars[lv.id] = Math.max(S.stars[lv.id] || 0, stars);
  S.xp += gained;
  S.unlocked = Math.max(S.unlocked, idx + 2);
  save(); updateHud();
  sWin();
  if (stars === 3) confetti(70);

  const ov = el('div', 'overlay');
  const starHtml = [1, 2, 3].map(i => `<span class="s${i <= stars ? ' lit' : ''}">⭐</span>`).join('');
  const modal = el('div', 'modal', `
    <h2>${stars === 3 ? 'מושלם! 🎉' : stars === 2 ? 'כל הכבוד! 👏' : 'עברתם! 💪'}</h2>
    <div class="star-row">${starHtml}</div>
    <div class="xp-gain">+${gained} XP</div>
    <p>${lv.doneMsg}</p>
  `);
  const row = el('div', 'cta-row');
  const mapBtn = el('button', 'btn', '🗺️ למפה');
  mapBtn.onclick = () => { ov.remove(); renderMap(); };
  row.appendChild(mapBtn);
  if (idx + 1 < LEVELS.length){
    const nxt = el('button', 'btn primary', `העולם הבא: ${LEVELS[idx + 1].icon} ⬅`);
    nxt.onclick = () => { ov.remove(); startLevel(idx + 1); };
    row.appendChild(nxt);
  } else {
    const cert = el('button', 'btn amber', '🎓 לתעודה!');
    cert.onclick = () => { ov.remove(); renderCertificate(); };
    row.appendChild(cert);
  }
  modal.appendChild(row);
  ov.appendChild(modal);
  document.body.appendChild(ov);
}

/* ---------------- level shell ---------------- */
function levelShell(idx){
  const lv = LEVELS[idx];
  screen.innerHTML = '';
  const head = el('div', 'level-head');
  head.appendChild(el('div', 'lv-icon', lv.icon)).style.setProperty('--nc', lv.color);
  head.appendChild(el('h1', null, `עולם ${idx + 1} · ${lv.name}`));
  const back = el('button', 'btn ghost', '🗺️ למפה');
  back.onclick = renderMap;
  head.appendChild(back);
  screen.appendChild(head);
  window.scrollTo({ top: 0 });
  return screen;
}

/* ============================================================
   LEVELS
   ============================================================ */

/* ---------- 1 · the condor playground ---------- */
function lvCondor(idx){
  const root = levelShell(idx);
  root.appendChild(el('div', 'card tint-amber', `
    <span class="eyebrow">🙋 מתחילים מהבסיס</span>
    <h2>מה אנחנו בכלל סוחרים כאן?</h2>
    <p><b>פז רב</b> סורק את השוק ובונה שתי אסטרטגיות אופציות:</p>
    <p>🦅 <b>Iron Condor</b> — התערבות שהמניה <b>תישאר רגועה</b>. מוכרים "תעלה" סביב המחיר,
    מקבלים כסף מראש (קרדיט 💰), ואם המחיר נשאר בתוך התעלה עד הפקיעה — הקרדיט כולו שלנו.
    אם הוא בורח החוצה — מפסידים, אבל ההפסד <b>חסום מראש</b> על ידי הכנפיים.</p>
    <p>📅 <b>DACS</b> (מרווח קלנדרי אלכסוני אדפטיבי) — קונים אופציה עם פקיעה רחוקה, מוכרים אחת
    קרובה. הזמן שוחק את הקרובה מהר יותר — ומזה מרוויחים. בניגוד לקונדור, ה־DACS דורש
    <b>ניהול אקטיבי</b> לאורך הדרך.</p>
    <p><small>💡 אגב דיוק: כל סכומי הדולר במערכת נשמרים <b>למניה בודדת</b>, וחוזה אופציות אמריקאי
    הוא ×100 — התצוגה מכפילה. במשחק שלנו כבר הכפלנו בשבילכם.</small></p>
  `));

  /* interactive condor payoff */
  const play = el('div', 'card payoff');
  play.appendChild(el('h3', null, '🎮 שחקו: גררו את מחיר המניה וראו מה קורה לקונדור'));
  play.appendChild(el('p', null,
    'הקונדור שלנו: סטרייקים 80 / 85 / 115 / 120, קרדיט של <b>$150</b>. ' +
    'האזור הירוק = רווח מלא. המשימה: מצאו את <b>שתי נקודות האיזון</b> (איפה שהרווח מתאפס).'));

  const chart = el('div', 'chart');
  const bar = el('div', 'zone-bar');
  const marker = el('div', 'price-marker', '📍');
  const labels = el('div', 'strike-labels',
    `<span style="left:16.7%">80</span><span style="left:25%">85</span>
     <span style="left:75%">115</span><span style="left:83.3%">120</span>`);
  const range = document.createElement('input');
  range.type = 'range'; range.min = 70; range.max = 130; range.step = 0.5; range.value = 100;
  range.setAttribute('aria-label', 'מחיר המניה בפקיעה');
  chart.append(marker, bar, labels, range);

  const read = el('div', 'pnl-read');
  const badges = el('div', 'be-badges');
  const beLo = el('span', 'be', '◻️ נקודת איזון תחתונה');
  const beHi = el('span', 'be', '◻️ נקודת איזון עליונה');
  badges.append(beLo, beHi);
  const cheer = el('p', 'center', '');
  const found = { lo: false, hi: false };

  function pnl(p){
    if (p >= 85 && p <= 115) return 150;
    if (p < 85) return 150 - 100 * Math.min(85 - p, 5);
    return 150 - 100 * Math.min(p - 115, 5);
  }
  function update(){
    const p = +range.value, v = pnl(p);
    marker.style.left = ((p - 70) / 60 * 100) + '%';
    read.className = 'pnl-read ' + (v > 10 ? 'win' : v < -10 ? 'lose' : 'zero');
    read.innerHTML = `מחיר: $${p} &nbsp;·&nbsp; ${v >= 0 ? 'רווח' : 'הפסד'}: $${Math.abs(v)}`;
    if (Math.abs(v) <= 15){
      if (p < 100 && !found.lo){ found.lo = true; beLo.textContent = '✅ איזון תחתון (~$83.5)'; beLo.classList.add('found'); sGood(); }
      if (p > 100 && !found.hi){ found.hi = true; beHi.textContent = '✅ איזון עליון (~$116.5)'; beHi.classList.add('found'); sGood(); }
      if (found.lo && found.hi && !cheer.textContent){
        cheer.innerHTML = '🎉 <b>מצאתם את שתיהן!</b> שימו לב: ההפסד המקסימלי חסום ב־$350 — הכנפיים (80 ו־120) מגינות עלינו.';
        confetti(40);
      }
    }
  }
  range.oninput = update;
  update();
  play.append(chart, read, badges, cheer);
  root.appendChild(play);

  quiz(root, [
    {
      q: 'מתי ה־Iron Condor מרוויח את המקסימום?',
      opts: ['כשהמניה מזנקת 🚀', 'כשהמניה נשארת רגועה בתוך התעלה 😴', 'כשהמניה קורסת 📉', 'כשיש דרמה בחדשות 📰'],
      correct: 1,
      why: 'הקונדור גובה קרדיט מראש ושומר עליו כל עוד המחיר נשאר בין הסטרייקים הקצרים (85–115). שקט = כסף.'
    },
    {
      q: 'ומה הרעיון של DACS?',
      opts: [
        'לקנות אופציה אחת ולקוות לטוב 🤞',
        'לנחש לאן השוק הולך 🔮',
        'לקנות פקיעה רחוקה ולמכור קרובה — ולהרוויח מהזמן שנשחק ⏳',
        'לקנות מניות רגילות 📄'
      ],
      correct: 2,
      why: 'האופציה הקרובה נשחקת מהר יותר מהרחוקה — הפער הזה הוא הרווח. וזו אסטרטגיה שחיה על ניהול אקטיבי.'
    }
  ], m => finishLevel(idx, m));
}

/* ---------- 2 · the golden rule sorter ---------- */
function lvGolden(idx){
  const root = levelShell(idx);
  root.appendChild(el('div', 'card tint-py', `
    <span class="eyebrow">📏 החוק שאי אפשר לשבור</span>
    <h2>חוק הזהב של פז רב</h2>
    <p>כל <b>מספר</b> במערכת — כל גריק, IV, מחיר, הסתברות רווח ו־P&L — מגיע מ<b>פייתון
    דטרמיניסטי</b> 🐍. מודלי שפה 🧠 רק <b>חושבים על</b> מספרים שכבר חושבו — הם אף פעם לא
    ממציאים אחד.</p>
    <p>עכשיו נבדוק אתכם: לכל משימה, החליטו מי אחראי עליה. זהירות — יש כאן כמה הפתעות! 😏</p>
  `));

  const items = [
    { t: '🧮 לחשב דלתא, גמא ותטא של אופציה', py: true,
      why: 'quant/greeks.py — מתמטיקה טהורה עם פונקציות טהורות. לב הדיוק של המערכת.' },
    { t: '✍️ לנסח את ההסבר על ההמלצה במילים פשוטות', py: true,
      why: 'הפתעה! ה־Explainer הוא היום תבנית קבועה. פעם הוא קרא ל־LLM — אבל מודל שכותב פרוזה עם מספרים עלול לשבש אותם, וזה הדבר האחד שאסור כאן.' },
    { t: '⚖️ לפסוק take / caution / pass על מועמד חדש', py: true,
      why: 'הפתעה שנייה! האנליסט והמבקר של ועדת הפתיחה הם קוד חוקים דטרמיניסטי — בלי שום LLM. ולכן זול לבדוק ולהריץ בבקטסט.' },
    { t: '🤔 להכריע hold / close / reduce על פוזיציה פתוחה', py: false,
      why: 'דיבייט הסגירה — המקום היחיד שבו מודלי שפה באמת מכריעים. שלושה מודלים אמיתיים מתווכחים על מספרים שפייתון חישב.' },
    { t: '💵 לחשב את הרווח הממומש כשסוגרים פוזיציה', py: true,
      why: 'מחושב ישירות מהמחיר האמיתי שדיווחתם מהברוקר — לעולם לא מנוחש ולא ממודל.' },
    { t: '🫆 לבנות את "טביעת האצבע" של עסקה בספר הזיכרונות', py: true,
      why: 'הווקטור נבנה ישירות מהמספרים שכבר חושבו (ימים לפקיעה, רווח, IV, מרחק מהסטופ) — לא embedding של מודל שפה. הכול שחזיר ובדיק.' },
    { t: '🚨 להפעיל את כלל היציאה "50% רווח או 21 יום לפקיעה"', py: true,
      why: 'positions/exit_rules — חוקים קבועים ושקופים. והם רק מדליקים דגל 🚩, אף פעם לא סוגרים לבד.' },
    { t: '🧑‍🏫 לפרש את סטטיסטיקת כל העסקאות ולהציע כיוונונים', py: false,
      why: 'המאמן (reflection agent): פייתון סופר את הציונים, ה־LLM רק מפרש את הסיכום ומציע. וגם אז — המלצה בלבד.' }
  ];

  const stage = el('div', 'card sort-stage');
  root.appendChild(stage);
  let i = 0, mistakes = 0;
  function show(){
    stage.innerHTML = '';
    if (i >= items.length){
      stage.remove();
      quiz(root, [{
        q: 'אז מה בעצם חוק הזהב אומר?',
        opts: [
          'ה־AI בודק את החישובים של פייתון 🔍',
          'פייתון מחשב כל מספר; ה־AI רק שוקל מספרים שכבר חושבו 🐍➕🧠',
          'משתמשים ב־AI הכי חזק שיש לכל דבר 💪',
          'אסור להשתמש ב־AI בכלל 🚫'
        ],
        correct: 1,
        why: 'בדיוק. ולכן כל מסך במערכת יכול להוכיח מאיפה הגיע כל מספר — אפס ניחושים.'
      }], m2 => finishLevel(idx, mistakes + m2));
      return;
    }
    stage.appendChild(el('div', 'progress-dots',
      items.map((_, k) => `<i class="${k < i ? 'done' : k === i ? 'now' : ''}"></i>`).join('')));
    stage.appendChild(el('div', 'sort-item', items[i].t));
    const btns = el('div', 'sort-btns');
    const mk = (label, cls, isPy) => {
      const b = el('button', 'btn ' + cls, label);
      b.onclick = () => {
        if (isPy === items[i].py){
          sGood();
          stage.appendChild(el('div', 'why', '✅ ' + items[i].why));
        } else {
          sBad(); mistakes++; shake(stage);
          stage.appendChild(el('div', 'why', '❌ דווקא לא! ' + items[i].why));
        }
        [...btns.children].forEach(x => x.disabled = true);
        const next = el('button', 'btn primary mt', 'הבא ⬅');
        next.onclick = () => { i++; show(); };
        stage.appendChild(next);
        next.focus();
      };
      return b;
    };
    btns.append(mk('🐍 פייתון דטרמיניסטי', 'primary', true), mk('🧠 מודל שפה (LLM)', 'ai', false));
    stage.appendChild(btns);
  }
  show();
}

/* ---------- 3 · the pipeline conveyor ---------- */
function lvPipeline(idx){
  const root = levelShell(idx);
  root.appendChild(el('div', 'card tint-py', `
    <span class="eyebrow">🏭 המסוע המרכזי</span>
    <h2>צינור אחד שהכול זורם דרכו</h2>
    <p>בלב המערכת יש פונקציה אחת: <code>Pipeline.run_once()</code>. המתזמן מריץ אותה בלולאה
    על נתונים חיים, וה<b>בקטסטר</b> מריץ בדיוק אותה על היסטוריה. פונקציה אחת = אמת אחת.</p>
    <p>אבל רגע — באיזה סדר הדברים קורים? זה התפקיד שלכם! 👇</p>
  `));

  orderGame(root, [
    { t: '📡 פיד נתונים', d: 'שרשרת אופציות נכנסת (yfinance או IBKR, מאחורי מתאם אחד)' },
    { t: '🔬 אנליטיקה', d: 'גריקים, IV Rank, משטר שוק ו־RSI — הכול נדחס ל־Feature אחד' },
    { t: '🧱 בילדר', d: 'מרכיב, מתמחר ומדרג מועמדי קונדור ו־DACS על ציון אחד משותף' },
    { t: '🧑‍⚖️ ועדת השיפוט', d: 'אנליסט מציע פסק דין, מבקר תוקף אותו' },
    { t: '📺 דשבורד', d: 'הרשימה המדורגת מגיעה אליכם, בזמן אמת דרך WebSocket' },
    { t: '🚨 מנהל היציאות', d: 'סורק פוזיציות פתוחות ומדליק דגלים — לעולם לא סוגר לבד' }
  ], gameMistakes => {
    sWin();
    root.appendChild(el('div', 'card tint-good', `
      <h3>🎉 המסוע עובד! ולמה הסדר הזה גאוני?</h3>
      <div class="fact-row">
        <div class="fact"><b>🪞 זהות לייב/בקטסט</b>
        מה שנבדק על העבר הוא <i>בדיוק</i> הקוד שרץ בהווה — אותו <code>run_once()</code>. אין "גרסת מחקר" ו"גרסת אמת".</div>
        <div class="fact"><b>⏱️ המתזמן הוא רק שעון</b>
        לא שירות ענק — טיימר בתוך התהליך שקורא לפונקציה. פשוט בכוונה.</div>
        <div class="fact"><b>📣 אוטובוס אירועים</b>
        כל שלב מפרסם לערוץ (תבנית Observer) — וה־WebSocket מזרים לדשבורד בלי לרענן.</div>
        <div class="fact"><b>🧱 מונוליט מודולרי</b>
        הכול תהליך אחד עם גבולות פנימיים קשיחים — מפרקים לשירותים רק כשכואב באמת.</div>
      </div>
    `));
    quiz(root, [{
      q: 'הבקטסטר והמערכת החיה מסכימים תמיד. איך?',
      opts: [
        'מסנכרנים אותם ידנית כל שבוע 🔧',
        'יש צוות QA שמשווה תוצאות 🧐',
        'שניהם קוראים לאותה פונקציה בדיוק — run_once() 🪞',
        'משתמשים באותו מסד נתונים 🗄️'
      ],
      correct: 2,
      why: 'זו כל התחבולה: קוד אחד, שני מצבי הרצה. ככה עדות מהעבר באמת מעידה על ההווה.'
    }], m => finishLevel(idx, gameMistakes + m));
  });
}

/* ---------- 4 · the opening committee ---------- */
function lvCommittee(idx){
  const root = levelShell(idx);
  root.appendChild(el('div', 'card tint-ai', `
    <span class="eyebrow">🧑‍⚖️ שני שופטים, אפס ניחושים</span>
    <h2>ועדת הקבלה: אנליסט נגד מבקר</h2>
    <p>כל מועמד שהבילדר מדרג עובר ועדה של <b>שניים</b>: 🟢 <b>אנליסט</b> שמציע פסק דין
    (take / caution / pass) ו־🔴 <b>מבקר</b> שתפקידו לתקוף — למצוא את התרחיש הרע.</p>
    <p>הטוויסט הגדול: <b>שניהם קוד חוקים דטרמיניסטי</b> — אפס קריאות LLM! ולכן הוועדה זולה,
    מהירה, וניתנת לבקטסט. את הלולאה ביניהם מנהל <b>LangGraph</b>: התנגדות חמורה מחזירה את
    התיק לאנליסט לסבב תיקון אחד.</p>
    <p>בואו נצפה בישיבה אמיתית 🍿:</p>
  `));

  const sim = el('div', 'card');
  sim.appendChild(el('h3', null, '📁 תיק: Iron Condor על SPY · IV Rank 62 · ‏FOMC בעוד 3 ימים'));
  root.appendChild(sim);

  stepper(sim, [
    { who: 'system', name: '🧱 הבילדר', text: 'מועמד מדורג #1: קרדיט $150, הסתברות רווח 71%, התעלה רחבה. מעביר לוועדה.' },
    { who: 'analyst', name: '🟢 האנליסט (חוקים, לא LLM)', text: 'ה־IV Rank גבוה (62) — מוכרים פרמיה שמנה. התעלה רחבה מהתנועה הצפויה. פסק הדין שלי: <b>take</b> ✅' },
    { who: 'critic', name: '🔴 המבקר (חוקים, לא LLM)', text: 'רגע רגע! הודעת ריבית (FOMC) בעוד 3 ימים — אירוע שיכול לזרוק את המחיר מחוץ לתעלה בבת אחת. <b>התנגדות חמורה!</b> ⚠️' },
    { loop: true, text: '🔁 LangGraph: התנגדות חמורה ⇒ התיק חוזר לאנליסט לסבב תיקון (פעם אחת בלבד)' },
    { who: 'analyst', name: '🟢 האנליסט', text: 'ההתנגדות מוצדקת. אני מוריד את פסק הדין ל־<b>caution</b> 🟡 — העסקה טובה, אבל התזמון מסוכן.' },
    { who: 'system', name: '✍️ המסביר (תבנית, לא LLM)', text: 'מנסח את הסיכום מתבנית קבועה — כי מודל שכותב פרוזה עם מספרים עלול לשבש אותם. כל הדיון נרשם ב־Langfuse 📊.' }
  ], () => {
    quiz(root, [
      {
        q: 'כמה קריאות LLM יש בוועדת הפתיחה כולה?',
        opts: ['שלוש — אחת לכל סוכן 3️⃣', 'אחת — רק המסביר 1️⃣', 'אפס! כולה חוקים דטרמיניסטיים 0️⃣', 'תלוי בשוק 🤷'],
        correct: 2,
        why: 'אפס. אנליסט ומבקר הם קוד חוקים, והמסביר הוא תבנית. ולכן אפשר להריץ את הוועדה על אלף מועמדים בבקטסט בחינם.'
      },
      {
        q: 'למה בכלל שניים ולא סוכן אחד חכם?',
        opts: [
          'כי שניים נשמע מרשים יותר 😎',
          'מי שמציע וגם מבקר את עצמו באותה נשימה — בטוח בעצמו מדי. הפרדה תופסת יותר עסקאות רעות 🎯',
          'כדי לחלק את העומס בין שרתים ⚙️',
          'כי LangGraph דורש לפחות שניים 📜'
        ],
        correct: 1,
        why: 'וגם לא יותר משניים: סוכני Regime/Risk/PM היו מוסיפים עלות על שיפוט שחוקים דטרמיניסטיים כבר מכסים.'
      }
    ], m => finishLevel(idx, m));
  }, '▶ המשך הישיבה');
}

/* ---------- 5 · the closing debate ---------- */
function lvDebate(idx){
  const root = levelShell(idx);
  root.appendChild(el('div', 'card tint-ai', `
    <span class="eyebrow">🧠 כאן ה־AI באמת מחליט</span>
    <h2>הדיבייט הגדול: מתי לסגור?</h2>
    <p>"האם לסגור עכשיו?" זו שאלה עם אותות <b>סותרים באמת</b> — ולכן זה המקום היחיד במערכת
    שבו <b>שלושה מודלי שפה אמיתיים</b> מתווכחים ומכריעים, על גרף LangGraph:</p>
    <p>🟢 <b>אנליסט</b> אומר מה הוא היה עושה · 🔴 <b>מבקר</b> טוען <i>בכוונה</i> את ההפך
    (איפכא מסתברא!) · ⚖️ <b>מכריע</b> שוקל את שניהם. ואם המכריע לא בטוח — התיק חוזר
    לאנליסט לסבב חשיבה אחד נוסף.</p>
    <p>והפעם — <b>אתם</b> תנחשו מה המכריע יגיד! 🎯</p>
  `));

  const sit = el('div', 'card tint-py', `
    <h3>📐 המצב (כל מספר חושב בפייתון, כרגיל):</h3>
    <div class="fact-row">
      <div class="fact"><b>💰 רווח נוכחי</b> 48% מהרווח המקסימלי (היעד: 50%)</div>
      <div class="fact"><b>⏳ זמן</b> נשארו 9 ימים לפקיעה</div>
      <div class="fact"><b>📉 מיקום</b> המחיר זוחל לאט לעבר הסטרייק הקצר</div>
      <div class="fact"><b>🌡️ תנודתיות</b> IV Rank יורד</div>
    </div>
  `);
  root.appendChild(sit);

  const sim = el('div', 'card');
  root.appendChild(sim);
  stepper(sim, [
    { who: 'analyst', name: '🟢 האנליסט (LLM אמיתי)', text: '48% זה כמעט היעד, וה־IV עוד יורד לטובתנו. אפשר להחזיק עוד קצת ולסחוט את ה־2% האחרונים. נוטה ל־<b>hold</b>.' },
    { who: 'critic', name: '🔴 המבקר (LLM אמיתי, טוען הפוך בכוונה)', text: '9 ימים לפקיעה זו טריטוריית גמא — כל תזוזה מוגברת. והמחיר כבר זוחל לעבר השורט! להסתכן בכל הרווח בשביל 2%? <b>close</b>, עכשיו.' }
  ], () => {
    const guess = el('div', 'card tint-amber');
    guess.appendChild(el('h3', null, '🙋 תורכם: מה לדעתכם ⚖️ המכריע יפסוק?'));
    const row = el('div', 'sort-btns');
    ['🟢 hold — להחזיק', '✂️ reduce — להקטין', '🔴 close — לסגור'].forEach((t, i) => {
      const b = el('button', 'btn', t);
      b.onclick = () => {
        [...row.children].forEach(x => x.disabled = true);
        const chat = el('div', 'chat');
        chat.appendChild(el('div', 'bubble decider',
          `<b>⚖️ המכריע (LLM אמיתי)</b>הכרעה: <b>close</b> · ביטחון 0.71.
          רוב הרווח כבר בכיס; הסיכון שנשאר (גמא + זחילה לשורט) גדול מהרווח שנשאר (2%).
          ${i === 2 ? '<br>🎯 <b>קלעתם בול!</b>' : '<br>💭 ניחשתם אחרת — וזה בסדר גמור: בדיוק בגלל שהשאלה קשה, נותנים לשלושה מודלים להתווכח עליה.'}`));
        guess.appendChild(chat);
        if (i === 2){ sGood(); confetti(30); } else tone(500, 0, .1);
        showFacts();
      };
      row.appendChild(b);
    });
    guess.appendChild(row);
    root.appendChild(guess);
  }, '▶ פתחו את הדיבייט');

  function showFacts(){
    root.appendChild(el('div', 'card tint-good', `
      <h3>🏠➡️🏠 והחלק ההנדסי המגניב: הדיבייט גר בבית משלו</h3>
      <div class="fact-row">
        <div class="fact"><b>🚚 מיקרו־שירות יחיד</b>
        הדיבייט איטי ויקר (3 קריאות LLM), אז הוא הוצא לקונטיינר נפרד — <code>advisor</code> על פורט 8001. כל השאר נשאר מונוליט אחד נעים.</div>
        <div class="fact"><b>🛟 שרשרת נפילה רכה</b>
        השירות נפל? הדיבייט רץ בבית, בתוך המונוליט. אין מפתח API? יש הכרעת חוקים דטרמיניסטית. הדשבורד <i>תמיד</i> עונה.</div>
        <div class="fact"><b>🔒 אי אפשר להמציא מספר</b>
        המודלים מחויבים להחזיר JSON מובנה (forced tool-use) — עמדה + נימוקים שמצביעים על המספרים שקיבלו. פרוזה חופשית? חסומה.</div>
        <div class="fact"><b>🗳️ ייעוץ בלבד</b>
        הדיבייט אף פעם לא סוגר בעצמו — הפקודה האמיתית אצל הברוקר שלכם. וכל דיבייט נשמר ב־Langfuse על הטרייס של פתיחת הפוזיציה.</div>
      </div>
    `));
    quiz(root, [
      {
        q: 'שירות ה־advisor קרס באמצע הלילה 😱. מה יקרה כשתלחצו "מתי לסגור?"',
        opts: [
          'הדשבורד יקפא ⏳',
          'תקבלו שגיאה אדומה 🚨',
          'הדיבייט ירוץ בתוך המונוליט עצמו — ואם גם זה בלתי אפשרי, תקבלו הכרעת חוקים 🛟',
          'הפוזיציה תיסגר אוטומטית ליתר ביטחון 🔒'
        ],
        correct: 2,
        why: 'מעגל חשמל כפול: שירות מרוחק → דיבייט מקומי → חוקים דטרמיניסטיים. שירות שנופל אף פעם לא מפיל את הדשבורד.'
      },
      {
        q: 'למה דווקא הדיבייט הזה זכה להיות מיקרו־שירות, ולא, נגיד, האנליטיקה?',
        opts: [
          'כי הוא הכי חדש בקוד 🆕',
          'כי הוא איטי ויקר (LLM), נהנה מסקיילינג נפרד — והחיתוך נקי: פונקציה טהורה של מספרים, בלי מסד נתונים 🎯',
          'כי מיקרו־שירותים תמיד עדיפים 🏗️',
          'כי LangGraph חייב לרוץ בקונטיינר נפרד 📦'
        ],
        correct: 1,
        why: 'מפרקים רק כשיש טריגר אמיתי. ובזכות גבולות המודולים — ההוצאה הייתה שינוי קונפיגורציה (ADVISOR_URL), לא שכתוב.'
      }
    ], m => finishLevel(idx, m));
  }
}

/* ---------- 6 · memory book + coach ---------- */
function lvMemory(idx){
  const root = levelShell(idx);
  root.appendChild(el('div', 'card tint-good', `
    <span class="eyebrow">📓 המערכת שלומדת מעצמה</span>
    <h2>ספר הזיכרונות</h2>
    <p>כל פוזיציה שנסגרת נרשמת בספר: "עסקה שנראתה <i>ככה</i> — נגמרה <i>ככה</i>".
    כשהדיבייט רץ על פוזיציה חדשה, הוא קודם <b>מדפדף בספר</b> ושולף את העסקאות הכי דומות
    מהעבר שלכם (חיפוש דמיון ב־pgvector) — ומגיש למודלים את התוצאות שלהן כהקשר.</p>
    <p>עכשיו אתם המחשב 🤖: הנה פוזיציה חדשה — <b>איזו עסקה מהעבר הכי דומה לה?</b></p>
  `));

  const newPos = el('div', 'card tint-amber', `
    <h3>🆕 הפוזיציה החדשה</h3>
    <div class="fact-row">
      <div class="fact"><b>⏳ ימים לפקיעה</b> 11</div>
      <div class="fact"><b>💰 רווח</b> ‎+42% מהמקסימום</div>
      <div class="fact"><b>🚧 מרחק מהסטופ</b> רחוק ובטוח</div>
      <div class="fact"><b>🌡️ IV Rank</b> 30</div>
    </div>
  `);
  root.appendChild(newPos);

  const pick = el('div', 'card');
  pick.appendChild(el('h3', null, '🔎 בחרו את העסקה הכי דומה מהספר:'));
  const grid = el('div', 'mem-grid');
  const cards = [
    { right: true, html: `<b>📄 עסקה א׳</b><table>
        <tr><td>ימים לפקיעה</td><td>12</td></tr><tr><td>רווח</td><td>‎+45%</td></tr>
        <tr><td>מרחק מהסטופ</td><td>רחוק</td></tr><tr><td>IV Rank</td><td>28</td></tr>
        <tr><td>נגמרה ב…</td><td>רווח ✅</td></tr></table>` },
    { right: false, html: `<b>📄 עסקה ב׳</b><table>
        <tr><td>ימים לפקיעה</td><td>2</td></tr><tr><td>רווח</td><td>‎-15%</td></tr>
        <tr><td>מרחק מהסטופ</td><td>צמוד! 😰</td></tr><tr><td>IV Rank</td><td>80</td></tr>
        <tr><td>נגמרה ב…</td><td>הפסד ❌</td></tr></table>` },
    { right: false, html: `<b>📄 עסקה ג׳</b><table>
        <tr><td>ימים לפקיעה</td><td>40</td></tr><tr><td>רווח</td><td>‎+5%</td></tr>
        <tr><td>מרחק מהסטופ</td><td>רחוק</td></tr><tr><td>IV Rank</td><td>55</td></tr>
        <tr><td>נגמרה ב…</td><td>רווח קטן 🤏</td></tr></table>` }
  ];
  let memMistakes = 0;
  cards.sort(() => Math.random() - .5).forEach(c => {
    const b = el('button', 'mem-card', c.html);
    b.onclick = () => {
      if (c.right){
        sGood();
        b.classList.add('right');
        [...grid.children].forEach(x => x.disabled = true);
        pick.appendChild(el('div', 'why',
          '✅ בדיוק! המספרים כמעט זהים — ולכן בעולם הווקטורים היא "שכנה קרובה". ' +
          'והחוכמה האמיתית: טביעת האצבע היא <b>וקטור מהמספרים שפייתון חישב</b> (ימים, רווח, מרחק, IV…) — ' +
          'לא embedding של מודל שפה. שחזיר, בדיק, ועובד גם בלי API. ' +
          'הדמיון עצמו? קוסינוס פשוט ב־pgvector.'));
        coach();
      } else {
        sBad(); memMistakes++;
        b.classList.add('wrong'); b.disabled = true; shake(b);
      }
    };
    grid.appendChild(b);
  });
  pick.appendChild(grid);
  root.appendChild(pick);

  function coach(){
    root.appendChild(el('div', 'card tint-ai', `
      <h3>🧑‍🏫 והמאמן שצופה בכל העונה</h3>
      <p>כל השאר מחליטים על <b>עסקה אחת, עכשיו</b>. סוכן ה<b>רפלקציה</b> שונה: כמו מאמן
      שצופה בצילומי כל העונה, הוא סוקר את <i>כל</i> העסקאות הסגורות ושואל — מה עובד, ומה
      כדאי לכוונן?</p>
      <div class="fact-row">
        <div class="fact"><b>📐 פייתון סופר, ה־LLM מפרש</b>
        אחוזי הצלחה, רווח ממוצע לאסטרטגיה, סיבות סגירה — הכול מחושב בפייתון. המודל רק קורא את לוח התוצאות.</div>
        <div class="fact"><b>📦 גודל קבוע = סקיילביליות</b>
        המאמן אף פעם לא רואה שורות גולמיות — רק סיכום בגודל קבוע. עובד אותו דבר על 10 עסקאות או 10,000.</div>
        <div class="fact"><b>🤫 יושרה סטטיסטית</b>
        מתחת למינימום עסקאות הוא עונה "אין מספיק נתונים עדיין" — במקום להמציא דפוסים מרעש.</div>
        <div class="fact"><b>📚 זוכר את עצמו</b>
        כל רפלקציה נשמרת ב־Postgres ומוזנת לרפלקציה הבאה — למידה עם המשכיות. וייעוץ בלבד: הוא לא מכוונן שום דבר בעצמו.</div>
      </div>
    `));
    quiz(root, [
      {
        q: 'יש לכם רק 4 עסקאות סגורות והרצתם את המאמן. מה יקרה?',
        opts: [
          'הוא ינתח אותן לעומק — כל נתון חשוב 🔬',
          'הוא יגיד בכנות "אין מספיק נתונים עדיין" 🤫',
          'הוא ישלים נתונים מהאינטרנט 🌐',
          'הוא יקרוס 💥'
        ],
        correct: 1,
        why: 'מתחת ל־MIN_SAMPLE אין ניתוח — כי 4 נקודות זה רעש, לא דפוס. מערכת שיודעת להגיד "לא יודע" היא מערכת שאפשר לסמוך עליה.'
      },
      {
        q: 'למה טביעת האצבע בספר הזיכרונות היא לא embedding של מודל שפה?',
        opts: [
          'כי embedding יקר מדי 💸',
          'כי pgvector לא תומך בזה 🚫',
          'כי וקטור מהמספרים המחושבים הוא שחזיר, בדיק אופליין — וחוק הזהב נשמר: המודלים רואים רק מספרים אמיתיים 🐍',
          'כי ככה יצא במקרה 🎲'
        ],
        correct: 2,
        why: 'שתי עסקאות שהרגישו דומות באמת קרובות במרחב — כי הצירים הם המספרים עצמם. אפס תלות ב־API של embeddings.'
      }
    ], m => finishLevel(idx, memMistakes + m));
  }
}

/* ---------- 7 · repo tour ---------- */
function lvRepo(idx){
  const root = levelShell(idx);
  root.appendChild(el('div', 'card tint-py', `
    <span class="eyebrow">🗺️ סיור בבניין</span>
    <h2>איפה כל דבר גר בקוד?</h2>
    <p>המערכת היא <b>מונוליט מודולרי</b>: בית אחד, חדרים עם קירות קשיחים. לחצו על חדרים
    כדי להכיר אותם — צריך לבקר ב<b>לפחות 8</b> כדי לפתוח את אתגר תבניות העיצוב! 🏆</p>
    <p class="visit-count" id="visit-count"></p>
  `));

  const FOLDERS = [
    { n: 'adapters/', d: 'שער הנתונים: yfinance או Interactive Brokers מאחורי ממשק MarketData אחד. החלפת ספק = שורה אחת.', p: 'Adapter' },
    { n: 'quant/', d: 'לב הדיוק: גריקים, IV, הסתברות רווח, שיערוך. פונקציות טהורות בלבד — עם fallback בפייתון נקי, כדי שטסטים ירוצו בלי numpy.', p: null },
    { n: 'analytics/', d: 'הופך שרשרת אופציות שלמה ל־Feature אחד: IV Rank, משטר שוק, RSI.', p: null },
    { n: 'strategies/', d: 'קונדור, DACS ורג׳יסטרי. @register על מחלקה — והיא זמינה לפי שם. ציון אחד משותף משווה מבנים שונים לגמרי.', p: 'Strategy + Factory' },
    { n: 'builder/', d: 'מעטר את השרשרת בגריקים פעם אחת, מונה מועמדים מכל האסטרטגיות, ומדרג.', p: null },
    { n: 'agents/', d: 'האנליסט, המבקר, המסביר (כולם דטרמיניסטיים!), דיבייט הסגירה והמאמן — פה גרה כל שכבת השיפוט.', p: null },
    { n: 'positions/', d: 'מחזור חיי פוזיציה: כללי יציאה + מנהל היציאות שרק מדליק דגלים. הסגירה תמיד שלכם, במחיר האמיתי.', p: null },
    { n: 'services/advisor/', d: 'המיקרו־שירות היחיד: דיבייט הסגירה בקונטיינר משלו. אותו image, entrypoint אחר, פורט 8001.', p: null },
    { n: 'store/', d: 'זיכרון ⇄ Redis ⇄ Postgres מאחורי Protocols. Redis = "מה נכון עכשיו", Postgres = "מה קרה". השולחן מול ארון התיוק.', p: 'Repository' },
    { n: 'bus/', d: 'ערוצי פרסום פנימיים — כל שלב במסוע מודיע, וה־WebSocket משדר לדשבורד.', p: 'Observer' },
    { n: 'contracts/', d: 'השפה המשותפת: סכמות Pydantic (OptionQuote, Feature…) שכל מודול מדבר בהן.', p: null },
    { n: 'api/', d: 'FastAPI + WebSocket. וכלל ברזל מקומי: את בריכת ה־Postgres בונים רק בתוך lifespan — אחרת הכול נתקע בשקט.', p: null },
    { n: 'web/', d: 'הדשבורד: React + TypeScript + Tailwind + Recharts. כרטיסים חיים לפתיחה וסגירה של פוזיציות נייר.', p: null },
    { n: 'tests/', d: 'טסטים טהורים: בלי רשת, בלי דוקר, בלי numpy. רצים בכל מקום, תמיד.', p: null }
  ];

  const grid = el('div', 'folder-grid');
  const info = el('div', 'card folder-info', '<p class="center">👆 לחצו על חדר כדי להציץ פנימה</p>');
  const visited = new Set();
  const countEl = () => $('#visit-count');
  const challengeHolder = el('div');
  let challengeShown = false;

  function refreshCount(){
    countEl().textContent = `ביקרתם ב־${visited.size} מתוך ${FOLDERS.length} חדרים ${visited.size >= 8 ? '— האתגר נפתח! 🔓' : ''}`;
    if (visited.size >= 8 && !challengeShown){
      challengeShown = true;
      sWin();
      showChallenge();
    }
  }
  FOLDERS.forEach(f => {
    const b = el('button', 'folder', `<span class="tick"></span><code>${f.n}</code>`);
    b.onclick = () => {
      tone(520, 0, .06);
      if (!visited.has(f.n)){
        visited.add(f.n);
        b.classList.add('visited');
        b.querySelector('.tick').textContent = '✅';
      }
      info.innerHTML = `<h3><code>${f.n}</code></h3><p>${f.d}</p>` +
        (f.p ? `<span class="pattern-tag">🎨 תבנית עיצוב: ${f.p}</span>` : '');
      refreshCount();
    };
    grid.appendChild(b);
  });
  root.appendChild(grid);
  root.appendChild(info);
  root.appendChild(challengeHolder);
  refreshCount();

  function showChallenge(){
    challengeHolder.appendChild(el('div', 'card tint-amber', `
      <h3>🏆 אתגר תבניות העיצוב</h3>
      <p>חמש תבניות עושות את כל העבודה הכבדה בבית הזה. תוכיחו שאתם יודעים איפה כל אחת גרה:</p>
    `));
    quiz(challengeHolder, [
      { q: '🔌 Adapter — "החלף ספק נתונים בלי שאף אחד ירגיש" גרה ב…',
        opts: ['adapters/', 'api/', 'bus/', 'quant/'], correct: 0,
        why: 'yfinance ו־IBKR מאחורי אותו ממשק MarketData — הצינור לא יודע ולא צריך לדעת מי מזין אותו.' },
      { q: '🗄️ Repository — "החלף אחסון בלי לשנות את הלוגיקה" גרה ב…',
        opts: ['contracts/', 'store/', 'web/', 'analytics/'], correct: 1,
        why: 'Protocols מגדירים את החוזה; זיכרון לטסטים, Redis+Postgres לחיים האמיתיים. אותו קוד עסקי בשני העולמות.' },
      { q: '📣 Observer — "ספר לכולם שקרה משהו" גרה ב…',
        opts: ['positions/', 'builder/', 'bus/', 'services/'], correct: 2,
        why: 'כל שלב מפרסם לערוץ, וה־WebSocket מזרים לדשבורד — בלי שאף מודול יכיר את הצרכנים שלו.' },
      { q: '🏭 Factory — "תן לי אסטרטגיה לפי שם" גרה ב…',
        opts: ['agents/', 'quant/', 'api/', 'strategies/registry'], correct: 3,
        why: '@register על המחלקה — ו־make_strategy("dacs") מחזיר אותה. הוספת אסטרטגיה לא נוגעת בשום קוד קיים.' },
      { q: '🎭 Strategy — "מבנים שונים לגמרי, ממשק אחד" גרה ב…',
        opts: ['strategies/base', 'bus/', 'adapters/', 'store/'], correct: 0,
        why: 'OptionStrategy דורש רק name ו־enumerate() — ולכן קונדור חד־פקיעתי ו־DACS רב־פקיעתי מתחרים באותה ליגה.' }
    ], m => finishLevel(idx, m));
  }
}

/* ---------- 8 · boss quiz ---------- */
function lvBoss(idx){
  const root = levelShell(idx);
  root.appendChild(el('div', 'card tint-bad', `
    <span class="eyebrow">👑 הקרב הסופי</span>
    <h2>קרב הבוס: 8 שאלות על כל מה שלמדתם</h2>
    <p>בלי רשתות ביטחון. בלי רמזים. רק אתם, המערכת, וכל מה שעברתם בשבעת העולמות. בהצלחה! 🍀</p>
  `));

  quiz(root, [
    { q: '1️⃣ מאיפה מגיע כל מספר שמופיע על המסך — כל גריק, IV ו־P&L?',
      opts: ['ממודל השפה החכם ביותר 🧠', 'מפייתון דטרמיניסטי — תמיד 🐍', 'משילוב של השניים 🤝', 'מהברוקר 🏦'],
      correct: 1,
      why: 'חוק הזהב. ה־AI רק שוקל מספרים שכבר חושבו — לעולם לא ממציא אחד.' },
    { q: '2️⃣ מה מבטיח שהבקטסט והמערכת החיה לעולם לא יסתרו זה את זה?',
      opts: ['בדיקות רגרסיה שבועיות 📋', 'שניהם קוראים לאותו run_once() בדיוק 🪞', 'מסד נתונים משותף 🗄️', 'קונפיגורציה זהה ⚙️'],
      correct: 1,
      why: 'פונקציה אחת, שני מצבי הרצה — אין "גרסת מחקר" נפרדת שמתנתקת מהמציאות.' },
    { q: '3️⃣ בוועדת הפתיחה (אנליסט + מבקר + מסביר) — כמה קריאות LLM?',
      opts: ['שלוש 3️⃣', 'שתיים 2️⃣', 'אחת 1️⃣', 'אפס 0️⃣'],
      correct: 3,
      why: 'כולם דטרמיניסטיים — כולל המסביר, שהוא תבנית (כי מודל שמנסח מספרים עלול לשבש אותם).' },
    { q: '4️⃣ תנאי יציאה התקיים על פוזיציה פתוחה. מה מנהל היציאות עושה?',
      opts: ['סוגר אותה מיד 🔒', 'מדליק דגל התראה — ולא יותר 🚩', 'שולח מייל לברוקר 📧', 'מקטין אותה בחצי ✂️'],
      correct: 1,
      why: 'ייעוץ בלבד, בכוונה: המילוי האמיתי קורה אצל הברוקר. אתם מדווחים את המחיר האמיתי — וממנו מחושב הרווח.' },
    { q: '5️⃣ איפה המקום היחיד שבו מודלי שפה באמת מכריעים החלטה?',
      opts: ['דירוג המועמדים 🧱', 'דיבייט הסגירה: אנליסט → מבקר → מכריע ⚖️', 'חישוב הגריקים 🧮', 'כללי היציאה 🚨'],
      correct: 1,
      why: 'שלושה מודלים אמיתיים על LangGraph, עם לולאת חשיבה־מחדש — כי "מתי לסגור" שוקל אותות סותרים באמת.' },
    { q: '6️⃣ למה דווקא הדיבייט הוצא למיקרו־שירות משלו (advisor)?',
      opts: ['כי ביקשו המשקיעים 💼', 'כי הוא איטי ויקר, נהנה מסקיילינג נפרד — והחיתוך נקי: פונקציה טהורה בלי מסד נתונים 🎯', 'כי LLM חייב קונטיינר נפרד 📦', 'סתם, לתרגול DevOps 🏗️'],
      correct: 1,
      why: 'מפרקים רק על טריגר אמיתי. והנפילה רכה: השירות נפל → הדיבייט רץ בבית → ואם צריך, הכרעת חוקים.' },
    { q: '7️⃣ Redis מול Postgres — במשפט אחד?',
      opts: ['Redis מהיר, Postgres איטי 🐢', 'Redis = "מה נכון עכשיו", Postgres = "מה קרה" 🗄️', 'Redis לפיתוח, Postgres לפרודקשן 🚧', 'אין הבדל אמיתי 🤷'],
      correct: 1,
      why: 'השולחן מול ארון התיוק: מצב חם ופאב/סאב ב־Redis; מועמדים, פוזיציות וספר הזיכרונות ב־Postgres (+pgvector).' },
    { q: '8️⃣ למה טביעת האצבע של עסקה בספר הזיכרונות היא לא embedding של LLM?',
      opts: ['כי זה היה יקר מדי 💸', 'כי הווקטור נבנה מהמספרים שפייתון חישב — שחזיר, בדיק אופליין, וחוק הזהב נשמר 🐍', 'כי pgvector דורש מספרים 🔢', 'כי לא הספיקו לממש 🕐'],
      correct: 1,
      why: 'הצירים הם המספרים עצמם — עסקאות שדומות באמת קרובות במרחב, בלי שום תלות במודל חיצוני. זה הקו הדטרמיניסטי שמחזיק את כל המערכת.' }
  ], m => finishLevel(idx, m, true));
}

/* ============================================================
   level registry
   ============================================================ */
const LEVELS = [
  { id: 'condor',   icon: '🦅', color: 'var(--amber-soft)', name: 'עולם הקונדור', tag: 'מה אנחנו בכלל סוחרים?', render: lvCondor,
    doneMsg: 'עכשיו אתם יודעים על מה כל המערכת בכלל מסתכלת: תעלות רגועות וזמן שנשחק.' },
  { id: 'golden',   icon: '📏', color: 'var(--py-soft)', name: 'חוק הזהב', tag: 'מי מחשב ומי חושב?', render: lvGolden,
    doneMsg: 'פייתון מחשב, ה־AI חושב — עכשיו זה בדם שלכם. זה החוק שמחזיק את כל השאר.' },
  { id: 'pipeline', icon: '🏭', color: 'var(--py-soft)', name: 'המסוע', tag: 'הצינור שהכול זורם דרכו', render: lvPipeline,
    doneMsg: 'run_once() אחד, שני מצבי הרצה — לייב ובקטסט לעולם לא יתווכחו.' },
  { id: 'committee',icon: '🧑‍⚖️', color: 'var(--good-soft)', name: 'ועדת הקבלה', tag: 'אנליסט נגד מבקר', render: lvCommittee,
    doneMsg: 'שני שופטים דטרמיניסטיים ולולאת LangGraph אחת — ואפס קריאות LLM. מפתיע, נכון?' },
  { id: 'debate',   icon: '⚖️', color: 'var(--ai-soft)', name: 'הדיבייט הגדול', tag: 'מתי לסגור? 3 מודלים רבים', render: lvDebate,
    doneMsg: 'ראיתם את המקום היחיד שבו AI באמת מכריע — ולמה הוא גר בקונטיינר משלו עם רשת ביטחון כפולה.' },
  { id: 'memory',   icon: '📓', color: 'var(--good-soft)', name: 'ספר הזיכרונות והמאמן', tag: 'המערכת שלומדת מעצמה', render: lvMemory,
    doneMsg: 'case memory + מאמן רפלקציה: העבר שלכם הופך להקשר, בלי לשבור את הקו הדטרמיניסטי.' },
  { id: 'repo',     icon: '🗺️', color: 'var(--py-soft)', name: 'סיור בבניין', tag: 'מבנה הקוד ותבניות העיצוב', render: lvRepo,
    doneMsg: 'עכשיו אתם יודעים בדיוק באיזה חדר גר כל דבר — ואיזו תבנית מחזיקה אותו.' },
  { id: 'boss',     icon: '👑', color: 'var(--bad-soft)', name: 'קרב הבוס', tag: 'החידון הגדול על הכול', render: lvBoss,
    doneMsg: 'ניצחתם את הבוס! 👑' }
];

/* ============================================================
   screens
   ============================================================ */
function renderHome(){
  screen.innerHTML = '';
  window.scrollTo({ top: 0 });
  const hero = el('div', 'hero', `
    <h1>ברוכים הבאים ל<span class="hl">פז רב</span> 🎮<br>המסע אל תוך המכונה</h1>
    <p class="sub">מנוע אסטרטגיות אופציות בזמן אמת — מוסבר כמו משחק, עולם אחרי עולם</p>
  `);
  const ctaRow = el('div', 'cta-row');
  const start = el('button', 'btn primary big', S.unlocked > 1 ? '🚀 ממשיכים במסע!' : '🚀 יוצאים למסע!');
  start.onclick = renderMap;
  ctaRow.appendChild(start);
  hero.appendChild(ctaRow);
  screen.appendChild(hero);

  screen.appendChild(el('div', 'card', `
    <h2>🤔 מה זה פז רב, בשלושה משפטים?</h2>
    <p>מערכת שסורקת את שוק האופציות, בונה ומדרגת אסטרטגיות (<b>Iron Condor</b> ו־<b>DACS</b>)
    בעזרת מתמטיקה דטרמיניסטית, ואז נותנת לשכבת AI רזה <b>לשפוט</b> אותן — אנליסט מציע, מבקר
    תוקף. הכול מוגש בדשבורד חי שבו אתם פותחים וסוגרים פוזיציות נייר.</p>
    <p>והחוק הקדוש שמחזיק הכול: <b>פייתון מחשב כל מספר. ה־AI רק חושב על מספרים שכבר חושבו.</b>
    שום דבר על המסך לא מנוחש.</p>
  `));

  screen.appendChild(el('div', 'card tint-amber', `
    <h2>🎨 מקרא הצבעים — תלמדו אותו וכל המשחק ייפתח</h2>
    <p>כל צבע במשחק (וגם בדיאגרמות של הפרויקט עצמו!) אומר משהו:</p>
    <div class="legend">
      <span class="chip"><span class="dot" style="background:var(--py)"></span>🐍 פייתון דטרמיניסטי מחשב</span>
      <span class="chip"><span class="dot" style="background:var(--ai)"></span>🧠 מודל שפה חושב</span>
      <span class="chip"><span class="dot" style="background:var(--good)"></span>🗄️ זיכרון ואחסון</span>
      <span class="chip"><span class="dot" style="background:var(--bad)"></span>🔥 המבקר והסיכונים</span>
      <span class="chip"><span class="dot" style="background:var(--amber)"></span>🙋 אתם — ההחלטה תמיד שלכם</span>
    </div>
  `));

  const reset = el('button', 'reset-link', 'איפוס התקדמות (מתחילים מאפס)');
  reset.onclick = () => {
    if (confirm('לאפס את כל הכוכבים וה־XP?')){
      S = { xp: 0, stars: {}, unlocked: 1, muted: S.muted };
      save(); updateHud(); renderHome();
    }
  };
  const wrap = el('div', 'center');
  wrap.appendChild(reset);
  screen.appendChild(wrap);
}

function renderMap(){
  screen.innerHTML = '';
  window.scrollTo({ top: 0 });
  const wrap = el('div', 'map-wrap');
  wrap.appendChild(el('h1', null, '🗺️ מפת העולמות'));
  const map = el('ol', 'map');
  LEVELS.forEach((lv, i) => {
    const li = el('li');
    const locked = i + 1 > S.unlocked;
    const stars = S.stars[lv.id] || 0;
    const node = el('button', 'node', `
      <span class="node-icon" style="--nc:${lv.color}">${locked ? '🔒' : lv.icon}</span>
      <span class="node-txt"><b>עולם ${i + 1} · ${lv.name}</b><small>${lv.tag}</small></span>
      <span class="node-stars">${locked ? '' : '⭐'.repeat(stars) + '☆'.repeat(3 - stars)}</span>
    `);
    node.disabled = locked;
    if (locked) node.title = 'סיימו את העולם הקודם כדי לפתוח';
    node.onclick = () => startLevel(i);
    li.appendChild(node);
    map.appendChild(li);
  });
  wrap.appendChild(map);
  if (Object.keys(S.stars).length === LEVELS.length){
    const certBtn = el('button', 'btn amber big', '🎓 לתעודת הבוגר שלי');
    certBtn.onclick = renderCertificate;
    const c = el('div', 'center mt');
    c.appendChild(certBtn);
    wrap.appendChild(c);
  }
  screen.appendChild(wrap);
}

function startLevel(i){
  LEVELS[i].render(i);
}

function renderCertificate(){
  screen.innerHTML = '';
  window.scrollTo({ top: 0 });
  confetti(120);
  sWin();
  screen.appendChild(el('div', 'cert', `
    <span class="big-emoji">🎓</span>
    <h1>תעודת בוגר רשמית<br>אקדמיית פז רב</h1>
    <p class="sub">הושלמו כל 8 העולמות!</p>
    <div class="stats">
      <span class="pill stars-pill">⭐ ${totalStars()} / 24 כוכבים</span>
      <span class="pill xp-pill">⚡ ${S.xp} XP</span>
    </div>
    <p><b>מה אתם יודעים עכשיו שלא ידעתם קודם:</b></p>
    <ul>
      <li>🐍 <b>חוק הזהב</b> — פייתון מחשב כל מספר; ה־AI רק שוקל מספרים שכבר חושבו.</li>
      <li>🏭 <b>run_once()</b> — פונקציה אחת מריצה גם לייב וגם בקטסט, ולכן הם לעולם מסכימים.</li>
      <li>🧑‍⚖️ <b>ועדת הפתיחה</b> — אנליסט + מבקר + מסביר, כולם דטרמיניסטיים, אפס LLM.</li>
      <li>⚖️ <b>דיבייט הסגירה</b> — המקום היחיד שבו 3 מודלים אמיתיים מכריעים, בקונטיינר משלו, עם נפילה רכה.</li>
      <li>📓 <b>ספר הזיכרונות והמאמן</b> — המערכת לומדת מהעסקאות של עצמה בלי לשבור את הקו הדטרמיניסטי.</li>
      <li>🗺️ <b>המבנה</b> — מונוליט מודולרי עם Strategy, Factory, Adapter, Repository ו־Observer שעושים את העבודה.</li>
    </ul>
    <p>📚 ההמשך הטבעי: <code>docs/ARCHITECTURE.md</code> — עכשיו תבינו כל שורה בו.</p>
  `));
  const row = el('div', 'center');
  const again = el('button', 'btn primary big', '🔁 חזרה למפה — לשחק שוב כל עולם שתרצו');
  again.onclick = renderMap;
  row.appendChild(again);
  screen.appendChild(row);
}

/* ============================================================
   wiring
   ============================================================ */
$('#home-btn').onclick = renderHome;
$('#map-btn').onclick = renderMap;
$('#mute-btn').onclick = () => { S.muted = !S.muted; save(); updateHud(); if (!S.muted) sGood(); };

updateHud();

/* deep links: #map opens the world map, #lv1–#lv8 open a level directly */
const hash = (location.hash || '').toLowerCase();
const lvMatch = hash.match(/^#lv([1-8])$/);
if (hash === '#map') renderMap();
else if (lvMatch) startLevel(+lvMatch[1] - 1);
else renderHome();

})();
