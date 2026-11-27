# Internship tracker

Save a posting link, pull the role details off the page, and move each application through Applied, In the process, Interview, Offered, and Rejected.

The React app runs on port 3000. The Flask API runs on port 5001 and uses the Supabase project in the root `.env` file. That file stays on your machine and is not part of this repo.

```bash
cd frontend
npm install
npm start
```

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python backend.py
```
