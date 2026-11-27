import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

const API_URL = "http://127.0.0.1:5001";
const STEPS = ["Name", "Email", "Password"];

function CreateUser() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function validateStep() {
    if (step === 0 && !name.trim()) {
      return "Enter your name.";
    }
    if (step === 1 && !email.includes("@")) {
      return "Enter a valid email.";
    }
    if (step === 2) {
      if (password.length < 6) {
        return "Password must be at least 6 characters.";
      }
      if (password !== confirmPassword) {
        return "Passwords do not match.";
      }
    }
    return "";
  }

  function goNext(event) {
    event.preventDefault();
    const problem = validateStep();
    setError(problem);
    if (!problem) {
      setStep((current) => current + 1);
    }
  }

  async function createAccount(event) {
    event.preventDefault();
    const problem = validateStep();
    setError(problem);
    setMessage("");
    if (problem) {
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch(`${API_URL}/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data.error || "Could not create the account.");
        return;
      }
      if (data.session) {
        localStorage.setItem("internship-session", JSON.stringify(data.session));
        localStorage.setItem("internship-user", JSON.stringify(data.user));
        navigate("/");
        return;
      }
      setMessage("Check your email to confirm the account, then log in.");
    } catch (requestError) {
      setError("Could not reach the server.");
    } finally {
      setSubmitting(false);
    }
  }

  const onLastStep = step === STEPS.length - 1;

  return (
    <main className="screen">
      <section className="panel">
        <Link className="brand" to="/">
          <span className="mark" aria-hidden="true" />
          Internship tracker
        </Link>
        <div className="card">
          <p className="step-label">
            Step {step + 1} of {STEPS.length}
          </p>
          <div className="steps" aria-hidden="true">
            {STEPS.map((label, index) => (
              <span
                key={label}
                className={
                  index === step ? "step is-current" : index < step ? "step is-done" : "step"
                }
              />
            ))}
          </div>
          <h1>{STEPS[step]}</h1>
          <form onSubmit={onLastStep ? createAccount : goNext}>
            {step === 0 ? (
              <label>
                Full name
                <input
                  autoComplete="name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </label>
            ) : null}
            {step === 1 ? (
              <label>
                Email
                <input
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </label>
            ) : null}
            {step === 2 ? (
              <>
                <label>
                  Password
                  <input
                    type="password"
                    autoComplete="new-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                  />
                </label>
                <label>
                  Confirm password
                  <input
                    type="password"
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                  />
                </label>
              </>
            ) : null}
            {error ? <p className="error">{error}</p> : null}
            {message ? <p className="success">{message}</p> : null}
            <div className="row">
              {step > 0 ? (
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    setError("");
                    setStep((current) => current - 1);
                  }}
                >
                  Back
                </button>
              ) : null}
              <button type="submit" disabled={submitting}>
                {onLastStep ? (submitting ? "Creating..." : "Create account") : "Next"}
              </button>
            </div>
          </form>
          <p className="footnote">
            Already have an account? <Link to="/login">Log in</Link>
          </p>
        </div>
      </section>
    </main>
  );
}

export default CreateUser;
