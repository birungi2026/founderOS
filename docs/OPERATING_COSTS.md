# FounderOS launch economics — planning estimate

Reviewed 2026-11-19. USD before tax. This is a planning model for the completed product, not provider quotes for a production SaaS agreement or implemented subscription entitlements. Interview transcription, live avatar rendering, automatic publishing and payment billing retain their current implementation limits.

## Initial monthly platform footprint

| Item | Published rate / planning allowance |
| --- | ---: |
| DigitalOcean Basic 4 GiB / 2 vCPU Droplet | $24 |
| Managed PostgreSQL starting node | $15.15 |
| Spaces base storage/transfer package | $5 |
| Weekly Droplet backups (20% of $24) | $4.80 |
| Email and monitoring allowance | $15–25 estimate |
| Domain renewal spread over a year | $2 estimate; actual Namecheap domain price varies |
| Capacity/contingency allowance | $15–40 estimate |

Budget about **$80–120/month** initially, with a larger app server if measurements justify it. A starting footprint is not a throughput or availability guarantee: this is not a high-availability deployment. Database backup/restore testing and deployment operations still need implementation. DigitalOcean hosts the frontend as well; separate Namecheap website hosting is unnecessary for this design. Domain renewal is annual, even when budgeted monthly.

Official rates: [Droplets and backups](https://www.digitalocean.com/pricing/droplets), [PostgreSQL](https://www.digitalocean.com/pricing/managed-databases), [Spaces](https://www.digitalocean.com/pricing/spaces-object-storage).

## Variable costs

Reserve **$10 per active workspace/month** for efficient text models, search and brief transcription as an initial allowance, then replace this assumption with measured usage. For example, 30 daily research runs × maximum 14 searches × $5/1,000 searches = $2.10 for search before account-wide promotional credits. Credits are not per customer. Model/context choice, retries and extra assignments change costs.

Reference rates: [Brave Search](https://brave.com/search/api/) $5/1,000 requests; [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini) $0.40/M input tokens and $1.60/M output tokens; [transcription](https://developers.openai.com/api/docs/pricing) mini transcription estimated at $0.003/minute. Transcription does not by itself provide facial-motion or full voice/accent analysis.

HeyGen API is pay-as-you-go and separate from its consumer creator plans:

| Digital Twin engine | Raw generated minute | 15 raw minutes | 15 minutes with 25% cost buffer |
| --- | ---: | ---: | ---: |
| Avatar III | $0.60 | $9.00 | $11.25 |
| Avatar IV | $4.83 | $72.45 | $90.56 |
| Avatar V | $7.20 | $108.00 | $135.00 |

Digital Twin creation is listed at $2.13/call, a separate onboarding cost. Choose the engine after testing the founder's sample; lower price does not establish that it meets the required quality. Pre-recorded consent submission through the API is documented as Enterprise-only. The Enterprise/multi-tenant onboarding agreement, any minimum commitment, extra editing models, translation, paid ads and other provider fees are not included in this model. Obtain the SaaS enrollment quote before committing to final pricing.

Sources: [HeyGen API rate card](https://help.heygen.com/en/articles/10060327-heygen-api-pricing-credits-explained), [consent/API requirements](https://help.heygen.com/en/articles/12092609-recording-your-consent-video).

## Proposed monthly subscriptions

| Plan | Monthly fee | Proposed included scope |
| --- | ---: | --- |
| Core | $49 | One workspace, research, written drafts, approvals and goal tracking; no rendered avatar video |
| Video Growth | $179 | Core plus 5 generated Avatar IV minutes |
| Video Pro | $399 | Core plus 15 generated Avatar IV minutes |

Generated minutes, including user-requested new renders/revisions, consume the allowance. A 30-second clip uses half a minute; video counts are approximate and depend on length and revisions. Publish a transparent credit/refund policy for provider failures. Extra Avatar IV minutes could be $25/minute; Avatar V could be $35/minute, subject to contract and quality validation. Do not sell unlimited rendering or guarantee reach/customers. Advertising spend is separately funded by each customer.

These are proposed prices for a completed workflow. Start the current product with an explicitly limited beta; do not charge for real cloning/publishing while those flows are demos. Validate willingness to pay and actual render acceptance/support costs with paying pilot users before an annual discount or larger quotas.

## Illustrative economics, all customers on Video Growth

Assumptions: $100 fixed platform budget, $10 AI/search allowance per customer, full 5 Avatar IV minutes/customer, 25% video buffer, 3.5% payment-processing allowance (not a universal processor quote), $5/customer support/refund reserve.

| Paying customers | Revenue | Video cost with buffer | Total modeled cost | Remaining before owner pay, marketing, taxes and any Enterprise contract |
| --- | ---: | ---: | ---: | ---: |
| 10 | $1,790 | $301.88 | $614.53 | $1,175.47 |
| 50 | $8,950 | $1,509.38 | $2,672.63 | $6,277.37 |

These are scenario calculations, not forecasts or net profit. The 50-customer case is roughly 70% contribution after these modeled costs, before omitted operating expenses. The most material unknown is the commercial avatar enrollment/consent arrangement, followed by render retries, support effort, higher-cost models and retention/churn. Track actual cost per workspace and generated minute before expanding allowances.
