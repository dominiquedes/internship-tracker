import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import STAGES from "./stages";
import StatusBurst, { effectFor } from "./statusBurst";

const API_URL = "http://127.0.0.1:5001";

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
            ? `${user.name}, move each posting as the application moves forward.`
            : "Move each posting as the application moves forward."}
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
          <div className="board">
            {STAGES.map((stage) => {
              const items = internships.filter((internship) => internship.status === stage.id);
              return (
                <section className={`stage stage-${stage.id}`} key={stage.id}>
                  <h2 className="stage-title">
                    {stage.label}
                    <span>{items.length}</span>
                  </h2>
                  {items.length === 0 ? (
                    <p className="note">None here.</p>
                  ) : (
                    <div className="list">
                      {items.map((internship) => (
                        <article
                          className={`internship${internship.status === "rejected" ? " is-rejected" : ""}`}
                          key={internship.id}
                        >
                          <a href={internship.url} target="_blank" rel="noreferrer">
                            <h3>{internship.title || "Untitled posting"}</h3>
                            <p className="meta">
                              {[internship.company, internship.location].filter(Boolean).join(" · ") ||
                                internship.url}
                            </p>
                            {internship.summary ? <p className="summary">{internship.summary}</p> : null}
                          </a>
                          <label className="status">
                            Status
                            <select
                              value={internship.status}
                              onChange={(event) => changeStatus(internship, event.target.value)}
                            >
                              {STAGES.map((option) => (
                                <option key={option.id} value={option.id}>
                                  {option.label}
                                </option>
                              ))}
                            </select>
                          </label>
                        </article>
                      ))}
                    </div>
                  )}
                </section>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}

export default IsUserHome;
