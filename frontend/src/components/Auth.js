import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

const API_URL = process.env.REACT_APP_API_URL || "http://127.0.0.1:5001";

function Auth() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    if (!email.trim() || !password) {
      setError("Enter your email and password.");
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data.error || "Could not log in.");
        return;
      }
      localStorage.setItem("internship-session", JSON.stringify(data.session));
      localStorage.setItem("internship-user", JSON.stringify(data.user));
      navigate("/");
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
          <h1>Welcome back</h1>
          <p className="lede">Log in to pick up your applications.</p>
          <form onSubmit={handleSubmit}>
            <label>
              Email
              <input
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label>
              Password
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            {error ? <p className="error">{error}</p> : null}
            <button type="submit" disabled={submitting}>
              {submitting ? "Logging in..." : "Log in"}
            </button>
          </form>
          <p className="footnote">
            New here? <Link to="/signup">Create an account</Link>
          </p>
        </div>
      </section>
    </main>
  );
}

export default Auth;
