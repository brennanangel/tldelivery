# Guardsmen Tree Lot Delivery Scheduler

This project was scaffolded from [Cookie Cutter Django](http://cookiecutter-django.readthedocs.io). If you have any questions about the underlying structure (e.g., Docker config), that's a good place to start. There are a bunch of artifacts from the scaffolding process that I neglected to remeove.

## Getting Started

Settings are managed in an .env file. Copy `.env.template` to `.env` and fill out the relevant application secrets. This will require creating a Postgresql database.

All other commands are basic Django, e.g., `python manage.py migrate`, `python manage.py createsuperuser`.

## Run

`python manage.py runserver`

## Deploy

The respository is hooked up to a Google Cloud CD pipeline, which will build the Docker container and deploy to a Kubernetes cluster automatically.
