import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import STAGES from "./stages";
import StatusBurst, { effectFor } from "./statusBurst";

const API_URL = process.env.REACT_APP_API_URL || "http://127.0.0.1:5001";

function readUser() {
  try {
    return JSON.parse(localStorage.getItem("internship-user"));
  } catch (error) {
    return null;
  }
}

function readToken() {
  try {
    return JSON.parse(localStorage.getItem("internship-session"))?.access_token || "";
  } catch (error) {
    return "";
  }
}

function payLabel(pay) {
  const text = String(pay || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .join(" · ");
  return text || "—";
}

function SheetCell({ value, display, onSave }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const skipSave = useRef(false);

  function start() {
    skipSave.current = false;
    setDraft(value || "");
    setEditing(true);
  }

  function save() {
    if (skipSave.current) {
      skipSave.current = false;
      return;
    }
    setEditing(false);
    const next = draft.trim();
    if (next === (value || "")) {
      return;
    }
    onSave(next);
  }

  if (editing) {
    return (
      <input
        className="sheet-edit"
        value={draft}
        autoFocus
        aria-label="Edit cell"
        onChange={(event) => setDraft(event.target.value)}
        onBlur={save}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            save();
          }
          if (event.key === "Escape") {
            skipSave.current = true;
            setEditing(false);
          }
        }}
      />
    );
  }

  return (
    <span
      className="sheet-value"
      role="button"
      tabIndex={0}
      title="Double-click to edit"
      onDoubleClick={start}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          start();
        }
      }}
    >
      {display}
    </span>
  );
}

function motionAllowed() {
  return !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function IsUserHome({ onLogout }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState(readUser);
  const [internships, setInternships] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [burst, setBurst] = useState(null);
  const [leaving, setLeaving] = useState(() => new Set());
  const removing = useRef(new Set());

  useEffect(() => {
    const token = readToken();
    if (!token) {
      navigate("/login");
      return;
    }

    fetch(`${API_URL}/internships`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((response) => response.json().then((data) => ({ ok: response.ok, data })))
      .then(({ ok, data }) => {
        if (!ok) {
          setError(data.error || "Could not load your internships.");
          return;
        }
        setInternships(data.internships || []);
      })
      .catch(() => setError("Could not reach the server."))
      .finally(() => setLoading(false));
  }, [navigate]);

  useEffect(() => {
    const arrived = location.state?.arrived;
    if (!arrived) {
      return;
    }
    const kind = effectFor(arrived);
    if (kind && motionAllowed()) {
      setBurst({ kind, token: Date.now() });
    }
    navigate(location.pathname, { replace: true, state: null });
  }, [location.pathname, location.state, navigate]);

  useEffect(() => {
    if (!burst) {
      return undefined;
    }
    const timer = window.setTimeout(() => setBurst(null), 2600);
    return () => window.clearTimeout(timer);
  }, [burst]);

  function logOut() {
    const token = readToken();
    if (token) {
      fetch(`${API_URL}/auth/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {});
    }
    localStorage.removeItem("internship-session");
    localStorage.removeItem("internship-user");
    setUser(null);
    onLogout();
  }

  async function changeStatus(internship, status) {
    const token = readToken();
    const previous = internships;
    setError("");
    setInternships((current) =>
      current.map((item) => (item.id === internship.id ? { ...item, status } : item))
    );

    try {
      const response = await fetch(`${API_URL}/internships/${internship.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ status }),
      });
      const data = await response.json();
      if (!response.ok) {
        setInternships(previous);
        setError(data.error || "Could not update that status.");
        return;
      }
      const kind = effectFor(status);
      if (kind && motionAllowed()) {
        setBurst({ kind, token: Date.now() });
      }
    } catch (requestError) {
      setInternships(previous);
      setError("Could not reach the server.");
    }
  }

  function rowClass(internship) {
    const names = [];
    if (internship.status === "rejected") {
      names.push("is-rejected");
    }
    if (leaving.has(internship.id)) {
      names.push("is-removing");
    }
    return names.join(" ") || undefined;
  }

  async function removeInternship(internship) {
    if (removing.current.has(internship.id)) {
      return;
    }
    removing.current.add(internship.id);
    const token = readToken();
    setError("");
    setLeaving((current) => new Set(current).add(internship.id));
    if (motionAllowed()) {
      await new Promise((resolve) => window.setTimeout(resolve, 480));
    }

    try {
      const response = await fetch(`${API_URL}/internships/${internship.id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      if (!response.ok) {
        removing.current.delete(internship.id);
        setLeaving((current) => {
          const next = new Set(current);
          next.delete(internship.id);
          return next;
        });
        setError(data.error || "Could not remove that company.");
        return;
      }
      setInternships((current) => current.filter((item) => item.id !== internship.id));
      removing.current.delete(internship.id);
      setLeaving((current) => {
        const next = new Set(current);
        next.delete(internship.id);
        return next;
      });
    } catch (requestError) {
      removing.current.delete(internship.id);
      setLeaving((current) => {
        const next = new Set(current);
        next.delete(internship.id);
        return next;
      });
      setError("Could not reach the server.");
    }
  }

  async function changeField(internship, field, value) {
    const token = readToken();
    const previous = internships;
    setError("");
    setInternships((current) =>
      current.map((item) => (item.id === internship.id ? { ...item, [field]: value || null } : item))
    );

    try {
      const response = await fetch(`${API_URL}/internships/${internship.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ [field]: value }),
      });
      const data = await response.json();
      if (!response.ok) {
        setInternships(previous);
        setError(data.error || "Could not update that cell.");
        return;
      }
      if (data.internship) {
        setInternships((current) =>
          current.map((item) => (item.id === internship.id ? data.internship : item))
        );
      }
    } catch (requestError) {
      setInternships(previous);
      setError("Could not reach the server.");
    }
  }

  return (
    <main className="page">
      {burst ? <StatusBurst key={burst.token} kind={burst.kind} /> : null}
      <div className="page-inner">
        <div className="topbar">
          <Link className="brand" to="/">
            <span className="mark" aria-hidden="true" />
            Internship tracker
          </Link>
          <button type="button" className="secondary" onClick={logOut}>
            Log out
          </button>
        </div>
        <h1>Your internships</h1>
        <p className="lede">
          {user?.name
            ? `${user.name}, double-click a cell to correct it.`
            : "Double-click a cell to correct it."}
        </p>
        <Link className="button" to="/submit">
          Add a link
        </Link>
        {error ? <p className="error">{error}</p> : null}
        {loading ? (
          <p className="note">Loading your internships.</p>
        ) : internships.length === 0 ? (
          <p className="note">Nothing saved yet. Add a posting link to start.</p>
        ) : (
          <div className="sheet-wrap">
            <table className="sheet">
              <colgroup>
                <col className="col-title" />
                <col className="col-company" />
                <col className="col-pay" />
                <col className="col-location" />
                <col className="col-status" />
                <col className="col-remove" />
              </colgroup>
              <thead>
                <tr>
                  <th>Job title</th>
                  <th>Company</th>
                  <th>Pay</th>
                  <th>Location</th>
                  <th>Status</th>
                  <th>
                    <span className="sr-only">Remove</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {internships.map((internship) => (
                  <tr className={rowClass(internship)} key={internship.id}>
                    <td>
                      <div className="title-cell">
                        <SheetCell
                          value={internship.title}
                          display={internship.title || "—"}
                          onSave={(value) => changeField(internship, "title", value)}
                        />
                        {internship.url ? (
                          <a
                            className="open-posting"
                            href={internship.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Open
                          </a>
                        ) : null}
                      </div>
                    </td>
                    <td className="company-cell">
                      <SheetCell
                        value={internship.company}
                        display={internship.company || "—"}
                        onSave={(value) => changeField(internship, "company", value)}
                      />
                    </td>
                    <td>
                      <SheetCell
                        value={internship.pay}
                        display={payLabel(internship.pay)}
                        onSave={(value) => changeField(internship, "pay", value)}
                      />
                    </td>
                    <td>
                      <SheetCell
                        value={internship.location}
                        display={internship.location || "—"}
                        onSave={(value) => changeField(internship, "location", value)}
                      />
                    </td>
                    <td>
                      <select
                        aria-label={`Status for ${internship.title || "posting"}`}
                        value={internship.status}
                        onChange={(event) => changeStatus(internship, event.target.value)}
                      >
                        {STAGES.map((option) => (
                          <option key={option.id} value={option.id}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="remove-cell">
                      <button
                        type="button"
                        className="remove-company"
                        aria-label={`Remove ${internship.company || internship.title || "this application"}`}
                        onClick={() => removeInternship(internship)}
                      >
                        <svg viewBox="0 0 24 24" aria-hidden="true">
                          <path d="M9 3h6l1 2h4v2H4V5h4l1-2z" />
                          <path d="M6 9h12l-1 12H7L6 9z" />
                        </svg>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}

export default IsUserHome;
