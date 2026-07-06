import type { ReactNode } from "react";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <details className="border-b border-line/60 py-2" open>
      <summary className="cursor-pointer text-sm font-semibold text-slate-200">{title}</summary>
      <div className="mt-2 text-[12px] text-slate-400 leading-relaxed space-y-1.5" dir="rtl">
        {children}
      </div>
    </details>
  );
}

export default function DacsGuide() {
  return (
    <div className="rounded-xl border border-line bg-panel/50 p-4" dir="rtl">
      <h2 className="text-sm font-semibold text-accent mb-2">מדריך DACS 1.0</h2>

      <Section title="סדר הפעולות">
        <p>1. <b>בחירת נכס:</b> מניה יציבה, RSI ~60, IV נמוך, ולא לפני דוח (בדיקת earnings).</p>
        <p>2. <b>שורט CALL:</b> ~חודש קדימה, ~8–10% מעל המחיר, דלתא ≤ 0.20.</p>
        <p>3. <b>לונג CALL:</b> חודש אחד קדימה מהשורט, אותו סטרייק, דביט קטן, וערך הלונג &gt; $1.</p>
        <p>4. <b>Fast Ratio:</b> ערך הלונג ÷ הסיכון. פחות מ־~12% → מוותרים.</p>
        <p>5. לא אופציה מתחת ל־$1. מעדיפים <b>דביט קטן</b> (לא קרדיט) לבטחונות נמוכים.</p>
      </Section>

      <Section title="סגירה אוטומטית">
        <p>קובעים <b>פקודת רווח מותנית כבר בפתיחה</b> (קנית ב־30¢ → מכירה ב־~1.1$).</p>
        <p>אם הנכס לא זז — השורט נעלם ומוכרים את הלונג, וזה הרווח.</p>
        <p>נשתדל לסגור ~<b>שבועיים לפני הפקיעה</b>, לא לחכות לרגע האחרון.</p>
      </Section>

      <Section title="נקודת סטופ (הכי חשוב!)">
        <p>לא נותנים לסטרייק לעבור את השורט <b>מינוס 1</b> (אגרסיבי) עד <b>מינוס 5</b> (שמרני).</p>
        <p>אם הגענו לסטופ — סוגרים. לפעמים בהפסד קטן, לפעמים אפילו ברווח. בממוצע רק ~20% מגיעים לשם.</p>
      </Section>

      <Section title="תרחישים">
        <p>דשדוש — מעולה · עליה קטנה — מעולה · <b className="text-bad">עליה גדולה — הסיכון היחיד</b></p>
        <p>ירידה קטנה — בסדר · ירידה גדולה — בסדר</p>
      </Section>

      <Section title="שאלות ותשובות">
        <p><b>למה DEBIT ולא CREDIT?</b> קרדיט = דרישת בטחונות גדולה וסיכון גבוה. דביט קטן מכריח מבנה שמרני ומאובטח. לפעמים יהיה קרדיט קטן כשאין ברירה — זה בסדר.</p>
        <p><b>למה דלתא ≤ 0.2?</b> מעל זה קרוב מדי לכסף. RSI נמוך? מפצים בדלתא נמוכה.</p>
        <p><b>למה לבדוק דוחות?</b> IV מושפע מדוח קרוב ויכול להעיף את השורט לשמים. בודקים ב־Yahoo → Calendars → Earnings.</p>
      </Section>

      <Section title="מערכות מסחר">
        <p><b>ThinkOrSwim</b> — פשוט (אמריקאי). <b>IB</b> — יקר יותר אך בעברית. <b>TradeStation</b> — טוב, אך חסר תצוגת דרישת בטחונות.</p>
        <p>שמים אלרט למעלה וגם למטה (למשל ב־Barchart).</p>
      </Section>
    </div>
  );
}
