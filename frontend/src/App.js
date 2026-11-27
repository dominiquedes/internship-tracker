import { useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Auth from "./components/Auth";
import CreateUser from "./components/createUser";
import GuestHome from "./components/guestHome";
import IsUserHome from "./components/isUserHome";
import SubmitInternshipForm from "./components/submitInternshipForm";
import "./App.css";

function readUser() {
  try {
    return JSON.parse(localStorage.getItem("internship-user"));
  } catch (error) {
    return null;
  }
}

function Home() {
  const [user, setUser] = useState(readUser);
  if (!user) {
    return <GuestHome />;
  }
  return <IsUserHome onLogout={() => setUser(null)} />;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Auth />} />
        <Route path="/signup" element={<CreateUser />} />
        <Route path="/submit" element={<SubmitInternshipForm />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
