#!/bin/bash
export MONGO_HOST="localhost"
export FLASK_ENV=development
export FLASK_SECRET_KEY=secret_key
export BASE_URL=http://localhost:5000

python3 ./app.py
