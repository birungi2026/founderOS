const steps = [
  {
    title: "Get to know you and your business",
    description:
      "Your story, the people you want to reach and what you offer help Rymu understand your brand. An interview can help capture your own words and speaking style.",
    location:
      "Brand profile holds your brand information. Interview tools are in Content studio.",
  },
  {
    title: "Check that Rymu understands you",
    description:
      "You review your brand information before Rymu uses it. This helps your content reflect what you actually do and how you want to sound.",
    location:
      "Your confirmed brand becomes the starting point for your content.",
  },
  {
    title: "Find useful ideas for your audience",
    description:
      "With research connected, Rymu looks for relevant news, audience questions and competitor activity. You can check the sources and confirm important findings before they become content.",
    location: "Research and its sources appear in Content studio.",
  },
  {
    title: "Turn ideas into content",
    description:
      "Rymu uses your confirmed brand and research to prepare a script and caption. With a connected video provider and your permission, it can also make an avatar video for you to review.",
    location: "Drafts and finished videos appear in Content studio.",
  },
  {
    title: "Share content when you are ready",
    description:
      "You choose the finished video, caption, connected Page and posting time. A post is scheduled only after you approve it. The connected video workflow currently supports Facebook Pages.",
    location:
      "Account connections are in Social accounts. Video approval and scheduling are in Content studio.",
  },
  {
    title: "Learn what helps your brand grow",
    description:
      "After a post is published, Rymu checks the available engagement results and uses them to inform future ideas. Likes and comments show interest; paying customers are tracked separately.",
    location:
      "Video engagement appears with your published content. Results tracks your wider progress.",
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
      <p>
        Here is how the steps fit together. This page is a guide — there is
        nothing to fill in or record here.
      </p>
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
      <p>
        Rymu helps you work toward steady growth. Reach, follower counts and
        sales depend on your offer, audience and content; they are not
        guaranteed.
      </p>
    </section>
  );
}
