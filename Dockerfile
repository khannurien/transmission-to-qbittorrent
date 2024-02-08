FROM python:3.10-slim as base

# Setup env
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1

FROM base AS python-deps

# Install pipenv and compilation dependencies
RUN pip install pipenv
RUN apt-get update && apt-get install -y --no-install-recommends gcc

# Install python dependencies in /.venv
COPY Pipfile .
COPY Pipfile.lock .
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy

FROM base AS runtime

# Create new user
RUN useradd --create-home app

# Copy virtual env from python-deps stage
COPY --from=python-deps --chown=app:app /.venv /.venv
ENV PATH="/.venv/bin:$PATH"

# Switch to new user
USER app
WORKDIR /home/app

# Install application into container
COPY --chown=app:app . .

# Run application
ENTRYPOINT ["python"]
CMD ["main.py"]
