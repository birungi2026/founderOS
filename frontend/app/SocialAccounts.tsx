"use client";
import { useEffect, useState } from "react";
import { api } from "./api";
type Account = {
  id: string;
  provider: string;
  name: string;
  status: string;
  permissions: string[];
  snapshot: {
    observed_at?: number;
    profile?: { followers_count?: number };
    posts?: unknown[];
  };
};
type Provider = {
  provider: string;
  configured: boolean;
  requested_permissions: string[];
};
export default function SocialAccounts({
  orgId,
  projectId,
  isOwner,
}: {
  orgId: string;
  projectId: string;
  isOwner: boolean;
}) {
  const [accounts, setAccounts] = useState<Account[]>([]),
    [providers, setProviders] = useState<Provider[]>([]),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  async function refresh() {
    const data = await api(`/v1/projects/${projectId}/social`, orgId);
    setAccounts(data.accounts);
    setProviders(data.providers);
  }
  useEffect(() => {
    refresh().catch((e) => setMessage(e.message));
  }, [orgId, projectId]);
  async function act(action: () => Promise<void>) {
    setBusy(true);
    setMessage("");
    try {
      await action();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Connection failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="card">
      <span className="eyebrow">CONNECTED SOCIAL ACCOUNTS</span>
      <h2>Give your growth employee account access.</h2>
      <p>
        Connect an Instagram Business or Creator account, or Facebook Pages.
        Access currently reads your profile and recent posts to inform growth
        workflows. Publishing and messaging are separate integrations.
      </p>
      {message && <p role="status">{message}</p>}
      {providers.map((p) => (
        <div key={p.provider}>
          <h3>{p.provider === "instagram" ? "Instagram" : "Facebook Pages"}</h3>
          <p>
            {p.configured
              ? "Ready to connect"
              : "Requires administrator setup of the Meta app and token encryption."}
          </p>
          <p>Requested permissions: {p.requested_permissions.join(", ")}</p>
          {isOwner && (
            <button
              disabled={busy || !p.configured}
              onClick={() =>
                act(async () => {
                  const result = await api(
                    `/v1/projects/${projectId}/social/${p.provider}/connect`,
                    orgId,
                    {},
                  );
                  window.location.assign(result.authorization_url);
                })
              }
            >
              Connect {p.provider}
            </button>
          )}
        </div>
      ))}
      <button
        className="secondary"
        disabled={busy}
        onClick={() => act(refresh)}
      >
        Refresh connected accounts
      </button>
      {accounts.map((a) => (
        <article key={a.id}>
          <h3>
            {a.name} · {a.provider}
          </h3>
          <p>Status: {a.status}</p>
          <p>Granted permissions: {a.permissions.join(", ") || "None"}</p>
          {a.snapshot.observed_at && (
            <p>
              Last retrieved:{" "}
              {new Date(a.snapshot.observed_at * 1000).toLocaleString()} ·
              Followers: {a.snapshot.profile?.followers_count ?? "Unavailable"}{" "}
              · Recent posts: {a.snapshot.posts?.length ?? 0}
            </p>
          )}
          {isOwner && a.status !== "disconnected" && (
            <>
              <button
                disabled={busy || a.status === "expired"}
                onClick={() =>
                  act(async () => {
                    await api(`/v1/social/accounts/${a.id}/sync`, orgId, {});
                    await refresh();
                    setMessage(
                      "Account data retrieved. New growth workflows can use this snapshot.",
                    );
                  })
                }
              >
                Retrieve account data
              </button>
              <button
                className="secondary"
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    await api(
                      `/v1/social/accounts/${a.id}/disconnect`,
                      orgId,
                      {},
                    );
                    await refresh();
                  })
                }
              >
                Disconnect
              </button>
            </>
          )}
        </article>
      ))}
      <p>
        Owners control access. Disconnect removes the stored token and current
        account snapshot. You can also revoke FounderOS in your social account
        settings. Previously created workflow snapshots remain in campaign
        history.
      </p>
    </section>
  );
}
