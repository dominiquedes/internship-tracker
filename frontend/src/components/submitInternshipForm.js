import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import STAGES from "./stages";

const API_URL = "http://127.0.0.1:5001";

function readToken() {
  try {
    return JSON.parse(localStorage.getItem("internship-session"))?.access_token || "";
  } catch (error) {
    return "";
  }
}

function SubmitInternshipForm() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState("applied");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!readToken()) {
      navigate("/login");
    }
  }, [navigate]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    const token = readToken();
    if (!token) {
      navigate("/login");
      return;
    }

    const link = url.trim();
    if (!link) {
      setError("Paste a posting link.");
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch(`${API_URL}/internships`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ url: link, status }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data.error || "Could not save that link.");
        return;
      }
      navigate("/", { state: { arrived: status } });
    } catch (requestError) {
      setError("Could not reach the server.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="screen">
      <section className="panel">
        <Link className="brand" to="/">
          <span className="mark" aria-hidden="true" />
          Internship tracker
        </Link>
        <div className="card">
          <h1>Add a posting</h1>
          <p className="lede">Paste the link and mark where this application stands.</p>
          <form onSubmit={handleSubmit}>
            <label>
              Posting link
              <input
                type="url"
                inputMode="url"
                placeholder="https://"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                required
              />
            </label>
            <label>
              Status
              <select value={status} onChange={(event) => setStatus(event.target.value)}>
                {STAGES.map((stage) => (
                  <option key={stage.id} value={stage.id}>
                    {stage.label}
                  </option>
                ))}
              </select>
            </label>
            {error ? <p className="error">{error}</p> : null}
            <button type="submit" disabled={submitting}>
              {submitting ? "Reading the page..." : "Save internship"}
            </button>
          </form>
          <p className="footnote">
            <Link to="/">Cancel</Link>
          </p>
        </div>
      </section>
    </main>
  );
}

export default SubmitInternshipForm;
