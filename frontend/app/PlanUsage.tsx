"use client";
import { useEffect, useState } from "react";
import { api } from "./api";
type Plan = {
  status: string;
  enforced: boolean;
  checkout_ready: boolean;
  monthly_price_usd: number;
  usage: Record<string, number>;
  limits: Record<string, number>;
  period: string;
  note: string;
};
export default function PlanUsage({
  orgId,
  isOwner,
}: {
  orgId: string;
  isOwner: boolean;
}) {
  const [data, setData] = useState<Plan | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    api("/v1/billing", orgId)
      .then((value) => {
        if (active) setData(value);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [orgId]);
  async function open(path: string) {
    setBusy(true);
    setError("");
    try {
      const result = await api(path, orgId, {});
      window.location.assign(result.url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Billing failed");
      setBusy(false);
    }
  }
  return (
    <section className="panel" aria-label="Plan and usage">
      <span className="eyebrow">PLAN & USAGE</span>
      <h2>$59 per month</h2>
      <p>
        Billed monthly. Cancel in the billing portal. Custom-avatar setup is
        separately provisioned.
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {data && (
        <>
          <p>
            Status: {data.status} · Usage month: {data.period}
          </p>
          {!data.enforced && (
            <p>
              Pilot mode: subscription checks are off. This does not mean a
              payment was made.
            </p>
          )}
          <ul>
            {Object.entries(data.limits).map(([kind, limit]) => (
              <li key={kind}>
                {kind === "video_seconds"
                  ? "Avatar video budget"
                  : kind === "footage_seconds"
                    ? "Edited footage"
                    : "Research workflows"}
                :{" "}
                {Math.round(
                  ((data.usage[kind] || 0) /
                    (kind.endsWith("seconds") ? 60 : 1)) *
                    10,
                ) / 10}{" "}
                / {limit / (kind.endsWith("seconds") ? 60 : 1)}{" "}
                {kind.endsWith("seconds") ? "minutes" : "runs"}
              </li>
            ))}
          </ul>
          <p>{data.note}</p>
          <p>
            Avatar minutes are conservatively reserved from script length before
            each request. Failed or uncertain requests keep the reservation; no
            automatic paid overages.
          </p>
          {isOwner && (
            <div className="journey-actions">
              <button
                disabled={
                  !data.checkout_ready || busy || data.status === "active"
                }
                onClick={() => void open("/v1/billing/checkout")}
              >
                Subscribe for $59/month
              </button>
              <button
                className="secondary"
                disabled={busy || data.status === "inactive"}
                onClick={() => void open("/v1/billing/portal")}
              >
                Manage or cancel subscription
              </button>
            </div>
          )}
          {!data.checkout_ready && <p>Billing setup is not connected yet.</p>}
        </>
      )}
    </section>
  );
}
