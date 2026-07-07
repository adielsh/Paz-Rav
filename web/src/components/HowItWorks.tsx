import type { ReactNode } from "react";
import { InfoButton } from "./Modal";
import { IconBrain, IconGauge, IconLayers, IconScale, IconSitemap } from "./Icon";

function Step({
  n,
  title,
  children,
  tone = "primary",
  icon,
  more,
}: {
  n: number;
  title: string;
  children: ReactNode;
  tone?: "primary" | "accent" | "good";
  icon: ReactNode;
  more?: { title: string; body: ReactNode };
}) {
  const ring =
    tone === "accent" ? "border-accent/30 bg-accent/5" : tone === "good" ? "border-good/30 bg-good/5" : "border-primary/30 bg-primary/5";
  const badge =
    tone === "accent" ? "bg-accent text-white" : tone === "good" ? "bg-good text-white" : "bg-primary text-white";
  return (
    <div className={`relative rounded-2xl border ${ring} p-5 shadow-card`}>
      <div className="flex items-center gap-3 mb-2">
        <span className={`grid place-items-center w-8 h-8 rounded-xl text-sm font-bold font-mono ${badge}`}>
          {n}
        </span>
        <span className="text-ink-3">{icon}</span>
        <h3 className="font-bold text-[15px] text-ink flex-1">{title}</h3>
        {more && (
          <InfoButton title={more.title} icon={icon} label="הרחבה">
            {more.body}
          </InfoButton>
        )}
      </div>
      <div className="text-[14px] text-ink-2 leading-relaxed pr-11">{children}</div>
    </div>
  );
}

/** "How it works" — a bright, child-friendly explanation of the whole system, with the
 * heavy technical detail tucked behind info buttons (progressive disclosure). */
export default function HowItWorks() {
  return (
    <div className="space-y-5" dir="rtl">
      <div className="rounded-2xl border border-line bg-panel/80 p-6 shadow-card">
        <h2 className="text-xl font-bold text-ink mb-1">איך המערכת עובדת — בקצרה</h2>
        <p className="text-[14px] text-ink-2 leading-relaxed">
          המערכת מוצאת עסקאות אופציות טובות, בודקת אותן, ועוזרת לך להחליט מתי לפתוח ומתי לסגור.
          <b className="text-ink"> חוק הזהב:</b> כל מספר (רווח, סיכון, הסתברות) מחושב במחשב בצורה
          מדויקת — ה-AI אף פעם לא ממציא מספר, הוא רק <b className="text-ink">שוקל</b> את המספרים
          שכבר חושבו.
        </p>
      </div>

      <Step
        n={1}
        tone="primary"
        icon={<IconGauge width={18} height={18} />}
        title="המנוע סורק את השוק"
        more={{
          title: "מה נחשב בשלב הזה",
          body: (
            <ul className="space-y-1.5 text-[13.5px] text-ink-2 leading-relaxed list-disc pr-5">
              <li>גריקים (דלתא/גמא/theta), IV rank, מדד מגמה (regime), RSI — הכל בפייתון טהור.</li>
              <li>מונה ומדרג מועמדים ל-Iron Condor ול-DACS לפי ציון אחיד.</li>
              <li>אותה פונקציה בדיוק רצה גם על היסטוריה (בקטסט) — כך שמה שנבדק = מה שירוץ חי.</li>
            </ul>
          ),
        }}
      >
        כל כמה שניות המערכת מסתכלת על מחירי אופציות אמיתיים, מחשבת סיכוי־רווח לכל עסקה, ומדרגת את
        חמש הטובות ביותר בכל אסטרטגיה.
      </Step>

      <Step
        n={2}
        tone="accent"
        icon={<IconScale width={18} height={18} />}
        title="ועדת AI בודקת כל עסקה"
        more={{
          title: "המנתח והמבקר",
          body: (
            <p className="text-[13.5px] text-ink-2 leading-relaxed">
              המנתח מציע פסק־דין (לפתוח / בזהירות / לוותר), והמבקר טוען את הצד ההפוך כדי לחשוף סיכון.
              אם ההתנגדות חריפה — ההחלטה חוזרת למנתח לשקילה חוזרת. ההפרדה בין הצעה לביקורת מקטינה
              ביטחון־יתר ותופסת יותר עסקאות גרועות.
            </p>
          ),
        }}
      >
        לפני שאתה פותח, שני "יועצים" עוברים על העסקה: אחד מציע, השני מתנגד — ואתה רואה גם את הנימוק
        וגם את הצד ההפוך.
      </Step>

      <Step
        n={3}
        tone="good"
        icon={<IconBrain width={18} height={18} />}
        title="שלושה מודלי AI מייעצים מתי לסגור"
        more={{
          title: "הדיבייט על הסגירה",
          body: (
            <p className="text-[13.5px] text-ink-2 leading-relaxed">
              על פוזיציה פתוחה, בלחיצת כפתור, רצות שלוש קריאות Claude אמיתיות על גרף LangGraph:
              מנתח → מבקר (איפכא מסתברא) → מכריע. אם המכריע לא בטוח (ביטחון נמוך) — ההחלטה חוזרת
              למנתח לסבב אחד. הם שוקלים רק מספרים שכבר חושבו (רווח, ימים לפקיעה, מרחק מהסטופ), ושולפים
              עסקאות דומות שנסגרו בעבר (זיכרון מקרים) כדי להישען על ההיסטוריה שלך.
            </p>
          ),
        }}
      >
        כשיש לך פוזיציה פתוחה ואתה שואל "מתי לסגור?", שלושה יועצי־AI מתווכחים — אחד בעד, אחד נגד,
        ואחד מכריע — ומראים לך המלצה ברורה (להחזיק / לסגור / להקטין). המלצה בלבד — אתה מבצע בברוקר.
      </Step>

      <Step
        n={4}
        tone="primary"
        icon={<IconLayers width={18} height={18} />}
        title="המערכת לומדת מהעסקאות שלך"
        more={{
          title: "זיכרון מקרים + רפלקציה",
          body: (
            <p className="text-[13.5px] text-ink-2 leading-relaxed">
              כל פוזיציה שנסגרת נשמרת כווקטור תכונות דטרמיניסטי (pgvector) יחד עם התוצאה האמיתית.
              הדיבייט הבא שולף מקרים דומים. בנוסף, "סוכן רפלקציה" סוקר את כל ההיסטוריה וממליץ על
              כוונונים — ייעוץ בלבד, ורק כשיש מספיק דאטה.
            </p>
          ),
        }}
      >
        ככל שתסגור יותר עסקאות, המערכת זוכרת איך עסקאות דומות נגמרו ומשתמשת בזה כדי לייעץ טוב יותר —
        ובעמוד "תובנות" היא סוקרת את כל העונה כמו מאמן וממליצה מה לשפר.
      </Step>

      <div className="rounded-2xl border border-line bg-panel2/60 p-5 shadow-card">
        <div className="flex items-center gap-2.5 mb-2">
          <span className="text-primary">
            <IconSitemap width={18} height={18} />
          </span>
          <h3 className="font-bold text-[15px] text-ink">למה זה בנוי ככה?</h3>
        </div>
        <p className="text-[13.5px] text-ink-2 leading-relaxed">
          המערכת רצה כתהליך אחד עם גבולות מודול נקיים ("בית עם חדרים"), חוץ מחלק אחד שכבר הופרד
          לשירות נפרד — <b className="text-ink">דיבייט הסגירה</b> — כי הוא איטי ויקר (קריאות AI) וכדאי
          שיתרחב בנפרד. Redis שומר את "מה שקורה עכשיו", Postgres שומר את "מה שקרה" (כולל זיכרון
          המקרים).
        </p>
      </div>
    </div>
  );
}
