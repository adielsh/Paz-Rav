import type { ReactNode } from "react";

function Chevron() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="shrink-0 transition-transform duration-200 group-open:rotate-90"
      aria-hidden="true"
    >
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <details className="group border-b border-line last:border-b-0 py-2.5">
      <summary className="flex items-center gap-2 cursor-pointer text-sm font-semibold text-ink [&::-webkit-details-marker]:hidden marker:content-none">
        <Chevron />
        {title}
      </summary>
      <div className="mt-2 pr-6 text-xs text-ink-2 leading-relaxed space-y-1.5" dir="rtl">
        {children}
      </div>
    </details>
  );
}

export default function DacsGuide() {
  return (
    <div className="rounded-2xl border border-line bg-panel/50 p-4" dir="rtl">
      <h2 className="text-sm font-bold text-accent mb-1">מדריך DACS 1.0</h2>

      <Section title="סדר הפעולות">
        <p>
          1. <b className="text-ink">בחירת נכס:</b> מניה יציבה, RSI ~60, IV נמוך, ולא לפני דוח (בדיקת earnings).
        </p>
        <p>
          2. <b className="text-ink">שורט CALL:</b> ~חודש קדימה, ~8–10% מעל המחיר, דלתא ≤ 0.20.
        </p>
        <p>
          3. <b className="text-ink">לונג CALL:</b> חודש אחד קדימה מהשורט, אותו סטרייק, דביט קטן, וערך הלונג &gt; $1.
        </p>
        <p>
          4. <b className="text-ink">Fast Ratio:</b> ערך הלונג ÷ הסיכון. פחות מ־~12% → מוותרים.
        </p>
        <p>
          5. לא אופציה מתחת ל־$1. מעדיפים <b className="text-ink">דביט קטן</b> (לא קרדיט) לבטחונות נמוכים.
        </p>
      </Section>

      <Section title="סגירה אוטומטית">
        <p>
          קובעים <b className="text-ink">פקודת רווח מותנית כבר בפתיחה</b> (קנית ב־30¢ → מכירה ב־~1.1$).
        </p>
        <p>אם הנכס לא זז — השורט נעלם ומוכרים את הלונג, וזה הרווח.</p>
        <p>
          נשתדל לסגור ~<b className="text-ink">שבועיים לפני הפקיעה</b>, לא לחכות לרגע האחרון.
        </p>
      </Section>

      <Section title="נקודת סטופ (הכי חשוב!)">
        <p>
          לא נותנים לסטרייק לעבור את השורט <b className="text-ink">מינוס 1</b> (אגרסיבי) עד{" "}
          <b className="text-ink">מינוס 5</b> (שמרני).
        </p>
        <p>אם הגענו לסטופ — סוגרים. לפעמים בהפסד קטן, לפעמים אפילו ברווח. בממוצע רק ~20% מגיעים לשם.</p>
      </Section>

      <Section title="תרחישים">
        <p>
          דשדוש — מעולה · עליה קטנה — מעולה · <b className="text-bad">עליה גדולה — הסיכון היחיד</b>
        </p>
        <p>ירידה קטנה — בסדר · ירידה גדולה — בסדר</p>
      </Section>

      <Section title="שאלות ותשובות">
        <p>
          <b className="text-ink">למה DEBIT ולא CREDIT?</b> קרדיט = דרישת בטחונות גדולה וסיכון גבוה. דביט קטן
          מכריח מבנה שמרני ומאובטח. לפעמים יהיה קרדיט קטן כשאין ברירה — זה בסדר.
        </p>
        <p>
          <b className="text-ink">למה דלתא ≤ 0.2?</b> מעל זה קרוב מדי לכסף. RSI נמוך? מפצים בדלתא נמוכה.
        </p>
        <p>
          <b className="text-ink">למה לבדוק דוחות?</b> IV מושפע מדוח קרוב ויכול להעיף את השורט לשמים. בודקים
          ב־Yahoo → Calendars → Earnings.
        </p>
      </Section>

      <Section title="מערכות מסחר">
        <p>
          <b className="text-ink">ThinkOrSwim</b> — פשוט (אמריקאי). <b className="text-ink">IB</b> — יקר יותר
          אך בעברית. <b className="text-ink">TradeStation</b> — טוב, אך חסר תצוגת דרישת בטחונות.
        </p>
        <p>שמים אלרט למעלה וגם למטה (למשל ב־Barchart).</p>
      </Section>
    </div>
  );
}
