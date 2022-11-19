# Guardsmen Tree Lot Delivery Scheduler

This project was scaffolded from [Cookie Cutter Django](http://cookiecutter-django.readthedocs.io). If you have any questions about the underlying structure (e.g., Docker config), that's a good place to start. There are a bunch of artifacts from the scaffolding process that I neglected to remeove.

## Getting Started

Settings are managed in an .env file. Copy `.env.template` to `.env` and fill out the relevant application secrets. This will require creating a Postgresql database.

All other commands are basic Django, e.g., `python manage.py migrate`, `python manage.py createsuperuser`. The theme files are available in `~/config/theme.json`.

## Run

`python manage.py runserver`

### Creating shifts

There is a manage.py command to create empty shifts, using start and end date. For example, `python manage.py create_shifts 2022-11-26 2022-12-13`.

## Deploy

The app lives on Google Cloud's App Engine. Copy all of the relevant secrets to an `env.yaml` file and deploy.

## Todo

- Better environment management w/ App Engine
- Update Cloud SQL to use DNS instead of IP
- Media management cleanup
- Test runner environment variables
- Skip canceled orders in Shopify
- Ensure items flow through from Shopify orders list
