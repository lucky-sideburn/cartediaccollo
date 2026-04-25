# accolli.it

A web app for generating "Carte di Accollo" — humorous certificates that formally commit someone to a task. Built with Flask, MongoDB, and Pillow.

## Features

- Create and share cards that certify a commitment to do something
- User accounts with personal dashboards
- Public dashboard links so contacts can create cards for you
- Card status tracking (open / in progress / done)
- QR code on every card linking back to the shareable page
- Color-coded cards and a lightweight text-only mode

## Stack

- **Backend**: Python 3 / Flask
- **Database**: MongoDB
- **Image generation**: Pillow + qrcode
- **Frontend**: Bootstrap 5, jQuery

## Running locally

### Prerequisites

- Docker and Docker Compose

### 1. Clone the repo

```bash
git clone https://github.com/lucky-sideburn/cartediaccollo.git
cd cartediaccollo
```

### 2. Configure environment variables

Copy the example and edit it:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `BASE_URL` | yes | Public base URL, e.g. `http://localhost:5000` |
| `MONGO_HOST` | yes | MongoDB hostname (use `mongodb` with Docker Compose) |
| `FLASK_SECRET_KEY` | yes | Secret key for Flask sessions — use a long random string in production |
| `ACCOLLI_MAIL_USER` | no | Gmail address for email notifications |
| `ACCOLLI_MAIL_PASSWORD` | no | Gmail app password for email notifications |

### 3. Start with Docker Compose

```bash
docker compose up -d
```

The app is available at <http://localhost:5000>.

Generated card images are stored in `./cards/` and mounted into the container.

### 4. Stop

```bash
docker compose down
```

## Running in development (without Docker)

### Prerequisites

- Python 3.9+
- MongoDB running on `localhost:27017`

### Install dependencies

```bash
pip install -r requirements.txt
```

### Set environment variables and start

```bash
export BASE_URL=http://localhost:5000
export MONGO_HOST=localhost
export FLASK_SECRET_KEY=dev_secret_key

# Optional — leave unset to disable email notifications
# export ACCOLLI_MAIL_USER=your_gmail@gmail.com
# export ACCOLLI_MAIL_PASSWORD=your_app_password

python app.py
```

Alternatively, use the helper script:

```bash
./start_dev.sh
```

## Docker image

A pre-built image is available on Docker Hub:

```bash
docker pull docker.io/luckysideburn/cartediaccollo:latest
```

Run it standalone (requires an external MongoDB):

```bash
docker run -p 5000:5000 \
  -e MONGO_HOST=<mongodb_host> \
  -e BASE_URL=http://localhost:5000 \
  -e FLASK_SECRET_KEY=change_me \
  -v $PWD/cards:/usr/src/app/static/cards \
  docker.io/luckysideburn/cartediaccollo:latest
```

## MongoDB collections

The app uses the `cartediaccollo` database with three collections:

| Collection | Purpose |
|---|---|
| `users` | User accounts (name + bcrypt password hash) |
| `dashboards` | Named dashboards linked to a user |
| `carte` | Card documents (uuid, token, status, task, sender, …) |

## Project structure

```
app.py                  # Flask application
requirements.txt        # Python dependencies
Dockerfile              # Container build
docker-compose.yml      # Multi-service local setup
start_dev.sh            # Dev startup helper
static/                 # Static assets (Bootstrap, JS, fonts, card images)
templates/
  index.html            # Home page / card creation form
  dashboard_accolli.html  # User dashboard
  show.html             # Card detail page
  access_denied.html    # Shown on invalid token
  includes/             # Shared partials (nav, head, modals, …)
```
