import { Link } from "react-router-dom";

function GuestHome() {
  return (
    <main className="screen">
      <section className="hero">
        <Link className="brand" to="/">
          <span className="mark" aria-hidden="true" />
          Internship tracker
        </Link>
        <h1>Every internship, from the first link to the offer.</h1>
        <p className="lede">
          Paste a posting link. We’ll pull out the role, the company, and the details worth keeping.
        </p>
        <div className="actions">
          <Link className="button" to="/login">
            Log in
          </Link>
          <Link className="button secondary" to="/signup">
            Create account
          </Link>
        </div>
      </section>
    </main>
  );
}

export default GuestHome;
