import { useControlQuery, useSetControlMutation } from "../store/api";
import { useT } from "../i18n/useT";
import { Pill } from "./ui";

export default function KillSwitch() {
  const { t } = useT();
  const { data: ctrl } = useControlQuery();
  const [setControl, { isLoading }] = useSetControlMutation();
  if (!ctrl) return <span className="muted">…</span>;
  const on = ctrl.trading_enabled;

  const toggle = async () => {
    if (on && !confirm("Disable trading? The daemon will skip new entries.")) return;
    await setControl({ trading_enabled: !on });
  };

  return (
    <div className="row">
      <span className="muted">{t("trading")}:</span>
      <Pill kind={on ? "ok" : "bad"}>{on ? t("enabled") : t("disabled")}</Pill>
      <button className={on ? "kill" : "enable"} onClick={toggle} disabled={isLoading}>
        {on ? t("kill_switch") : t("re_enable")}
      </button>
    </div>
  );
}
