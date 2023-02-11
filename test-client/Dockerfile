FROM python:3.11
WORKDIR /app
COPY ./requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY tests /app/tests
WORKDIR /app/tests
ENV PYTHONUNBUFFERED 1
CMD "pytest" "${PYTEST_TESTS:=.}" | tee /var/log/pytest/result.log

