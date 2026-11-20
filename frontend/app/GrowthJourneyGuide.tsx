const steps = [
  {
    title: "Know your brand",
    description:
      "Share your story, audience and offer. An interview captures your words and style.",
    location: "Brand profile · Interview tools in Content studio",
  },
  {
    title: "Confirm your brand",
    description: "Confirm your brand so content reflects your work and voice.",
    location: "Your approved brand guides your content.",
  },
  {
    title: "Research your audience",
    description:
      "Rymu researches news, audience questions and competitors. Check the sources and confirm findings.",
    location: "Research · Content studio",
  },
  {
    title: "Turn ideas into content",
    description:
      "Rymu creates scripts and captions from approved research. Avatar videos need a connected provider and your consent.",
    location: "Drafts & videos · Content studio",
  },
  {
    title: "Approve and schedule",
    description:
      "Approve your video, caption, Page and time. Video scheduling currently supports Facebook Pages.",
    location: "Connect · Social accounts. Approve & schedule · Content studio.",
  },
  {
    title: "Learn from results",
    description:
      "Rymu uses post engagement to improve future ideas. Customers are tracked separately.",
    location: "Engagement · Published content. Progress · Results.",
  },
];

export default function GrowthJourneyGuide() {
  return (
    <section
      className="panel journey-guide"
      aria-label="How your growth journey works"
    >
      <p className="eyebrow">HOW RYMU HELPS</p>
      <h2>From your story to content that connects.</h2>
      <p>Your path from brand setup to results. No action needed here.</p>
      <ol className="journey-guide-steps">
        {steps.map((step, index) => (
          <li key={step.title}>
            <span className="journey-guide-number" aria-hidden="true">
              {index + 1}
            </span>
            <div>
              <h3>{step.title}</h3>
              <p>{step.description}</p>
              <p className="journey-guide-location">{step.location}</p>
            </div>
          </li>
        ))}
      </ol>
      <p>Growth depends on your offer, audience and content.</p>
    </section>
  );
}
