
import { useRef, useState, type Dispatch, type SetStateAction } from "react";
import "./App.css";
import CropEditor from "./components/CropEditor";

const API_URL =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8017";

type UploadedImage = {
  name: string;
  size: number;
  original: File;
  preview: string;
};

type UploadCardProps = {
  type: "source" | "target";
  file: UploadedImage | null;
  onFileChange: (file: File) => void;
  onRemove: () => void;
};

type MatchResult = {
  id: string;
  name: string;
  score: number;
};

type MatchSet = {
  total: number;
  results: MatchResult[];
};

type AnalysisResult = {
  comparison: {
    visual_similarity: number;
    similarity_level: string;
  };
  image_a_matches: MatchSet;
  image_b_matches: MatchSet;
  detail?: string;
};

function BrandLogo() {
  return (
    <div className="brand">
      <div className="brand-symbol">A</div>
      <div className="brand-copy">
        <strong>APEXIVE<span>AI</span></strong>
        <small>BRAND INTELLIGENCE</small>
      </div>
    </div>
  );
}

function UploadCard({ type, file, onFileChange, onRemove }: UploadCardProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);

  const isSource = type === "source";

  function validateFile(selected: File | undefined) {
    if (!selected) return;

    const allowed = [
      "image/png",
      "image/jpeg",
      "image/webp",
    ];

    if (!allowed.includes(selected.type)) {
      alert("Please upload a PNG, JPG or WEBP image.");
      return;
    }

    if (selected.size > 15 * 1024 * 1024) {
      alert("Maximum image size is 15 MB.");
      return;
    }

    setPendingFile(selected);
  }

  return (
    <section
      className={`upload-card ${dragging ? "is-dragging" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        validateFile(event.dataTransfer.files[0]);
      }}
    >
      <div className="upload-card-header">
        <div className="upload-title">
          <span className={`mark-number ${isSource ? "blue" : "violet"}`}>
            {isSource ? "01" : "02"}
          </span>
          <div>
            <span className="field-label">
              {isSource ? "ORIGINAL TRADEMARK" : "COMPARISON TRADEMARK"}
            </span>
            <h3>{isSource ? "Source Mark" : "Target Mark"}</h3>
          </div>
        </div>

        {file && (
          <button
            className="icon-button"
            onClick={onRemove}
            aria-label="Remove image"
          >
            ×
          </button>
        )}
      </div>

      {file ? (
        <div className="preview-container">
          <div className="preview-image">
            <img src={file.preview} alt="Trademark preview" />
          </div>
          <div className="file-details">
            <div className="file-icon">
              <span>IMG</span>
            </div>
            <div className="file-text">
              <strong>{file.name}</strong>
              <small>{(file.size / 1024).toFixed(1)} KB</small>
            </div>
            <span className="file-check">✓</span>
          </div>
          <button
            className="replace-link"
            onClick={() => inputRef.current?.click()}
          >
            Replace image
          </button>
        </div>
      ) : (
        <div
          className="drop-area"
          onClick={() => inputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              inputRef.current?.click();
            }
          }}
        >
          <div className="upload-visual">
            <div className="upload-visual-inner">
              <svg
                width="28"
                height="28"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 16V4m-5 5 5-5 5 5" />
                <path d="M20 16.5v2A1.5 1.5 0 0 1 18.5 20h-13A1.5 1.5 0 0 1 4 18.5v-2" />
              </svg>
            </div>
          </div>

          <h4>Drop your image here</h4>
          <p>or <span>browse files</span> from your device</p>
          <small>PNG, JPG or WEBP · Max 15 MB</small>
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        hidden
        onChange={(event) => {
          const selected = event.target.files?.[0];
          validateFile(selected);
          event.target.value = "";
        }}
      />

      <div className="upload-card-footer">
        <span>
          <span className="secure-icon">◇</span>
          Secure image processing
        </span>
        <span>{file ? "Uploaded" : "Awaiting image"}</span>
      </div>

      {pendingFile && (
        <CropEditor
          file={pendingFile}
          onCancel={() => setPendingFile(null)}
          onApply={(croppedFile) => {
            onFileChange(croppedFile);
            setPendingFile(null);
          }}
        />
      )}
    </section>
  );
}

function ResultPanel({
  result,
  onReset,
}: {
  result: AnalysisResult;
  onReset: () => void;
}) {
  const comparison = result.comparison || {};
  const matchGroups: { title: string; data: MatchSet }[] = [
    { title: "Source Mark Matches", data: result.image_a_matches },
    { title: "Target Mark Matches", data: result.image_b_matches },
  ];

  return (
    <section className="result-panel">
      <div className="result-heading">
        <div>
          <span className="field-label">ANALYSIS COMPLETE</span>
          <h2>Visual Comparison Results</h2>
        </div>
        <span className="result-status">Completed</span>
      </div>

      <div className="score-card">
        <span className="field-label">VISUAL SIMILARITY SCORE</span>
        <div className="score-number">
          {comparison.visual_similarity ?? 0}
          <small>%</small>
        </div>
        <p>
          {comparison.similarity_level || "Analysis completed"}
        </p>
        <div className="score-track">
          <div
            className="score-fill"
            style={{
              width: `${Math.min(
                100,
                Math.max(0, comparison.visual_similarity || 0)
              )}%`,
            }}
          />
        </div>
      </div>

      <div className="match-columns">
        {matchGroups.map(({ title, data }) => (
          <div className="match-card" key={title}>
            <h3>{title}</h3>
            <strong>{data?.total ?? 0}</strong>
            <small>Database matches returned</small>
            <div className="match-list">
              {(data?.results || []).slice(0, 5).map((item) => (
                <div className="match-row" key={item.id}>
                  <span>{item.name}</span>
                  <b>{item.score}%</b>
                </div>
              ))}
              {!data?.results?.length && (
                <p className="empty-matches">
                  No indexed trademark records found.
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      <p className="legal-notice">
        AI visual similarity is a screening signal, not a legal
        determination of trademark infringement or registrability.
      </p>

      <button className="secondary-button" onClick={onReset}>
        Start new comparison
      </button>
    </section>
  );
}

export default function App() {
  const [source, setSource] = useState<UploadedImage | null>(null);
  const [target, setTarget] = useState<UploadedImage | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState("");

  const count = Number(Boolean(source)) + Number(Boolean(target));

  function updateFile(
    setter: Dispatch<SetStateAction<UploadedImage | null>>,
    file: File
  ) {
    setter({
      name: file.name,
      size: file.size,
      original: file,
      preview: URL.createObjectURL(file),
    });
    setError("");
  }

  function resetComparison() {
    if (source?.preview) URL.revokeObjectURL(source.preview);
    if (target?.preview) URL.revokeObjectURL(target.preview);

    setSource(null);
    setTarget(null);
    setResult(null);
    setError("");
  }

  async function runAnalysis() {
    if (!source || !target || loading) return;

    setLoading(true);
    setError("");

    try {
      const formData = new FormData();

      formData.append("image_a", source.original);
      formData.append("image_b", target.original);

      const response = await fetch(
        `${API_URL}/api/v1/compare-logos`,
        {
          method: "POST",
          body: formData,
        }
      );

      const data: AnalysisResult = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Trademark analysis failed."
        );
      }

      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to connect to the AI engine."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <div className="header-inner">
          <BrandLogo />

          <div className="header-center">
            <span className="platform-indicator">
              <span className="online-dot" />
              INTELLIGENCE PLATFORM
            </span>
          </div>

          <div className="header-right">
            <span className="edition-label">GLOBAL EDITION</span>
            <div className="profile-avatar">BH</div>
          </div>
        </div>
      </header>

      <main className="main-container">
        <section className="hero-section">
          <div className="hero-copy">
            <span className="hero-kicker">
              NEXT-GENERATION TRADEMARK INTELLIGENCE
            </span>
            <h1>
              Discover similarity.
              <br />
              <span>Protect originality.</span>
            </h1>
            <p>
              Intelligent visual trademark analysis designed
              for a world without borders.
            </p>
          </div>

          <div className="hero-decoration">
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <div className="orbit-core">
              <span>A</span>
              <small>AI</small>
            </div>
            <div className="orbit-tag tag-one">VISION AI</div>
            <div className="orbit-tag tag-two">GLOBAL</div>
          </div>
        </section>

        <section className="workspace">
          <div className="workspace-heading">
            <div>
              <div className="section-overline">
                <span className="section-line" />
                YOUR WORKSPACE
              </div>
              <h2>Visual Trademark Search</h2>
              <p>
                Compare two marks and identify potential visual similarities.
              </p>
            </div>

            <div className="step-indicator">
              <span>STEP 01</span>
              <div className="step-line" />
              <span className="muted-step">IMAGE UPLOAD</span>
            </div>
          </div>

          {!result ? (
            <>
              <div className="upload-grid">
                <UploadCard
                  type="source"
                  file={source}
                  onFileChange={(file) =>
                    updateFile(setSource, file)
                  }
                  onRemove={() => setSource(null)}
                />

                <div className="versus-column">
                  <div className="versus-circle">VS</div>
                  <span>COMPARE</span>
                </div>

                <UploadCard
                  type="target"
                  file={target}
                  onFileChange={(file) =>
                    updateFile(setTarget, file)
                  }
                  onRemove={() => setTarget(null)}
                />
              </div>

              <div className="workspace-bottom">
                <div className="upload-progress">
                  <div className="progress-top">
                    <span>Upload progress</span>
                    <strong>{count} / 2</strong>
                  </div>
                  <div className="progress-track">
                    <div
                      className="progress-value"
                      style={{ width: `${count * 50}%` }}
                    />
                  </div>
                </div>

                <button
                  className="analyze-button"
                  disabled={count !== 2 || loading}
                  onClick={runAnalysis}
                >
                  {loading ? (
                    <>
                      <span className="loading-spinner" />
                      Analyzing trademarks...
                    </>
                  ) : (
                    <>
                      Run AI Analysis
                      <span className="button-arrow">→</span>
                    </>
                  )}
                </button>
              </div>

              {error && (
                <div className="error-message">
                  <strong>Analysis error</strong>
                  <span>{error}</span>
                </div>
              )}
            </>
          ) : (
            <ResultPanel result={result} onReset={resetComparison} />
          )}
        </section>

        <section className="capabilities">
          <div className="capability-heading">
            <span className="section-overline">
              INTELLIGENCE CAPABILITIES
            </span>
            <span className="capability-subtitle">
              Designed for global brand professionals
            </span>
          </div>

          <div className="capability-grid">
            <article className="capability-card">
              <div className="capability-icon blue-icon">
                <span>◎</span>
              </div>
              <h3>Visual Intelligence</h3>
              <p>
                AI-powered visual feature extraction and similarity analysis.
              </p>
            </article>

            <article className="capability-card">
              <div className="capability-icon purple-icon">
                <span>⌘</span>
              </div>
              <h3>Global Search</h3>
              <p>
                Search across indexed trademark records and jurisdictions.
              </p>
            </article>

            <article className="capability-card">
              <div className="capability-icon green-icon">
                <span>◇</span>
              </div>
              <h3>Risk Intelligence</h3>
              <p>
                Evidence-based screening to support brand protection decisions.
              </p>
            </article>
          </div>
        </section>

        <footer className="site-footer">
          <BrandLogo />
          <span>
            © 2026 APEXIVEAI. ALL RIGHTS RESERVED.
          </span>
          <span>BUILT FOR A GLOBAL MARKET.</span>
        </footer>
      </main>
    </div>
  );
}
