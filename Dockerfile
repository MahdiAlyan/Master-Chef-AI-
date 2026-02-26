# Dockerfile for ai_recipe_hub

FROM python:3.11-slim

# set environment
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /code

# install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy project
COPY . .

# make collectstatic optional on build? you can run on startup

# default command
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
