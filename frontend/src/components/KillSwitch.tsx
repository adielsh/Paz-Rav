import { useControlQuery, useSetControlMutation } from "../store/api";
import { useT } from "../i18n/useT";
import { Pill } from "./ui";

export default function KillSwitch() {
  const { t } = useT();
  const { data: ctrl } = useControlQuery();
  const [setControl, { isLoading }] = useSetControlMutation();
  // available=false means this account has no daemon of its own — one broker connection
  // exists and it is the owner's. Render nothing rather than a switch that toggles nothing.
  if (ctrl && ctrl.available === false) return null;
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
