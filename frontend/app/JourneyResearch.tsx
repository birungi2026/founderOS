type Finding = {
  company?: string;
  name?: string;
  angle?: string;
  observation?: string;
  audience_fit?: string;
  uncertainty?: string;
  qualification?: string;
  unknowns?: string;
  ranking_summary?: string;
  platform?: string;
  experiment?: string;
  success_metric?: string;
  source_id?: string;
  evidence_ids?: string[];
};
type Report = {
  company_understanding?: string;
  differentiation_hypothesis?: string;
  opportunities?: Finding[];
  competitor_observations?: Finding[];
  prospects?: Finding[];
  platform_strategies?: Finding[];
};
export default function JourneyResearch({
  artifact,
  sources,
}: {
  artifact: Record<string, unknown>;
  sources: { id: string; title: string; url: string }[];
}) {
  const report = artifact as Report;
  return (
    <div className="journey-research">
      {report.company_understanding && (
        <>
          <h4>What Rymu understands about your business</h4>
          <p>{report.company_understanding}</p>
        </>
      )}
      {report.differentiation_hypothesis && (
        <>
          <h4>A possible reason to choose you</h4>
          <p>{report.differentiation_hypothesis}</p>
        </>
      )}
      {(
        [
          ["Content opportunities", report.opportunities],
          ["Competitor observations", report.competitor_observations],
          ["Potential customer conversations", report.prospects],
          ["Ideas to test on each platform", report.platform_strategies],
        ] as [string, Finding[] | undefined][]
      ).map(
        ([title, findings]) =>
          !!findings?.length && (
            <section key={title}>
              <h4>{title}</h4>
              {findings.map((finding, index) => (
                <article key={index}>
                  <strong>
                    {finding.angle ||
                      finding.company ||
                      finding.name ||
                      finding.platform}
                  </strong>
                  {finding.observation && <p>{finding.observation}</p>}
                  {finding.audience_fit && (
                    <p>Why it fits: {finding.audience_fit}</p>
                  )}
                  {finding.qualification && (
                    <p>Why they may be relevant: {finding.qualification}</p>
                  )}
                  {finding.ranking_summary && <p>{finding.ranking_summary}</p>}
                  {finding.experiment && <p>Try this: {finding.experiment}</p>}
                  {finding.success_metric && (
                    <p>What to measure: {finding.success_metric}</p>
                  )}
                  {(finding.uncertainty || finding.unknowns) && (
                    <p>
                      Still needs checking:{" "}
                      {finding.uncertainty || finding.unknowns}
                    </p>
                  )}
                  {sources
                    .filter((source) =>
                      [
                        ...(finding.evidence_ids || []),
                        finding.source_id,
                      ].includes(source.id),
                    )
                    .map((source) => (
                      <p key={source.id}>
                        <a href={source.url} target="_blank" rel="noreferrer">
                          Source: {source.title}
                        </a>
                      </p>
                    ))}
                </article>
              ))}
            </section>
          ),
      )}
      <p>
        Search results are evidence to assess, not independently verified facts.
        Correct your brand or company profile and start fresh research if
        important facts are wrong.
      </p>
    </div>
  );
}
