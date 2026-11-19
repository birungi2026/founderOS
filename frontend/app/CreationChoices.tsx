import Icon from "./Icon";
export default function CreationChoices({
  onChoose,
  compact = false,
}: {
  onChoose: (tab: string) => void;
  compact?: boolean;
}) {
  return (
    <section
      className={`creation-section ${compact ? "compact" : ""}`}
      aria-label="Create with Rymu"
    >
      <div className="studio-section-heading">
        <div>
          <span className="eyebrow">A LITTLE INSPIRATION. A LOT OF YOU.</span>
          <h2>What will you create next?</h2>
        </div>
        <span className="soft-label">Made for your brand</span>
      </div>
      <div className="creation-grid">
        <button
          className="creation-card video-choice"
          onClick={() => onChoose("video")}
        >
          <span className="format-art" aria-hidden="true">
            <span className="format-phone">
              <span className="portrait-shape" />
              <span className="caption-lines" />
              <span className="play-glyph">▶</span>
            </span>
            <span className="art-label">YOUR VOICE. YOUR STORY.</span>
          </span>
          <span className="creation-copy">
            <span className="format-kind">VIDEO SCRIPT</span>
            <strong>Turn your ideas into video</strong>
            <span>Hooks, scenes and captions for your next short.</span>
            <span className="choice-link">
              Open video studio <Icon name="arrow" size={16} />
            </span>
          </span>
        </button>
        <button
          className="creation-card post-choice"
          onClick={() => onChoose("growth")}
        >
          <span className="format-art" aria-hidden="true">
            <span className="poster-sheet">
              <span>
                Small ideas.
                <br />
                Real impact.
              </span>
              <i />
              <i />
            </span>
            <span className="art-label">SOMETHING WORTH SHARING.</span>
          </span>
          <span className="creation-copy">
            <span className="format-kind">SOCIAL POSTS</span>
            <strong>Show up with something useful</strong>
            <span>On-brand drafts for the people you want to reach.</span>
            <span className="choice-link">
              Open content calendar <Icon name="arrow" size={16} />
            </span>
          </span>
        </button>
        <button
          className="creation-card research-choice"
          onClick={() => onChoose("research")}
        >
          <span className="format-art" aria-hidden="true">
            <span className="radar-art">
              <span />
              <span />
              <span />
              <i />
            </span>
            <span className="art-label">FIND YOUR NEXT GOOD IDEA.</span>
          </span>
          <span className="creation-copy">
            <span className="format-kind">RESEARCH & IDEAS</span>
            <strong>Find your audience’s next question</strong>
            <span>Explore evidence, competitors and fresh angles.</span>
            <span className="choice-link">
              Open research radar <Icon name="arrow" size={16} />
            </span>
          </span>
        </button>
      </div>
      {!compact && (
        <p className="creation-hint">
          These are starting points, not generated content. Your employee uses
          your approved brand and research. Video output is a script until
          rendering is connected.
        </p>
      )}
    </section>
  );
}
