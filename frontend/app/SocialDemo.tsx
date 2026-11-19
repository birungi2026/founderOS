"use client";
import { useState } from "react";

type DemoAccount = { provider: string; retrieved: boolean };
export default function SocialDemo() {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState("");
  const [accounts, setAccounts] = useState<DemoAccount[]>([]);
  const [notice, setNotice] = useState("");
  const label = (provider: string) =>
    ({
      instagram: "Instagram",
      facebook: "Facebook Pages",
      linkedin: "LinkedIn",
      tiktok: "TikTok",
    })[provider as "instagram" | "facebook" | "linkedin" | "tiktok"];
  return (
    <div className="social-demo">
      <button
        type="button"
        className="secondary"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        {" "}
        {open ? "Hide demo connection flow" : "Try demo connection flow"}
      </button>
      {open && (
        <section aria-label="Social connection demo">
          <h3>Demo mode · sample data only</h3>
          <p>
            Preview connecting, granting access, retrieving posts and
            disconnecting. No provider credentials are needed. This preview
            never contacts social platforms, publishes content or adds sample
            metrics to your real growth workflows.
          </p>
          {notice && <p role="status">{notice}</p>}
          {["instagram", "facebook", "linkedin", "tiktok"].map((provider) => (
            <button
              type="button"
              key={provider}
              disabled={accounts.some((a) => a.provider === provider)}
              onClick={() => {
                setPending(provider);
                setNotice("");
              }}
            >
              Preview {label(provider)} connection
            </button>
          ))}
          {pending && (
            <section
              role="dialog"
              aria-modal="false"
              aria-label="Demo account authorization"
            >
              <h3>Simulated {label(pending)} authorization</h3>
              <p>
                In the live flow, the platform opens its own login and
                permission screen. This is a Rymu preview, not a Meta login
                page.
              </p>
              <p>
                Sample account:{" "}
                {pending === "instagram"
                  ? "@demo_founder"
                  : "Demo Founder Company"}
              </p>
              <ul>
                <li>
                  {pending === "linkedin"
                    ? "Read basic profile; post analytics requires additional approval"
                    : "Read profile and available account data"}
                </li>
                <li>
                  {pending === "linkedin"
                    ? "No post or follower analytics with basic profile access"
                    : "Read recent public content"}
                </li>
                <li>No publishing or messaging access</li>
              </ul>
              <button
                type="button"
                onClick={() => {
                  setAccounts([
                    ...accounts,
                    { provider: pending, retrieved: false },
                  ]);
                  setPending("");
                  setNotice(
                    "Demo account connected. Retrieve sample data to continue.",
                  );
                }}
              >
                Approve demo access
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  setPending("");
                  setNotice("Demo connection cancelled. No access granted.");
                }}
              >
                Cancel demo connection
              </button>
            </section>
          )}
          {accounts.map((account) => (
            <article
              key={account.provider}
              aria-label={`${label(account.provider)} demo account`}
            >
              <h3>
                {label(account.provider)} ·{" "}
                {account.provider === "instagram"
                  ? "@demo_founder"
                  : "Demo Founder Company"}
              </h3>
              <p>Status: Demo connected · read-only sample access</p>
              <button
                type="button"
                onClick={() => {
                  setAccounts(
                    accounts.map((a) =>
                      a.provider === account.provider
                        ? { ...a, retrieved: true }
                        : a,
                    ),
                  );
                  setNotice(
                    "Sample data retrieved. These numbers are fictional and excluded from real analytics and agent context.",
                  );
                }}
              >
                Retrieve {label(account.provider)} sample data
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  setAccounts(
                    accounts.filter((a) => a.provider !== account.provider),
                  );
                  setNotice(
                    "Demo account disconnected. Its sample data was removed.",
                  );
                }}
              >
                Disconnect {label(account.provider)} demo
              </button>
              {account.retrieved && (
                <div>
                  <p>
                    <strong>Sample followers:</strong>{" "}
                    {account.provider === "linkedin" ||
                    account.provider === "tiktok"
                      ? "Unavailable with requested scopes"
                      : "1,240"}{" "}
                    · <strong>Sample recent posts:</strong>{" "}
                    {account.provider === "linkedin" ? 0 : 2}
                  </p>
                  {account.provider !== "linkedin" && (
                    <>
                      <h4>Example posts</h4>
                      <p>
                        “Why I started this company: the problem our first
                        customers helped us understand.”
                      </p>
                      <p>
                        “Three lessons from building our first product
                        prototype.”
                      </p>
                    </>
                  )}
                  <p>
                    <strong>Next in the live workflow:</strong> retrieved
                    account data informs research and content drafts. Founder
                    research confirmation and publishing approval still apply.
                  </p>
                </div>
              )}
            </article>
          ))}
          <p>
            Preview state resets when you reload or switch projects. Real
            connections are managed separately below.
          </p>
        </section>
      )}
    </div>
  );
}
