"use client";
import { useState } from "react";
import { api } from "./api";
export default function ConversionTools({
  orgId,
  projectId,
  isOwner,
}: {
  orgId: string;
  projectId: string;
  isOwner: boolean;
}) {
  const [source, setSource] = useState("instagram"),
    [campaign, setCampaign] = useState("weekly_content"),
    [url, setUrl] = useState(""),
    [key, setKey] = useState(""),
    [error, setError] = useState("");
  async function link() {
    setError("");
    try {
      setUrl(
        (
          await api(`/v1/projects/${projectId}/campaign-link`, orgId, {
            source,
            campaign,
          })
        ).url,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Link failed");
    }
  }
  return (
    <details className="panel">
      <summary>Track website referrals and conversions</summary>
      <p>
        Create a campaign link for your approved website. Your website analytics
        measures visits; a server integration can report leads and paid
        customers.
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <label>
        Referral channel
        <select value={source} onChange={(e) => setSource(e.target.value)}>
          {["instagram", "facebook", "linkedin", "tiktok"].map((v) => (
            <option key={v}>{v}</option>
          ))}
        </select>
      </label>
      <label>
        Campaign name
        <input
          pattern="[a-zA-Z0-9_-]+"
          maxLength={80}
          value={campaign}
          onChange={(e) => setCampaign(e.target.value)}
        />
      </label>
      <button className="secondary" onClick={() => void link()}>
        Create tracking link
      </button>
      {url && (
        <label>
          Campaign link
          <input readOnly value={url} />
        </label>
      )}
      {isOwner && (
        <details>
          <summary>Server conversion integration</summary>
          <p>
            Keys belong on your server, never in a browser or social post.
            Creating a key invalidates the previous one.
          </p>
          <button
            className="secondary"
            onClick={async () => {
              setError("");
              try {
                setKey(
                  (
                    await api(
                      `/v1/projects/${projectId}/conversion-key`,
                      orgId,
                      {},
                    )
                  ).key,
                );
              } catch (e) {
                setError(
                  e instanceof Error ? e.message : "Key creation failed",
                );
              }
            }}
          >
            Create or rotate conversion key
          </button>
          {key && (
            <label>
              Copy this key once
              <input
                readOnly
                type="password"
                value={key}
                autoComplete="off"
                onFocus={(e) => e.currentTarget.select()}
              />
              <small>This key disappears when you leave this screen.</small>
            </label>
          )}
          <p>
            POST lead, signup or paying_customer events to /v1/conversions with
            a stable customer/event ID. See the deployment guide. Reports are
            server-reported, not independently payment-verified.
          </p>
        </details>
      )}
    </details>
  );
}
