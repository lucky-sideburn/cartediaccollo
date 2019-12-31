#!/bin/bash
export MONGO_HOST=127.0.0.1
export FLASK_ENV=development
export FLASK_SECRET_KEY=secret_key

python3 ./app.py
